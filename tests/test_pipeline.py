"""End-to-end pre-generation pipeline test on the real KB and frozen classifier artifact (skipped if either is missing).
Uses cached embeddings; no network."""
import pytest

from resolveai import config
from resolveai.intelligence.classifier import ARTIFACT
from resolveai.schemas import ConversationContext, ConversationTurn

pytestmark = pytest.mark.skipif(not ARTIFACT.exists() or not (config.PROCESSED_DIR / "apple_pairs.csv").exists(), reason="artifact or subsample missing")


@pytest.fixture(scope="module")
def pipe():
    from resolveai.intelligence.pipeline import PreGenerationPipeline

    return PreGenerationPipeline()


def test_understand_returns_full_contract_and_latency(pipe):
    pipe.understand("warm-up call loads the embedding model")
    u = pipe.understand("my battery drains from 100 to 40 percent in an hour since the iOS 11 update")
    assert u.intent.intent in {"battery_power", "performance_crash"} and u.intent.calibrated and u.intent.confidence_band in {"HIGH", "MEDIUM", "LOW"}
    assert u.plan.text and u.evidence.retriever.startswith("dense:bge-small") and len(u.evidence.items) <= 5
    assert set(u.latency_ms) == {"context_ms", "classify_ms", "query_ms", "retrieve_ms"} and u.total_ms < 2000   # warm call; cold start loads BGE (~7-17 s)
    assert u.evidence.sufficiency_reason in {"strong_consistent_evidence", "weak_similarity", "insufficient_resolution_evidence", "conflicting_evidence", "ambiguous_intent", "no_relevant_evidence", "customer_history_risk", "insufficient_query", "mixed_resolution", "weak_resolution_evidence"}


def test_short_reply_with_context_builds_query_from_issue(pipe):
    ctx = ConversationContext(turns=[ConversationTurn(role="customer", text="iPhone keeps restarting every 30 seconds"), ConversationTurn(role="brand", text="Did you update iOS?")])
    u = pipe.understand("yes", ctx)
    assert u.bundle.is_short_reply and not u.bundle.insufficient_context and u.plan.text.startswith("iPhone keeps restarting")


def test_degenerate_message_is_flagged_not_hallucinated(pipe):
    u = pipe.understand("<url>")
    assert u.bundle.insufficient_context and u.intent.confidence_band == "LOW" and u.intent.insufficient_context
    assert u.evidence.sufficiency_reason == "insufficient_query" and not u.evidence.sufficient and u.plan.boost == "none"


def test_low_confidence_never_filters_evidence(pipe):
    u = pipe.understand("something is wrong")
    assert u.plan.boost in {"none", "mild", "strong"}
    assert u.evidence.n_retrieved >= len(u.evidence.items)   # boosting reorders, never discards


def test_pipeline_refuses_unredacted_pii(pipe):
    with pytest.raises(ValueError):
        pipe.understand("call me at 415-555-0134 my battery is dead")
