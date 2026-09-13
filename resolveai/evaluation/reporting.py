"""Turns records + judge outputs into the evaluation artifacts. Pure functions over files; no agent or LLM calls.
Every table states its denominator; every headline metric carries a bootstrap interval from resolveai.evaluation.bootstrap.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from resolveai.evaluation.bootstrap import bootstrap_ci, paired_bootstrap
from resolveai.evaluation.judge import BINARY, DIMENSIONS
from resolveai.evaluation.metrics import autonomy_metrics, calibration, cost_latency, escalation_metrics, intent_metrics, is_safe_autonomous, selective_accuracy
from resolveai.evaluation.records import SystemRecord, read_records
from resolveai.evaluation.slices import gold_slices, record_slices, slice_table
from resolveai.models.taxonomy import INTENT_NAMES

PRIMARY_JUDGE = "glm-5.2"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def gold_map(gold: pd.DataFrame) -> dict[str, dict]:
    return {r.gid: {"intent": r.intent, "should_escalate": bool(r.should_escalate), "escalation_reason": r.escalation_reason} for r in gold.itertuples()}


def load_runs(runs_dir: Path) -> dict[str, list[SystemRecord]]:
    out = {}
    for p in sorted(runs_dir.glob("*.jsonl")):
        out[p.stem] = read_records(p)
    return out


def load_judge(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


# ------------------------------------------------------------------ per-system core metrics ------------------------
def _macro_f1(rows):
    return intent_metrics([g for g, _ in rows], [p for _, p in rows])["macro_f1"]


def _acc(rows):
    return float(np.mean([g == p for g, p in rows])) if rows else 0.0


def _esc_f1(rows):
    return escalation_metrics([g for g, _ in rows], [p for _, p in rows])["f1"]


def _esc_recall(rows):
    return escalation_metrics([g for g, _ in rows], [p for _, p in rows])["recall"]


def _rate(rows):
    return float(np.mean(rows)) if rows else 0.0


def system_report(recs: list[SystemRecord], gold: pd.DataFrame, gm: dict, *, n_boot: int = 1000, seed: int = 42) -> dict:
    recs = sorted(recs, key=lambda r: r.gid)
    yt, yp = [gm[r.gid]["intent"] for r in recs], [r.intent_pred for r in recs]
    et, ep = [gm[r.gid]["should_escalate"] for r in recs], [r.escalate_pred for r in recs]
    intent = intent_metrics(yt, yp)
    intent["bootstrap"] = {"macro_f1": bootstrap_ci(list(zip(yt, yp, strict=True)), _macro_f1, n_boot=n_boot, seed=seed), "accuracy": bootstrap_ci(list(zip(yt, yp, strict=True)), _acc, n_boot=n_boot, seed=seed)}
    esc = escalation_metrics(et, ep)
    esc["bootstrap"] = {"f1": bootstrap_ci(list(zip(et, ep, strict=True)), _esc_f1, n_boot=n_boot, seed=seed), "recall": bootstrap_ci(list(zip(et, ep, strict=True)), _esc_recall, n_boot=n_boot, seed=seed)}
    esc["false_negatives"] = [{"gid": r.gid, "gold_reason": gm[r.gid]["escalation_reason"], "action": r.action, "reason_code": r.reason_code, "message": r.message[:160]} for r in recs if gm[r.gid]["should_escalate"] and not r.escalate_pred]
    auto = autonomy_metrics(recs, gm)
    safe_rows = [is_safe_autonomous(r, gm[r.gid]["should_escalate"], gm[r.gid]["intent"])[0] for r in recs]
    auto["bootstrap"] = {"safe_auto_handle_rate": bootstrap_ci(safe_rows, _rate, n_boot=n_boot, seed=seed)}
    rep = {"system": recs[0].system, "n": len(recs), "failed": sum(1 for r in recs if r.failed), "intent": intent, "escalation": esc, "autonomy": auto, "cost_latency": cost_latency(recs)}
    conf = [r.intent_confidence for r in recs if r.intent_confidence is not None]
    if len(conf) == len(recs):
        correct = [r.intent_pred == gm[r.gid]["intent"] for r in recs]
        rep["calibration"] = calibration(conf, correct)
        rep["selective_prediction"] = selective_accuracy(conf, correct)
        by_band = {}
        for band in ("HIGH", "MEDIUM", "LOW"):
            rs = [r for r in recs if r.intent_band == band]
            if rs:
                by_band[band] = {"n": len(rs), "accuracy": round(float(np.mean([r.intent_pred == gm[r.gid]["intent"] for r in rs])), 3)}
        rep["accuracy_by_band"] = by_band
    return rep


# ------------------------------------------------------------------ judge aggregation ------------------------------
def judge_summary(judge_rows: list[dict], systems: list[str], gm: dict, recs_by_system: dict[str, list[SystemRecord]], *, judge_model: str = PRIMARY_JUDGE, n_boot: int = 1000, seed: int = 42) -> dict:
    out = {"judge_model": judge_model, "systems": {}}
    for s in systems:
        rows = [j for j in judge_rows if j["system"] == s and j.get("judge_model") == judge_model]
        n_total = len(rows)
        ok = [j for j in rows if not j.get("failed")]
        if not rows:
            continue
        rec_map = {r.gid: r for r in recs_by_system.get(s, [])}
        d = {"n_scored": n_total, "n_parsed": len(ok), "judge_failures": n_total - len(ok), "means": {}, "bootstrap": {}, "rates": {}}
        for dim in DIMENSIONS:
            vals = [j[dim] for j in ok]
            d["means"][dim] = round(float(np.mean(vals)), 3) if vals else None
            d["bootstrap"][dim] = bootstrap_ci(vals, _rate, n_boot=n_boot, seed=seed) if vals else None
            d["rates"][f"{dim}_share_ge4"] = round(float(np.mean([v >= 4 for v in vals])), 3) if vals else None
        for b in BINARY:
            vals = [bool(j[b]) for j in ok]
            d["rates"][b] = round(float(np.mean(vals)), 3) if vals else None
            d["bootstrap"][b] = bootstrap_ci(vals, _rate, n_boot=n_boot, seed=seed) if vals else None
        by_kind = {}
        for j in ok:
            k = rec_map[j["gid"]].response_kind if j["gid"] in rec_map else "?"
            by_kind.setdefault(k, []).append(j)
        d["by_response_kind"] = {k: {"n": len(v), **{dim: round(float(np.mean([j[dim] for j in v])), 2) for dim in DIMENSIONS}, "hallucination": round(float(np.mean([j["hallucination"] for j in v])), 3)} for k, v in by_kind.items()}
        out["systems"][s] = d
    return out


def pairwise_summary(pair_rows: list[dict], *, judge_model: str = PRIMARY_JUDGE) -> dict:
    out = {}
    for (x, y), rows in pd.DataFrame(pair_rows).groupby(["system_x", "system_y"]) if pair_rows else []:
        rows = rows[rows.judge_model == judge_model]
        ok = rows[~rows.failed.astype(bool)]
        wins = int((ok.winner == x).sum())
        losses = int((ok.winner == y).sum())
        ties = int((ok.winner == "tie").sum())
        pos_a = ok[ok.position_a == x]
        out[f"{x}_vs_{y}"] = {"n": int(len(rows)), "judge_failures": int(len(rows) - len(ok)), "win": wins, "tie": ties, "loss": losses,
                              "win_rate": round(wins / len(ok), 3) if len(ok) else None, "loss_rate": round(losses / len(ok), 3) if len(ok) else None,
                              "position_check": {"x_in_position_A": int(len(pos_a)), "x_wins_when_A": round(float((pos_a.winner == x).mean()), 3) if len(pos_a) else None,
                                                 "x_wins_when_B": round(float((ok[ok.position_b == x].winner == x).mean()), 3) if len(ok[ok.position_b == x]) else None},
                              "question": "Which response is safer and more useful given the available evidence?"}
    return out


# ------------------------------------------------------------------ comparisons ------------------------------------
def paired_comparisons(recs_by_system: dict[str, list[SystemRecord]], gm: dict, ref: str, others: list[str], *, n_boot: int = 1000, seed: int = 42) -> dict:
    out = {}
    base = {r.gid: r for r in recs_by_system[ref]}
    for o in others:
        if o not in recs_by_system:
            continue
        om = {r.gid: r for r in recs_by_system[o]}
        gids = sorted(set(base) & set(om))
        a_int = [(gm[g]["intent"], om[g].intent_pred) for g in gids]
        b_int = [(gm[g]["intent"], base[g].intent_pred) for g in gids]
        a_esc = [(gm[g]["should_escalate"], om[g].escalate_pred) for g in gids]
        b_esc = [(gm[g]["should_escalate"], base[g].escalate_pred) for g in gids]
        a_safe = [is_safe_autonomous(om[g], gm[g]["should_escalate"], gm[g]["intent"])[0] for g in gids]
        b_safe = [is_safe_autonomous(base[g], gm[g]["should_escalate"], gm[g]["intent"])[0] for g in gids]
        out[f"{ref}_minus_{o}"] = {"intent_macro_f1": paired_bootstrap(a_int, b_int, _macro_f1, n_boot=n_boot, seed=seed), "escalation_f1": paired_bootstrap(a_esc, b_esc, _esc_f1, n_boot=n_boot, seed=seed),
                                  "escalation_recall": paired_bootstrap(a_esc, b_esc, _esc_recall, n_boot=n_boot, seed=seed), "safe_auto_rate": paired_bootstrap(a_safe, b_safe, _rate, n_boot=n_boot, seed=seed)}
    return out


def slices_for(recs_by_system: dict[str, list[SystemRecord]], gold: pd.DataFrame) -> dict:
    gs = gold_slices(gold)
    out = {}
    for s, recs in recs_by_system.items():
        out[s] = slice_table(recs, gold, gs | record_slices(recs))
    return out


def counts_by_intent(recs: list[SystemRecord], gm: dict) -> dict:
    c = Counter()
    for r in recs:
        c[(gm[r.gid]["intent"], r.action)] += 1
    return {i: {a: c[(i, a)] for a in ("AUTO_HANDLE", "CLARIFICATION_REQUIRED", "HUMAN_HANDOFF", "CHANNEL_REDIRECT")} for i in INTENT_NAMES}
