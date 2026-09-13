"""Metric definitions (pure functions over labels/records; no agent logic). Every function returns plain dicts of floats
and ints so reports can serialise them. Denominators are always reported next to rates.

Definitions (evaluation contract, docs/EVALUATION.md):
- intent: accuracy, macro-F1 over the 11 taxonomy classes (zero_division=0), per-class precision/recall/F1/support, confusion.
- escalation: positive = HUMAN_HANDOFF; gold positive = should_escalate. precision, recall, F1, confusion, false-escalation
  rate (FP / gold negatives), missed-escalation rate (FN / gold positives), cost-weighted utility under ASSUMED cost ratios.
- autonomy: rates over all rows; SAFE AUTONOMOUS RESOLUTION (strict) = AUTO_HANDLE on a row the annotators marked
  should_escalate=false AND (troubleshooting reply with evidence refs that passed verification OR an appropriate canned
  template for a non_english / closure row); anything else autonomous is counted as unsafe or ungrounded, never as success.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from resolveai.evaluation.records import SystemRecord
from resolveai.models.taxonomy import INTENT_NAMES

CANNED_OK_INTENTS = {"non_english", "other"}   # the only gold intents for which a template counts as a safe resolution


def intent_metrics(y_true: list[str], y_pred: list[str], labels: list[str] | None = None) -> dict:
    labels = labels or INTENT_NAMES
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, average=None, zero_division=0)
    per_class = {lab: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4), "f1": round(float(f[i]), 4), "support": int(s[i]),
                       "predicted": int(sum(1 for x in y_pred if x == lab))} for i, lab in enumerate(labels)}
    macro_f1 = float(np.mean(f)) if len(f) else 0.0
    present = [i for i, lab in enumerate(labels) if s[i] > 0]
    return {"n": len(y_true), "accuracy": round(float(np.mean([a == b for a, b in zip(y_true, y_pred, strict=True)])), 4) if y_true else None,
            "macro_f1": round(macro_f1, 4), "macro_f1_present_classes_only": round(float(np.mean([f[i] for i in present])), 4) if present else None,
            "per_class": per_class, "confusion": {"labels": labels, "matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist()}}


def escalation_metrics(y_true: list[bool], y_pred: list[bool], cost_ratios: tuple[float, ...] = (1.0, 3.0, 5.0)) -> dict:
    yt, yp = np.array(y_true, dtype=bool), np.array(y_pred, dtype=bool)
    tp = int((yt & yp).sum())
    fp = int((~yt & yp).sum())
    fn = int((yt & ~yp).sum())
    tn = int((~yt & ~yp).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    out = {"n": int(len(yt)), "gold_positive": int(yt.sum()), "gold_negative": int((~yt).sum()), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
           "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
           "false_escalation_rate": round(fp / int((~yt).sum()), 4) if (~yt).sum() else None,
           "missed_escalation_rate": round(fn / int(yt.sum()), 4) if yt.sum() else None,
           "confusion_gold_x_pred": [[tn, fp], [fn, tp]],
           "cost_weighted": {}}
    for w in cost_ratios:
        # ASSUMED cost model: a false escalation costs 1 unit (a needless human touch); a missed escalation costs w units.
        cost = fp * 1.0 + fn * w
        worst = len(yt) * max(1.0, w)
        out["cost_weighted"][f"missed_cost_{w:g}x"] = {"total_cost": round(cost, 2), "cost_per_row": round(cost / len(yt), 4) if len(yt) else None,
                                                     "cost_sensitive_accuracy": round(1 - cost / worst, 4) if worst else None, "assumption": "false escalation = 1, missed escalation = w; not measured business costs"}
    return out


def is_safe_autonomous(rec: SystemRecord, gold_should_escalate: bool, gold_intent: str) -> tuple[bool, str]:
    """Strict definition. Returns (safe, reason)."""
    if rec.action != "AUTO_HANDLE":
        return False, "not_autonomous"
    if rec.failed:
        return False, "failed_call"
    if gold_should_escalate:
        return False, "unsafe_gold_should_escalate"
    if rec.response_kind == "canned":
        from resolveai.agent.drafter import CANNED

        expected = CANNED.get(gold_intent)   # the intent-appropriate template (language redirect / closure acknowledgement); a generic "DM us" is not a resolution
        if expected is None:
            return False, "canned_on_non_canned_intent"
        return (rec.response.strip() == expected.strip()), ("safe_canned" if rec.response.strip() == expected.strip() else "wrong_template")
    if rec.response_kind == "troubleshoot":
        if not rec.evidence_refs:
            return False, "ungrounded_no_refs"
        if rec.verified is not True:
            return False, "unverified"
        return True, "safe_grounded_verified"
    # copy / llm_direct: autonomous text with no verification and no grounding contract
    return False, f"unverified_{rec.response_kind}"


def autonomy_metrics(recs: list[SystemRecord], gold: dict[str, dict]) -> dict:
    n = len(recs)
    c = Counter(r.action for r in recs)
    reasons = Counter()
    safe = unsafe = grounded = 0
    correct_handoff = unnecessary_nonauto = 0
    for r in recs:
        g = gold[r.gid]
        ok, why = is_safe_autonomous(r, g["should_escalate"], g["intent"])
        reasons[why] += 1
        if r.action == "AUTO_HANDLE":
            if ok:
                safe += 1
            if g["should_escalate"]:
                unsafe += 1
            if r.response_kind == "troubleshoot" and r.evidence_refs and r.verified is True:
                grounded += 1
        else:
            if g["should_escalate"]:
                correct_handoff += 1
            else:
                unnecessary_nonauto += 1
    return {"n": n, "auto_handle_rate": round(c["AUTO_HANDLE"] / n, 4), "clarification_rate": round(c["CLARIFICATION_REQUIRED"] / n, 4), "handoff_rate": round(c["HUMAN_HANDOFF"] / n, 4),
            "auto_handle_count": c["AUTO_HANDLE"], "safe_auto_handle_count": safe, "safe_auto_handle_rate": round(safe / n, 4),
            "safe_share_of_auto": round(safe / c["AUTO_HANDLE"], 4) if c["AUTO_HANDLE"] else None, "unsafe_auto_handle_count": unsafe,
            "grounded_auto_handle_count": grounded, "correct_non_autonomous_count": correct_handoff, "unnecessary_non_autonomous_count": unnecessary_nonauto,
            "autonomy_outcomes": dict(reasons), "failed_rows": sum(1 for r in recs if r.failed),
            "definition": "safe = AUTO_HANDLE on a gold should_escalate=false row AND (verified troubleshooting reply with evidence refs OR the intent-appropriate canned template on a non_english/other row)"}


def cost_latency(recs: list[SystemRecord]) -> dict:
    lat = [r.latency_ms for r in recs]
    return {"n": len(recs), "p50_latency_ms": round(float(np.percentile(lat, 50)), 1) if lat else None, "p95_latency_ms": round(float(np.percentile(lat, 95)), 1) if lat else None,
            "llm_calls_per_message": round(float(np.mean([r.llm_calls for r in recs])), 3), "live_calls_per_message": round(float(np.mean([r.live_calls for r in recs])), 3),
            "tokens_in_per_message": round(float(np.mean([r.tokens_in for r in recs])), 1), "tokens_out_per_message": round(float(np.mean([r.tokens_out for r in recs])), 1),
            "estimated_cost_usd_per_message": round(float(np.mean([r.cost_usd for r in recs])), 6), "failed_calls": sum(1 for r in recs if r.failed)}


def calibration(confidences: list[float], correct: list[bool], bins: int = 5) -> dict:
    """Reliability table + expected calibration error over equal-width confidence bins."""
    conf, cor = np.array(confidences, dtype=float), np.array(correct, dtype=bool)
    edges = np.linspace(0, 1, bins + 1)
    rows, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (conf >= lo) & (conf < hi) if hi < 1 else (conf >= lo) & (conf <= hi)
        if m.sum():
            acc, avg = float(cor[m].mean()), float(conf[m].mean())
            ece += m.sum() / len(conf) * abs(acc - avg)
            rows.append({"bin": f"[{lo:.1f}, {hi:.1f}{')' if hi < 1 else ']'}", "n": int(m.sum()), "mean_confidence": round(avg, 3), "accuracy": round(acc, 3)})
    return {"n": int(len(conf)), "ece": round(float(ece), 4), "bins": rows}


def selective_accuracy(confidences: list[float], correct: list[bool], thresholds: tuple[float, ...] = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9)) -> list[dict]:
    conf, cor = np.array(confidences, dtype=float), np.array(correct, dtype=bool)
    out = []
    for t in thresholds:
        m = conf >= t
        out.append({"threshold": t, "coverage": round(float(m.mean()), 3), "n": int(m.sum()), "accuracy": round(float(cor[m].mean()), 3) if m.sum() else None})
    return out
