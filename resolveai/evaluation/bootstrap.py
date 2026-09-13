"""Deterministic bootstrap confidence intervals.

Procedure (documented in artifacts/evaluation/statistical_uncertainty.md): resample the golden rows WITH replacement
n_boot times (default 1000) with numpy's Generator seeded from `seed` (default 42), recompute the statistic on each
resample, report the 2.5 / 97.5 percentiles. Paired comparisons resample the SAME row indices for both systems so the
difference's interval reflects per-row pairing. Rows with failed calls stay in the sample (they count as wrong).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np


def bootstrap_ci(rows: Sequence, stat: Callable[[list], float], *, n_boot: int = 1000, seed: int = 42, alpha: float = 0.05) -> dict:
    rows = list(rows)
    rng = np.random.default_rng(seed)
    n = len(rows)
    point = float(stat(rows))
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        vals.append(float(stat([rows[i] for i in idx])))
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"point": round(point, 4), "ci_low": round(float(lo), 4), "ci_high": round(float(hi), 4), "n": n, "n_boot": n_boot, "seed": seed}


def paired_bootstrap(rows_a: Sequence, rows_b: Sequence, stat: Callable[[list], float], *, n_boot: int = 1000, seed: int = 42, alpha: float = 0.05) -> dict:
    """CI of stat(B) - stat(A) with the same resampled indices for both systems (rows aligned by position)."""
    a, b = list(rows_a), list(rows_b)
    assert len(a) == len(b), "paired bootstrap needs aligned rows"
    rng = np.random.default_rng(seed)
    n = len(a)
    point = float(stat(b)) - float(stat(a))
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        vals.append(float(stat([b[i] for i in idx])) - float(stat([a[i] for i in idx])))
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"difference": round(point, 4), "ci_low": round(float(lo), 4), "ci_high": round(float(hi), 4), "n": n, "n_boot": n_boot, "seed": seed,
            "interval_excludes_zero": bool(lo > 0 or hi < 0)}
