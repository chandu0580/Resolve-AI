"""Judge <-> human agreement. Per-dimension only; never one pooled kappa across unrelated dimensions.

Ordinal dimensions (1-5): quadratic-weighted Cohen's kappa + Spearman rho (+ mean human - judge difference = leniency sign).
Binary outcomes (hallucination, policy_violation): Cohen's kappa + raw agreement.
Bootstrap CIs (seeded) over the rated examples. Returns status PENDING_HUMAN_RATINGS when the human columns are empty.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import cohen_kappa_score

from resolveai.evaluation.bootstrap import bootstrap_ci

ORDINAL = ("groundedness", "relevance", "actionability", "completeness", "policy_compliance", "tone")
BINARY = ("hallucination", "policy_violation")


def _kappa(a, b, weights=None) -> float | None:
    a, b = list(a), list(b)
    if len(set(a) | set(b)) < 2:
        return None   # kappa undefined when everyone gives one value
    try:
        return round(float(cohen_kappa_score(a, b, weights=weights)), 3)
    except ValueError:
        return None


def per_dimension_agreement(pairs: pd.DataFrame, *, n_boot: int = 1000, seed: int = 42) -> dict:
    """pairs: one row per rated example with columns human_<dim> and judge_<dim>."""
    out = {"n": int(len(pairs)), "ordinal": {}, "binary": {}}
    for d in ORDINAL:
        h, j = pairs[f"human_{d}"].astype(float), pairs[f"judge_{d}"].astype(float)
        m = h.notna() & j.notna()
        hh, jj = h[m].astype(int).tolist(), j[m].astype(int).tolist()
        if len(hh) < 3:
            out["ordinal"][d] = {"n": len(hh), "status": "insufficient"}
            continue
        rows = list(zip(hh, jj, strict=True))
        wk = bootstrap_ci(rows, lambda rs: (_kappa([x for x, _ in rs], [y for _, y in rs], "quadratic") or 0.0), n_boot=n_boot, seed=seed)
        rho = spearmanr(hh, jj)
        out["ordinal"][d] = {"n": len(hh), "weighted_kappa": _kappa(hh, jj, "quadratic"), "weighted_kappa_ci": [wk["ci_low"], wk["ci_high"]],
                             "spearman_rho": (round(float(rho.statistic), 3) if not np.isnan(rho.statistic) else None), "spearman_p": (round(float(rho.pvalue), 4) if not np.isnan(rho.pvalue) else None),
                             "exact_agreement": round(float(np.mean([x == y for x, y in rows])), 3), "within_one": round(float(np.mean([abs(x - y) <= 1 for x, y in rows])), 3),
                             "mean_human": round(float(np.mean(hh)), 3), "mean_judge": round(float(np.mean(jj)), 3),
                             "judge_minus_human": round(float(np.mean(jj) - np.mean(hh)), 3), "judge_leniency": ("lenient" if np.mean(jj) - np.mean(hh) > 0.25 else "harsh" if np.mean(jj) - np.mean(hh) < -0.25 else "neutral")}
    for d in BINARY:
        h, j = pairs[f"human_{d}"], pairs[f"judge_{d}"]
        m = h.notna() & j.notna()
        hh = [bool(int(x)) for x in h[m]]
        jj = [bool(x) if isinstance(x, (bool, np.bool_)) else bool(int(x)) for x in j[m]]
        if len(hh) < 3:
            out["binary"][d] = {"n": len(hh), "status": "insufficient"}
            continue
        rows = list(zip(hh, jj, strict=True))
        k = bootstrap_ci(rows, lambda rs: (_kappa([x for x, _ in rs], [y for _, y in rs]) or 0.0), n_boot=n_boot, seed=seed)
        out["binary"][d] = {"n": len(hh), "cohen_kappa": _kappa(hh, jj), "cohen_kappa_ci": [k["ci_low"], k["ci_high"]], "raw_agreement": round(float(np.mean([x == y for x, y in rows])), 3),
                            "human_positive_rate": round(float(np.mean(hh)), 3), "judge_positive_rate": round(float(np.mean(jj)), 3)}
    return out


def load_human_packet(packet_csv, key_json, judge_rows: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Joins the human-scored packet (blind example ids) with the judge scores through the hidden key. Returns (pairs, status)."""
    import json
    from pathlib import Path

    packet = pd.read_csv(packet_csv, dtype=str, keep_default_na=False)
    key = json.loads(Path(key_json).read_text(encoding="utf-8"))
    human_cols = [f"human_{d}" for d in ORDINAL + BINARY]
    filled = packet[human_cols].replace("", np.nan).notna().all(axis=1)
    status = {"n_examples": int(len(packet)), "n_fully_rated": int(filled.sum()), "n_partially_rated": int((packet[human_cols].replace("", np.nan).notna().any(axis=1) & ~filled).sum())}
    if status["n_fully_rated"] == 0:
        return pd.DataFrame(), status | {"status": "PENDING_HUMAN_RATINGS"}
    jmap = {(r["gid"], r["system"]): r for r in judge_rows if not r.get("failed")}
    rows = []
    for _, p in packet[filled].iterrows():
        k = key[p.example_id]
        j = jmap.get((k["gid"], k["system"]))
        if j is None:
            continue
        row = {"example_id": p.example_id, "gid": k["gid"], "system": k["system"]}
        for d in ORDINAL + BINARY:
            row[f"human_{d}"] = p[f"human_{d}"]
            row[f"judge_{d}"] = j[d]
        rows.append(row)
    return pd.DataFrame(rows), status | {"status": "RATED", "n_joined": len(rows)}
