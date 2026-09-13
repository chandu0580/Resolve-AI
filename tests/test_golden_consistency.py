"""Annotation consistency tests for the candidate gold set (v1.1). Run after scripts/phase1/d2_apply_v11.py."""
import re

import pandas as pd
import pytest

from resolveai import config
from resolveai.models.taxonomy import INTENT_NAMES

G = config.GOLDEN_DIR
REASONS = {"safety", "legal_media", "private_info", "hardware", "repeat_contact", "vague_hostile", "none"}
FLAGS = ["taxonomy_gap", "insufficient_context", "multi_intent", "evidence_unavailable"]
SAFETY = re.compile(r"kill myself|smoke|burned me|shocked me", re.I)

pytestmark = pytest.mark.skipif(not (G / "golden_adjudicated.csv").exists(), reason="run d2_apply_v11.py first")


def _load(name):
    df = pd.read_csv(G / name, dtype=str, keep_default_na=False)
    df["should_escalate"] = df.should_escalate.str.lower().eq("true")
    for f in FLAGS:
        df[f] = df[f].str.lower().eq("true")
    return df


@pytest.fixture(scope="module")
def gold():
    return _load("golden_adjudicated.csv")


def test_shape_and_ids(gold):
    assert len(gold) == 197 and gold.gid.is_unique and gold.customer_tweet_id.is_unique


def test_vocabularies(gold):
    assert set(gold.intent) <= set(INTENT_NAMES)
    assert set(gold.escalation_reason) <= REASONS


def test_reason_iff_escalate(gold):
    assert (gold.should_escalate == (gold.escalation_reason != "none")).all()


def test_non_english_never_escalates(gold):
    assert not gold[gold.intent == "non_english"].should_escalate.any()


def test_other_escalates_only_for_explicit_prior_contact(gold):
    o = gold[(gold.intent == "other") & gold.should_escalate]
    assert set(o.escalation_reason) <= {"repeat_contact"} and len(o) <= 1


def test_safety_language_is_escalated_as_safety(gold):
    hits = gold[gold.customer_message.str.contains(SAFETY)]
    assert len(hits) >= 3 and (hits.escalation_reason == "safety").all()


def test_evidence_unavailable_matches_url_token(gold):
    assert (gold.evidence_unavailable == gold.customer_message.str.contains("<url>", regex=False)).all()


def test_taxonomy_gap_rows_use_allowed_fallbacks(gold):
    assert set(gold[gold.taxonomy_gap].intent) <= {"general_complaint", "apps_services", "connectivity"}


def test_both_passes_agree_after_v11():
    a, b = _load("golden_annotatorA_v11.csv"), _load("golden_annotatorB_v11.csv")
    m = a.merge(b, on="gid", suffixes=("_A", "_B"))
    for f in ("intent", "should_escalate", "escalation_reason"):
        assert (m[f + "_A"] == m[f + "_B"]).all(), f"residual disagreement on {f}"


def test_every_changed_label_has_a_rule():
    diff = pd.read_csv(G / "golden_v11_diff.csv", dtype=str)
    assert diff.rule.str.len().gt(0).all()
    assert set(diff.rule.str.split(",").explode()) <= {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "meta", "priority"}


def test_golden_disjoint_from_kb(gold):
    kb = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", usecols=["customer_tweet_id", "split"])
    assert not set(gold.customer_tweet_id.astype(int)) & set(kb[kb.split == "kb"].customer_tweet_id)
