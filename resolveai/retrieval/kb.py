"""Knowledge base of historical (customer message -> AppleSupport reply) pairs.

Frozen construction rules (Phase 1, enforced here and in tests/test_retrieval.py):
- rows come ONLY from the `kb` temporal split of the shipped subsample; the holdout (and therefore every golden example)
  can never enter the index;
- every KB row precedes the holdout window (temporal eligibility), checked against the dataset manifest;
- IDs are the dataset's deterministic tweet ids; customer text is already PII-redacted by ingestion;
- rows with replies shorter than 40 characters are dropped (nothing to ground on); a `substantive` flag marks replies that
  are not DM handoffs and long enough to contain an action;
- the KB manifest records the preprocessing version, the subsample hash and a hash of the corpus texts, so any index or
  embedding cache is tied to exactly this corpus.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import pandas as pd

from resolveai import config
from resolveai.data.clean import is_dm_handoff
from resolveai.models.weak_labels import action_class, weak_intent
from resolveai.retrieval.bm25 import BM25Index
from resolveai.retrieval.dense import DenseIndex, Embedder, texts_hash

MIN_REPLY_CHARS = 40
SUBSTANTIVE_CHARS = 60


def _sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_kb_rows() -> pd.DataFrame:
    df = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", dtype={"context": str, "followup": str}, keep_default_na=False)
    df = df[df.split == "kb"].copy()
    df = df[df.brand_reply.str.len() >= MIN_REPLY_CHARS]
    df["dm_handoff"] = df.brand_reply.map(is_dm_handoff)
    df["substantive"] = (~df.dm_handoff) & (df.brand_reply.str.len() >= SUBSTANTIVE_CHARS)
    df["weak_intent"] = df.customer_message.map(weak_intent)
    df["action_class"] = df.brand_reply.map(action_class)
    df["created_at"] = pd.to_datetime(df.created_at, utc=True)
    df = df.sort_values(["created_at", "customer_tweet_id"]).reset_index(drop=True)
    df["doc"] = range(len(df))
    return df


@dataclass
class KnowledgeBase:
    rows: pd.DataFrame
    manifest: dict
    bm25: BM25Index | None = None
    dense: dict[str, DenseIndex] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)

    # ---- construction -------------------------------------------------------------------------
    @classmethod
    def build(cls, dense_models: list[str] | None = None, with_bm25: bool = True) -> KnowledgeBase:
        import time

        rows = load_kb_rows()
        dm = json.loads((config.PROCESSED_DIR / "dataset_manifest.json").read_text(encoding="utf-8"))
        corpus_hash = texts_hash(rows.customer_message.tolist())
        manifest = {
            "n_rows": int(len(rows)),
            "n_substantive": int(rows.substantive.sum()),
            "preprocessing_version": dm["preprocessing_version"],
            "subsample_sha256": dm["artifacts"]["apple_pairs.csv"]["sha256"],
            "corpus_hash": corpus_hash,
            "kb_max_created_at": str(rows.created_at.max()),
            "holdout_min_created_at": dm["split_boundaries"]["holdout_min_created_at"],
            "min_reply_chars": MIN_REPLY_CHARS,
            "substantive_chars": SUBSTANTIVE_CHARS,
        }
        kb = cls(rows=rows, manifest=manifest)
        kb.assert_eligible()
        if with_bm25:
            t0 = time.perf_counter()
            kb.bm25 = BM25Index(rows.customer_message.tolist())
            kb.timings["bm25_build_s"] = time.perf_counter() - t0
        for m in dense_models or []:
            kb.add_dense(m)
        return kb

    REPRESENTATIONS = ("customer", "reply", "pair")

    def add_dense(self, model_id: str, representation: str = "customer") -> None:
        """Index one representation of the KB rows: 'customer' (problem text), 'reply' (the brand's resolution text) or
        'pair' (customer + reply). Keys: model_id for 'customer' (Phase-2 compatible), f"{model_id}|{representation}" otherwise."""
        emb = Embedder(model_id)
        if representation == "customer":
            texts, tag, key = self.rows.customer_message.tolist(), "kb", model_id
        elif representation == "reply":
            texts, tag, key = self.rows.brand_reply.tolist(), "kb_reply", f"{model_id}|reply"
        elif representation == "pair":
            texts, tag, key = (self.rows.customer_message + " || reply: " + self.rows.brand_reply).tolist(), "kb_pair", f"{model_id}|pair"
        else:
            raise ValueError(representation)
        X, info = emb.encode(texts, tag=tag)
        self.dense[key] = DenseIndex(X)
        self.timings[f"embed_{emb.slug}_{representation}_s"] = info["seconds"]
        self.timings[f"embed_{emb.slug}_{representation}_cached"] = float(info["cached"])
        self.timings[f"load_{emb.slug}_s"] = emb.load_s

    def dense_index(self, model_id: str, representation: str = "customer") -> DenseIndex:
        key = model_id if representation == "customer" else f"{model_id}|{representation}"
        if key not in self.dense:
            self.add_dense(model_id, representation)
        return self.dense[key]

    # ---- invariants ----------------------------------------------------------------------------
    def assert_eligible(self) -> None:
        assert (self.rows.split == "kb").all(), "KB must contain only the kb split"
        assert self.manifest["kb_max_created_at"] < self.manifest["holdout_min_created_at"], "KB row after holdout start"
        assert self.rows.customer_tweet_id.is_unique and self.rows.brand_tweet_id.is_unique, "KB ids must be unique"

    def assert_isolated_from(self, ids: set[int], what: str = "golden") -> None:
        overlap = set(self.rows.customer_tweet_id.astype(int)) & set(int(i) for i in ids)
        assert not overlap, f"{what} rows found inside the KB: {sorted(overlap)[:5]}"

    def temporally_eligible(self, doc: int, query_created_at: pd.Timestamp | None) -> bool:
        return True if query_created_at is None else bool(self.rows.created_at.iat[doc] < query_created_at)

    # ---- provenance ----------------------------------------------------------------------------
    def source(self) -> dict[str, str]:
        return {"dataset": "kaggle:thoughtvector/customer-support-on-twitter:v10", "brand": config.BRAND,
                "preprocessing_version": self.manifest["preprocessing_version"], "kb_hash": self.manifest["corpus_hash"]}
