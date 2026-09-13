"""BM25 lexical retrieval baseline (rank_bm25 BM25Okapi).

Tokenisation decisions (documented for the benchmark):
- lowercase; keep alphanumeric runs; keep dotted version numbers as one token ("11.1.1", "10.13.1") because product
  versions are strong exact-match signals; keep redaction tokens (<phone>) and the <url> token as ordinary words;
- drop a small stopword list (function words only) so "my phone is not working" is not dominated by "my/is/not";
  negations are kept because "not charging" matters;
- no stemming (Twitter text is short; stemming mostly adds collisions like "charge/charger");
- a query with zero overlapping terms yields all-zero scores and is reported as a no-result query.
"""
from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"<[a-z_]+>|[a-z0-9]+(?:\.[0-9]+)+|[a-z0-9]+")
STOPWORDS = frozenset("a an the and or but if so of to in on at for with by from as is are was were be been am i im ive me my we our you your it its this that these those he she they them his her their do does did have has had would could should will can just".split())


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall((text or "").lower()) if t not in STOPWORDS]


class BM25Index:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self._bm25 = BM25Okapi([tokenize(t) for t in texts], k1=k1, b=b)
        self.n = len(texts)

    def scores(self, query: str) -> np.ndarray:
        toks = tokenize(query)
        if not toks:
            return np.zeros(self.n, dtype="float32")
        return np.asarray(self._bm25.get_scores(toks), dtype="float32")

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Top-k (index, score) with score > 0. Fewer than k results means the query had little lexical overlap."""
        s = self.scores(query)
        if not s.any():
            return []
        top = np.argpartition(-s, min(k, self.n - 1))[:k]
        top = top[np.argsort(-s[top], kind="stable")]
        return [(int(i), float(s[i])) for i in top if s[i] > 0]
