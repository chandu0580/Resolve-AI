"""Reciprocal Rank Fusion. Combines ranked lists without calibrating incompatible score scales:
RRF(d) = sum over lists L of 1 / (k + rank_L(d)). Items absent from a list contribute 0 from that list."""
from __future__ import annotations


def rrf(ranked_lists: dict[str, list[int]], k: int = 60) -> list[tuple[int, float, dict[str, int]]]:
    """ranked_lists: name -> list of doc ids in rank order (best first).
    Returns [(doc_id, rrf_score, {list_name: rank}), ...] sorted by score desc, ties broken by doc id for determinism."""
    scores: dict[int, float] = {}
    ranks: dict[int, dict[str, int]] = {}
    for name, docs in ranked_lists.items():
        for r, d in enumerate(docs, start=1):
            scores[d] = scores.get(d, 0.0) + 1.0 / (k + r)
            ranks.setdefault(d, {})[name] = r
    return sorted(((d, s, ranks[d]) for d, s in scores.items()), key=lambda t: (-t[1], t[0]))
