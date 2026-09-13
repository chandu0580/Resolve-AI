"""Phase 3 intelligence-layer tests: context builder, query constructor, classifier output contract, multi-intent,
insufficient context, calibration helpers, PII safety, retrieval boost, golden isolation. No network, no model downloads."""
import numpy as np
import pytest

from resolveai.intelligence.classifier import EmbedLR, band, softmax, to_result
from resolveai.intelligence.context import (
    MAX_BRAND_TURNS,
    MAX_CUSTOMER_TURNS,
    TOTAL_CHARS,
    build_context,
    content_tokens,
    parse_context,
)
from resolveai.intelligence.query import CANONICAL, build_query
from resolveai.models.taxonomy import INTENT_NAMES
from resolveai.retrieval.fusion import rrf
from resolveai.schemas import ConversationContext, ConversationTurn, IntentResult


# ------------------------------------------------------------------ context builder ----------------------------------
def test_parse_context_roundtrip():
    ctx = parse_context("customer: iPhone keeps restarting\nbrand: Did you update iOS?")
    assert [t.role for t in ctx.turns] == ["customer", "brand"] and ctx.turns[0].text == "iPhone keeps restarting"


def test_short_reply_uses_issue_text_from_context():
    ctx = parse_context("customer: iPhone keeps restarting every 30 seconds\nbrand: Did you update iOS?")
    b = build_context("yes", ctx)
    assert b.is_short_reply and b.issue_text == "iPhone keeps restarting every 30 seconds" and not b.insufficient_context
    assert b.text_for_classification == "iPhone keeps restarting every 30 seconds || reply: yes" and b.used_context


def test_short_reply_without_informative_context_is_insufficient():
    b = build_context("still happening", parse_context("brand: Which iPhone do you have?"))
    assert b.is_short_reply and b.insufficient_context and b.issue_text == "" and b.text_for_classification == "still happening"
    assert build_context("ok", None).insufficient_context


def test_long_message_ignores_context_for_classification():
    b = build_context("my battery drains from 100 to 40 in an hour since the update", parse_context("customer: hello"))
    assert not b.is_short_reply and b.text_for_classification == b.current and not b.used_context


def test_context_is_bounded_and_deduplicated():
    turns = [ConversationTurn(role="customer", text=f"customer turn number {i} with enough words to count") for i in range(6)]
    turns += [ConversationTurn(role="brand", text="Try a restart. ^EC")] * 3 + [ConversationTurn(role="customer", text="<url>")]
    b = build_context("yes", ConversationContext(turns=turns))
    assert len(b.prior_customer) <= MAX_CUSTOMER_TURNS and len(b.prior_brand) <= MAX_BRAND_TURNS and b.truncated
    assert b.prior_brand == ["Try a restart."] and all("<url>" != t for t in b.prior_customer)
    assert sum(len(t) for t in b.prior_customer + b.prior_brand) <= TOTAL_CHARS
    assert b.prior_customer[0] == "customer turn number 5 with enough words to count"  # most recent first


def test_context_refuses_unredacted_pii():
    with pytest.raises(ValueError):
        build_context("call me on 415-555-0134", None)
    with pytest.raises(ValueError):
        build_context("yes", parse_context("customer: my email is a@b.com"))
    build_context("yes", parse_context("customer: my email is <EMAIL> and the battery dies"))  # redacted is fine


def test_content_tokens_ignores_placeholders():
    assert content_tokens("<url>") == 0 and content_tokens("fix this <url>") == 1 and content_tokens("battery drains fast") == 3


# ------------------------------------------------------------------ classifier contract ------------------------------
def _P(**probs):
    P = np.full(len(INTENT_NAMES), 0.001)
    for k, v in probs.items():
        P[INTENT_NAMES.index(k)] = v
    return P / P.sum()


def test_to_result_bands_and_top3():
    r = to_result(_P(battery_power=0.9), method="embed_lr", calibrated=True)
    assert r.intent == "battery_power" and r.confidence_band == "HIGH" and len(r.top3) == 3 and r.top3[0][0] == "battery_power" and not r.multi_intent
    assert band(0.5) == "MEDIUM" and band(0.2) == "LOW"


def test_multi_intent_detection_from_probabilities():
    r = to_result(_P(battery_power=0.5, performance_crash=0.35), method="embed_lr", calibrated=True)
    assert r.multi_intent and r.secondary_intents == ["performance_crash"] and r.intent == "battery_power"
    r2 = to_result(_P(battery_power=0.8, performance_crash=0.1), method="embed_lr", calibrated=True)
    assert not r2.multi_intent


def test_insufficient_context_forces_low_band_and_taxonomy_gap_flag():
    r = to_result(_P(battery_power=0.9), method="embed_lr", calibrated=True, insufficient_context=True)
    assert r.confidence_band == "LOW" and r.insufficient_context
    g = to_result(_P(general_complaint=0.2, other=0.18, apps_services=0.17, battery_power=0.15), method="embed_lr", calibrated=True)
    assert g.taxonomy_gap and g.intent == "general_complaint"


def test_intent_result_schema_has_no_hidden_reasoning_fields():
    fields = set(IntentResult.model_fields)
    assert {"intent", "confidence", "top3", "confidence_band", "calibrated", "secondary_intents", "multi_intent", "insufficient_context", "taxonomy_gap"} <= fields
    assert not {"reasoning", "chain_of_thought", "rationale"} & fields


def test_temperature_scaling_and_artifact_roundtrip(tmp_path):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 8)).astype("float32")
    y = [INTENT_NAMES[int(i)] for i in (X[:, 0] > 0).astype(int) + 2 * (X[:, 1] > 0).astype(int)]  # 4 classes
    m = EmbedLR(C=1.0).fit(None, y, X=X)
    P = m.predict_proba(X=X)
    assert P.shape == (300, len(INTENT_NAMES)) and np.allclose(P.sum(axis=1), 1)
    cal = m.calibrate(None, y, X=X)
    assert cal["temperature"] in cal["grid"] and softmax(np.zeros((1, 3)), 2.0).sum() == pytest.approx(1)
    p = tmp_path / "m.json"
    m.save(p)
    m2 = EmbedLR.load(p)
    assert np.allclose(m2.predict_proba(X=X), m.predict_proba(X=X)) and m2.temperature == m.temperature


# ------------------------------------------------------------------ query constructor --------------------------------
def _intent(name, conf, band_, secondary=(), insufficient=False):
    return IntentResult(intent=name, confidence=conf, confidence_band=band_, secondary_intents=list(secondary), multi_intent=bool(secondary), insufficient_context=insufficient)


def test_query_construction_short_reply_with_context_and_intent():
    ctx = parse_context("customer: iPhone keeps restarting\nbrand: Did you update iOS?")
    b = build_context("yes", ctx)
    q = build_query(b, _intent("performance_crash", 0.9, "HIGH"))
    assert q.text.startswith("iPhone keeps restarting yes") and "crashes" in q.text.lower() and CANONICAL["performance_crash"].split()[0] in q.text.lower()
    assert q.boost == "strong" and q.allowed_intents == ("performance_crash",) and not q.ambiguous


def test_query_low_confidence_never_filters_and_marks_ambiguity():
    b = build_context("something is wrong with my phone", None)
    q = build_query(b, _intent("general_complaint", 0.3, "LOW"))
    assert q.boost == "none" and q.allowed_intents == () and q.ambiguous and q.text == "something is wrong with my phone"
    qm = build_query(b, _intent("battery_power", 0.6, "MEDIUM", secondary=["performance_crash"]))
    assert qm.boost == "mild" and qm.allowed_intents == ("battery_power", "performance_crash") and qm.ambiguous


def test_query_dedupes_tokens_and_skips_phrase_for_long_messages():
    b = build_context("battery battery drains drains fast fast " + " ".join(f"w{i}" for i in range(15)), None)
    q = build_query(b, _intent("battery_power", 0.95, "HIGH"))
    assert q.text.split()[:3] == ["battery", "drains", "fast"] and "not charging" not in q.text   # 18 distinct tokens: no phrase appended


def test_insufficient_context_query_has_no_intent():
    q = build_query(build_context("ok", None), _intent("other", 0.9, "HIGH", insufficient=True))
    assert q.intent_hint is None and q.ambiguous and q.boost == "none"


# ------------------------------------------------------------------ retrieval integration ---------------------------
def test_intent_boost_fuses_without_discarding():
    plain = [1, 2, 3, 4, 5]
    filtered = [4, 5]
    fused = [d for d, _, _ in rrf({"plain": plain, "intent": filtered}, k=20)]
    assert set(fused) == set(plain) and fused[0] in (4, 1)  # nothing discarded; boosted docs move up


@pytest.mark.skipif(not (__import__("resolveai").config.PROCESSED_DIR / "silver_train.csv").exists(), reason="silver labels not built")
def test_silver_and_dev_are_isolated_from_golden():
    import pandas as pd

    from resolveai import config
    from resolveai.evaluation import load_golden

    g = set(load_golden().customer_tweet_id.astype(int))
    for f in ("silver_train.csv", "silver_dev.csv"):
        ids = set(pd.read_csv(config.PROCESSED_DIR / f, usecols=["customer_tweet_id"]).customer_tweet_id)
        assert not ids & g
