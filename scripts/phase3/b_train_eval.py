"""Phase 3-B: baselines, model selection on DEV (silver labels), calibration on DEV, freeze, then ONE golden evaluation.
  python scripts/phase3/b_train_eval.py
Writes artifacts/intelligence/{classifier_results.json, classifier_results.md, per_query_golden_intent.jsonl}
and the frozen artifact resolveai/models/artifacts/intent_bge_lr.json.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

import resolveai  # noqa: F401
from resolveai import config
from resolveai.evaluation import load_golden
from resolveai.intelligence.classifier import EmbedLR, KeywordClassifier, MajorityClassifier, TfidfLR, to_result
from resolveai.intelligence.context import build_context, parse_context
from resolveai.models.taxonomy import INTENT_NAMES
from resolveai.retrieval.dense import SUPPORTED, Embedder

OUT = Path("artifacts/intelligence")
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(config.SEED)


def ece(P: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    conf, pred = P.max(axis=1), P.argmax(axis=1)
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=False):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return round(float(e), 4)


def brier(P: np.ndarray, y: np.ndarray) -> float:
    Y = np.zeros_like(P)
    Y[np.arange(len(y)), y] = 1
    return round(float(((P - Y) ** 2).sum(axis=1).mean()), 4)


def metrics(P: np.ndarray, y_true: list[str]) -> dict:
    y = np.array([INTENT_NAMES.index(v) for v in y_true])
    pred = P.argmax(axis=1)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=range(len(INTENT_NAMES)), zero_division=0)
    return {"n": int(len(y)), "accuracy": round(float(accuracy_score(y, pred)), 4), "macro_f1": round(float(f1_score(y, pred, average="macro", zero_division=0)), 4),
            "weighted_f1": round(float(f1_score(y, pred, average="weighted", zero_division=0)), 4), "ece": ece(P, y), "brier": brier(P, y),
            "per_intent": {n: {"precision": round(float(p[i]), 3), "recall": round(float(r[i]), 3), "f1": round(float(f[i]), 3), "support": int(s[i])} for i, n in enumerate(INTENT_NAMES)},
            "confusion": confusion_matrix(y, pred, labels=range(len(INTENT_NAMES))).tolist()}


def boot_ci(P: np.ndarray, y_true: list[str], n: int = 500) -> dict:
    y = np.array([INTENT_NAMES.index(v) for v in y_true])
    pred = P.argmax(axis=1)
    accs, f1s = [], []
    for _ in range(n):
        i = RNG.integers(0, len(y), len(y))
        accs.append((pred[i] == y[i]).mean())
        f1s.append(f1_score(y[i], pred[i], average="macro", zero_division=0))
    return {"accuracy": [round(float(np.percentile(accs, 2.5)), 3), round(float(np.percentile(accs, 97.5)), 3)],
            "macro_f1": [round(float(np.percentile(f1s, 2.5)), 3), round(float(np.percentile(f1s, 97.5)), 3)]}


def main() -> None:
    t_all = time.perf_counter()
    train = pd.read_csv(config.PROCESSED_DIR / "silver_train.csv", keep_default_na=False)
    dev = pd.read_csv(config.PROCESSED_DIR / "silver_dev.csv", keep_default_na=False)
    gold = load_golden()
    assert not set(train.customer_tweet_id) & set(gold.customer_tweet_id.astype(int)) and not set(dev.customer_tweet_id) & set(gold.customer_tweet_id.astype(int))
    emb = Embedder(SUPPORTED["bge-small"])
    Xtr_all, _ = emb.encode(train.customer_message.tolist(), tag="kb")      # cached by the silver step
    Xdev, _ = emb.encode(dev.customer_message.tolist(), tag="silverdev")
    ydev = dev.silver_intent.tolist()
    # training band set is a hyperparameter: HIGH only (~0.82 precision, fewer rows) vs HIGH+MEDIUM (~0.71, more rows); chosen on DEV
    band_sets = {"HIGH": ["HIGH"], "HIGH+MEDIUM": ["HIGH", "MEDIUM"]}
    report: dict = {"dev_rows": int(len(dev)), "timings_s": {}, "band_set_dev": {}}
    best_bs = None
    for bs_name, bands in band_sets.items():
        m_idx = train.silver_band.isin(bands).values
        sc = metrics(EmbedLR(C=1.0).fit(None, train.silver_intent[m_idx].tolist(), X=Xtr_all[m_idx]).predict_proba(X=Xdev), ydev)
        report["band_set_dev"][bs_name] = {"rows": int(m_idx.sum()), "macro_f1": sc["macro_f1"], "accuracy": sc["accuracy"]}
        if best_bs is None or sc["macro_f1"] > best_bs[1]:
            best_bs = (bs_name, sc["macro_f1"])
    tr = train[train.silver_band.isin(band_sets[best_bs[0]])]
    Xtr = Xtr_all[train.silver_band.isin(band_sets[best_bs[0]]).values]
    ytr = tr.silver_intent.tolist()
    report |= {"train_band_set": best_bs[0], "train_rows_used": int(len(tr)), "train_coverage": round(len(tr) / len(train), 4)}

    # ---- baselines + selection on DEV (silver) ----
    dev_scores = {}
    t0 = time.perf_counter()
    maj = MajorityClassifier().fit(tr.customer_message, ytr)
    dev_scores["majority"] = metrics(maj.predict_proba(dev.customer_message), ydev)
    report["timings_s"]["majority"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    kw = KeywordClassifier()
    dev_scores["keyword"] = metrics(kw.predict_proba(dev.customer_message), ydev)
    report["timings_s"]["keyword"] = time.perf_counter() - t0
    best_tfidf = None
    for C in (0.5, 2.0, 8.0):
        t0 = time.perf_counter()
        m = TfidfLR(C=C).fit(tr.customer_message.tolist(), ytr)
        sc = metrics(m.predict_proba(dev.customer_message.tolist()), ydev)
        if best_tfidf is None or sc["macro_f1"] > best_tfidf[1]["macro_f1"]:
            best_tfidf = (m, sc, C, time.perf_counter() - t0)
    dev_scores["tfidf_lr"] = best_tfidf[1] | {"C": best_tfidf[2]}
    report["timings_s"]["tfidf_lr_fit"] = best_tfidf[3]
    best_emb = None
    for C in (0.25, 1.0, 4.0):
        for cw in ("balanced", None):
            t0 = time.perf_counter()
            m = EmbedLR(C=C, class_weight=cw).fit(None, ytr, X=Xtr)
            sc = metrics(m.predict_proba(X=Xdev), ydev)
            if best_emb is None or sc["macro_f1"] > best_emb[1]["macro_f1"]:
                best_emb = (m, sc, {"C": C, "class_weight": cw}, time.perf_counter() - t0)
    model = best_emb[0]
    dev_scores["embed_lr_uncalibrated"] = best_emb[1] | best_emb[2]
    report["timings_s"]["embed_lr_fit"] = best_emb[3]

    # ---- calibration on DEV ----
    cal = model.calibrate(None, ydev, X=Xdev)
    Pdev = model.predict_proba(X=Xdev)
    dev_scores["embed_lr_calibrated"] = metrics(Pdev, ydev) | best_emb[2] | cal
    # bands from DEV reliability: HIGH = lowest confidence at which predictions above it are >= 0.85 accurate; MEDIUM >= 0.60
    ydev_i = np.array([INTENT_NAMES.index(v) for v in ydev])
    conf, pred = Pdev.max(axis=1), Pdev.argmax(axis=1)
    def acc_above(p):
        mask = conf >= p
        return float((pred[mask] == ydev_i[mask]).mean()) if mask.sum() >= 30 else 0.0

    high = next((p for p in np.arange(0.5, 0.96, 0.05) if acc_above(p) >= 0.85), 0.75)
    medium = next((p for p in np.arange(0.3, high, 0.05) if acc_above(p) >= 0.60), 0.45)
    model.band_high, model.band_medium = round(float(high), 2), round(float(medium), 2)
    model.meta = {"dev_ece": dev_scores["embed_lr_calibrated"]["ece"], "dev_macro_f1_silver": dev_scores["embed_lr_calibrated"]["macro_f1"], "silver_version": "silver-v2",
                  "band_rule": "HIGH: dev acc>=0.85 above threshold; MEDIUM: >=0.60", "selected_on": "silver dev macro-F1"}
    model.save()
    report["selected"] = {"model": "embed_lr", **best_emb[2], "train_band_set": best_bs[0], "temperature": model.temperature, "band_high": model.band_high, "band_medium": model.band_medium}
    report["dev"] = dev_scores
    reliability = []
    for lo in np.arange(0, 1, 0.1):
        m = (conf > lo) & (conf <= lo + 0.1)
        if m.any():
            reliability.append({"bin": f"{lo:.1f}-{lo+0.1:.1f}", "n": int(m.sum()), "confidence": round(float(conf[m].mean()), 3), "accuracy": round(float((pred[m] == ydev_i[m]).mean()), 3)})
    report["dev_reliability"] = reliability

    # ---- smoke-dev (30 hand-labelled) sanity, not for selection ----
    smoke = [json.loads(line) for line in Path("data/dev/smoke_dev.jsonl").read_text(encoding="utf-8").splitlines()]
    report["smoke_dev_hand_labelled"] = {"n": len(smoke), "embed_lr_accuracy": metrics(model.predict_proba([s["customer_message"] for s in smoke], tag="smoke"), [s["intent"] for s in smoke])["accuracy"],
                                         "keyword_accuracy": metrics(kw.predict_proba([s["customer_message"] for s in smoke]), [s["intent"] for s in smoke])["accuracy"]}

    # ---- GOLDEN, once ----
    ygold = gold.intent.tolist()
    bundles = [build_context(m, parse_context(c)) for m, c in zip(gold.customer_message, gold.context, strict=False)]
    textA = gold.customer_message.tolist()
    textB = [b.text_for_classification for b in bundles]
    golden = {"majority": metrics(maj.predict_proba(textA), ygold), "keyword": metrics(kw.predict_proba(textA), ygold),
              "tfidf_lr": metrics(best_tfidf[0].predict_proba(textA), ygold)}
    t0 = time.perf_counter()
    PA = model.predict_proba(textA, tag="q")
    report["timings_s"]["golden_embed_lr_197_predict"] = time.perf_counter() - t0
    PB = model.predict_proba(textB, tag="goldctx")
    golden["embed_lr_message_only"] = metrics(PA, ygold) | {"ci95": boot_ci(PA, ygold)}
    golden["embed_lr_with_context"] = metrics(PB, ygold) | {"ci95": boot_ci(PB, ygold)}
    # per-query records + slices for the context variant (the deployed one)
    recs = []
    for k, (g, b) in enumerate(zip(gold.itertuples(), bundles, strict=False)):
        rA, rB = to_result(PA[k], method="embed_lr", calibrated=True, band_high=model.band_high, band_medium=model.band_medium), \
                 to_result(PB[k], method="embed_lr", calibrated=True, band_high=model.band_high, band_medium=model.band_medium, context_used=b.used_context, insufficient_context=b.insufficient_context)
        recs.append({"gid": g.gid, "gold": g.intent, "predA": rA.intent, "confA": rA.confidence, "predB": rB.intent, "confB": rB.confidence, "bandB": rB.confidence_band,
                     "correctA": rA.intent == g.intent, "correctB": rB.intent == g.intent, "context_used": b.used_context, "short_reply": b.is_short_reply,
                     "pred_insufficient_context": b.insufficient_context, "pred_multi": rB.multi_intent, "secondary": rB.secondary_intents, "pred_gap": rB.taxonomy_gap, "top3B": rB.top3,
                     "slices": {"short": len(g.customer_message) < 40, "first_turn": int(g.n_context_turns) == 0, "multi_turn": int(g.n_context_turns) > 0,
                                "multi_intent": bool(g.multi_intent), "insufficient_context": bool(g.insufficient_context), "taxonomy_gap": bool(g.taxonomy_gap),
                                "evidence_unavailable": bool(g.evidence_unavailable), "customer_seen_in_kb": str(g.customer_seen_in_kb).lower() == "true", "low_confidence": rB.confidence_band == "LOW"}})
    (OUT / "per_query_golden_intent.jsonl").write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    slices = {}
    for s in recs[0]["slices"]:
        rs = [r for r in recs if r["slices"][s]]
        if rs:
            slices[s] = {"n": len(rs), "acc_message_only": round(sum(r["correctA"] for r in rs) / len(rs), 3), "acc_with_context": round(sum(r["correctB"] for r in rs) / len(rs), 3)}
    golden["slices_embed_lr"] = slices
    flags = {"multi_intent": {"gold_n": int(gold.multi_intent.sum()), "pred_n": sum(r["pred_multi"] for r in recs), "tp": sum(r["pred_multi"] and r["slices"]["multi_intent"] for r in recs)},
             "insufficient_context": {"gold_n": int(gold.insufficient_context.sum()), "pred_n": sum(r["pred_insufficient_context"] for r in recs), "tp": sum(r["pred_insufficient_context"] and r["slices"]["insufficient_context"] for r in recs)},
             "taxonomy_gap": {"gold_n": int(gold.taxonomy_gap.sum()), "pred_n": sum(r["pred_gap"] for r in recs), "tp": sum(r["pred_gap"] and r["slices"]["taxonomy_gap"] for r in recs)}}
    golden["flag_detection"] = flags
    golden["band_distribution_with_context"] = pd.Series([r["bandB"] for r in recs]).value_counts().to_dict()
    golden["accuracy_by_band_with_context"] = {b: round(float(np.mean([r["correctB"] for r in recs if r["bandB"] == b])), 3) for b in ("HIGH", "MEDIUM", "LOW") if any(r["bandB"] == b for r in recs)}
    report["golden"] = golden
    report["timings_s"] = {k: round(v, 3) for k, v in report["timings_s"].items()} | {"total": round(time.perf_counter() - t_all, 1)}
    (OUT / "classifier_results.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")

    # ---- markdown ----
    L = ["# Intent classifier results (Phase 3)", "", f"Train: {len(tr)} silver-v2 rows ({best_bs[0]} band(s), {report['train_coverage']:.0%} of KB; band-set choice on DEV: {report['band_set_dev']}). Dev: {len(dev)} silver-labelled holdout rows (selection + calibration). Golden: 197 human-labelled, evaluated once.", "",
         "## DEV (silver labels; noisy, used for selection only)", "", "| model | accuracy | macro-F1 | weighted-F1 | ECE | Brier |", "|---|---|---|---|---|---|"]
    for n, m in dev_scores.items():
        L.append(f"| {n} | {m['accuracy']} | {m['macro_f1']} | {m['weighted_f1']} | {m['ece']} | {m['brier']} |")
    L += ["", f"Selected: `{report['selected']}`. Smoke-dev (30 hand-labelled) accuracy: embed_lr {report['smoke_dev_hand_labelled']['embed_lr_accuracy']}, keyword {report['smoke_dev_hand_labelled']['keyword_accuracy']}.", "",
          "## GOLDEN (197, once)", "", "| model | accuracy | macro-F1 | weighted-F1 | ECE | Brier | 95% CI acc | 95% CI macro-F1 |", "|---|---|---|---|---|---|---|---|"]
    for n, m in golden.items():
        if "accuracy" in m:
            ci = m.get("ci95", {})
            L.append(f"| {n} | {m['accuracy']} | {m['macro_f1']} | {m['weighted_f1']} | {m['ece']} | {m['brier']} | {ci.get('accuracy', '')} | {ci.get('macro_f1', '')} |")
    L += ["", "### Per-intent (embed_lr with context)", "", "| intent | P | R | F1 | support |", "|---|---|---|---|---|"]
    for n, v in golden["embed_lr_with_context"]["per_intent"].items():
        L.append(f"| {n} | {v['precision']} | {v['recall']} | {v['f1']} | {v['support']} |")
    L += ["", "### Slices (accuracy)", "", "| slice | n | message only | with context |", "|---|---|---|---|"] + [f"| {s} | {v['n']} | {v['acc_message_only']} | {v['acc_with_context']} |" for s, v in slices.items()]
    L += ["", f"Bands on golden (with context): {golden['band_distribution_with_context']}; accuracy by band: {golden['accuracy_by_band_with_context']}", "", f"Flag detection: {flags}", "",
          "### DEV reliability (calibrated)", "", "| bin | n | mean confidence | accuracy |", "|---|---|---|---|"] + [f"| {r['bin']} | {r['n']} | {r['confidence']} | {r['accuracy']} |" for r in reliability]
    L += ["", f"Timings (s): {report['timings_s']}"]
    (OUT / "classifier_results.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
