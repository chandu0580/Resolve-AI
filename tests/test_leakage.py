"""Data-leakage defence: temporal separation, golden isolation, KB eligibility, deterministic ids."""
import json

import pandas as pd
import pytest

from resolveai import config
from resolveai.retrieval.kb import load_kb_rows as kb_rows

SUB = config.PROCESSED_DIR / "apple_pairs.csv"
GOLD = config.GOLDEN_DIR / "golden_final.csv"
pytestmark = pytest.mark.skipif(not SUB.exists(), reason="processed subsample missing")


@pytest.fixture(scope="module")
def sub():
    return pd.read_csv(SUB, parse_dates=["created_at"])


@pytest.fixture(scope="module")
def gold():
    if not GOLD.exists():
        pytest.skip("golden_final.csv not frozen yet")
    return pd.read_csv(GOLD, parse_dates=["created_at"])


def test_temporal_split_is_strict(sub):
    kb, ho = sub[sub.split == "kb"], sub[sub.split == "holdout"]
    assert kb.created_at.max() < ho.created_at.min()
    assert set(sub.split) == {"kb", "holdout"}


def test_kb_rows_are_only_kb_split(sub):
    rows = kb_rows()
    assert (rows.split == "kb").all() and set(rows.customer_tweet_id) <= set(sub[sub.split == "kb"].customer_tweet_id)


def test_golden_isolated_from_kb_and_after_it(sub, gold):
    kb = sub[sub.split == "kb"]
    assert not set(gold.customer_tweet_id) & set(kb.customer_tweet_id)
    assert not set(gold.brand_tweet_id) & set(kb.brand_tweet_id)
    assert gold.created_at.min() > kb.created_at.max(), "historical evidence must predate every golden example"


def test_golden_rows_come_from_holdout(sub, gold):
    full = config.PROCESSED_DIR / "full_apple_pairs.csv"
    if full.exists():
        ho = set(sub[sub.split == "holdout"].customer_tweet_id) | set(pd.read_csv(full, usecols=["customer_tweet_id"]).customer_tweet_id)
        assert set(gold.customer_tweet_id) <= ho
    # The full pair file is local-only (gitignored) and golden rows were sampled from the FULL holdout, not the 2,000-row subsample.
    # The committed manifest records the split boundaries, which prove the same property in a fresh clone.
    bounds = json.loads((config.PROCESSED_DIR / "dataset_manifest.json").read_text(encoding="utf-8"))["split_boundaries"]
    created = pd.to_datetime(gold.created_at, utc=True)
    assert created.min() >= pd.Timestamp(bounds["holdout_min_created_at"]) and created.max() <= pd.Timestamp(bounds["holdout_max_created_at"])


def test_ids_are_deterministic_and_unique(sub, gold):
    assert sub.customer_tweet_id.is_unique and gold.gid.is_unique
    assert list(gold.gid) == [f"g{i:03d}" for i in range(len(gold))]


def test_customer_identity_leakage_is_measured(sub):
    man = json.loads((config.PROCESSED_DIR / "dataset_manifest.json").read_text(encoding="utf-8"))
    share = man["holdout_customer_seen_in_kb_share"]
    assert 0 <= share <= 1 and "customer_seen_in_kb" in sub.columns
    assert abs(sub[sub.split == "holdout"].customer_seen_in_kb.mean() - share) < 1e-6


def test_no_raw_pii_survives_in_processed_text(sub):
    # Phase 9: the corrected phone pattern finds 4 sentence-end phone/case numbers the pre-Phase-9 redactor missed in the frozen, manifest-hashed
    # corpus (all in the KB split; the holdout, and so the golden set, has none). The data is not rewritten; retrieval re-redacts evidence text.
    from resolveai.trust.pii import contains_unredacted_pii, redact_pii
    gap = sub[sub.customer_message.map(contains_unredacted_pii)]
    assert len(gap) == 4 and (gap.split == "kb").all(), f"expected the 4 measured KB rows, found {len(gap)}"
    assert not gap.customer_message.map(lambda t: contains_unredacted_pii(redact_pii(t).text)).any()
