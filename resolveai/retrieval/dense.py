"""Dense retrieval with deterministic embedding cache.

Cache key = SHA-256(model id, model revision string, normalised text list hash). Embeddings for the KB corpus are stored as
one .npy per (model, corpus hash); query embeddings are cached per text. No network call happens once the model weights
are present locally.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from resolveai import config

SUPPORTED = {
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "bge-small": "BAAI/bge-small-en-v1.5",
}
_CACHE = config.CACHE_DIR / "embeddings"


def model_slug(model_id: str) -> str:
    for k, v in SUPPORTED.items():
        if v == model_id:
            return k
    return hashlib.sha256(model_id.encode()).hexdigest()[:10]


def texts_hash(texts: list[str]) -> str:
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:24]


class Embedder:
    _models: dict[str, object] = {}
    _memo: dict[tuple[str, str], np.ndarray] = {}   # (model, text) -> vector; bounded by _MEMO_MAX
    _MEMO_MAX = 2048

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.slug = model_slug(model_id)
        self.dir = _CACHE / self.slug
        self.dir.mkdir(parents=True, exist_ok=True)
        self.load_s = 0.0

    def _model(self):
        if self.model_id not in Embedder._models:
            from sentence_transformers import SentenceTransformer  # heavy, lazy

            t0 = time.perf_counter()
            Embedder._models[self.model_id] = SentenceTransformer(self.model_id)
            self.load_s = time.perf_counter() - t0
        return Embedder._models[self.model_id]

    def encode_one(self, text: str) -> np.ndarray:
        """Single-text embedding with an in-process memo, so the classifier and the retriever share one computation."""
        k = (self.model_id, text)
        if k not in Embedder._memo:
            if len(Embedder._memo) >= Embedder._MEMO_MAX:
                Embedder._memo.clear()
            Embedder._memo[k] = self._model().encode([text], normalize_embeddings=True, show_progress_bar=False).astype("float32")[0]
        return Embedder._memo[k]

    def encode(self, texts: list[str], *, tag: str = "") -> tuple[np.ndarray, dict]:
        """Returns (embeddings float32 L2-normalised, info{cached, seconds})."""
        key = texts_hash(texts)
        p = self.dir / f"{tag or 'batch'}_{key}.npy"
        if p.exists():
            return np.load(p), {"cached": True, "seconds": 0.0, "key": key}
        t0 = time.perf_counter()
        X = self._model().encode(texts, batch_size=128, normalize_embeddings=True, show_progress_bar=False).astype("float32")
        secs = time.perf_counter() - t0
        np.save(p, X)
        (self.dir / f"{tag or 'batch'}_{key}.json").write_text(json.dumps({"model": self.model_id, "n": len(texts), "seconds": secs}))
        return X, {"cached": False, "seconds": secs, "key": key}


class DenseIndex:
    """Exact inner-product search over L2-normalised vectors (cosine). FAISS flat; numpy fallback for tiny corpora."""

    def __init__(self, X: np.ndarray):
        self.X = X
        try:
            import faiss

            self._index = faiss.IndexFlatIP(X.shape[1])
            self._index.add(X)
        except ImportError:  # pragma: no cover
            self._index = None

    def search(self, q: np.ndarray, k: int) -> list[tuple[int, float]]:
        if self._index is not None:
            s, i = self._index.search(q.reshape(1, -1), min(k, len(self.X)))
            return [(int(j), float(v)) for v, j in zip(s[0], i[0], strict=False) if j >= 0]
        s = self.X @ q
        top = np.argsort(-s)[:k]
        return [(int(j), float(s[j])) for j in top]

    def cosine(self, q: np.ndarray, idx: list[int]) -> np.ndarray:
        return self.X[idx] @ q


def save_index_path(slug: str, corpus_hash: str) -> Path:
    return _CACHE / slug / f"kb_{corpus_hash}.npy"
