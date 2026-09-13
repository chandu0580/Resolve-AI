"""Read-only views for the operator console's Evaluation, Agents and Knowledge surfaces.

Nothing here runs the agent, calls a model or recomputes a metric:
- release_view: serves the frozen release artifacts (artifacts/final) as stored, grouped by dataset. Frozen golden set, dev
  experiments and verification checks are kept apart and never combined. Example message text is PII-redacted and truncated.
- agent_profile: the ACTIVE configuration of the loaded agent (retrieval, evidence gate, rerank weights, second opinion,
  ordered policy rules) next to the configuration the release was EVALUATED with, with the differences listed.
- knowledge_summary: aggregates over the knowledge-base rows (counts, shares, date range). No customer or reply text.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from resolveai import config
from resolveai.api.errors import ApiError
from resolveai.trust.pii import redact_pii

# resolveai.policy and resolveai.retrieval are imported inside the functions that need them: imported on their own (before
# resolveai.agent has loaded) they form an import cycle through resolveai.intelligence.

FINAL_DIR = config.ROOT / "artifacts" / "final"
PRODUCT_DIR = config.ROOT / "artifacts" / "product"
RELEASE_META = FINAL_DIR / "evaluation" / "runs" / "final_release.meta.json"
TEXT_KEYS = {"message", "text", "customer_message", "release_response", "judge_note_release"}
MAX_TEXT = 240

ALLOWED_ACTIONS = [
    {"action": "AUTO_HANDLE", "label": "Auto-handled", "response_kinds": ["auto_reply", "template_reply"],
     "requires": "Sufficient or strong evidence, no risk flags, a policy rule that allows autonomy, a verified draft and every output-gate check passing (or a fixed template)."},
    {"action": "CLARIFICATION_REQUIRED", "label": "Clarification", "response_kinds": ["clarifying_question"],
     "requires": "A policy rule that allows clarification: the issue is unstated, confidence is low, or the evidence gap is clarifiable and nothing is high-impact."},
    {"action": "HUMAN_HANDOFF", "label": "Human handoff", "response_kinds": ["handoff_notice"],
     "requires": "Any hard-block risk, sensitive or private action, repeated contact, conflicting or insufficient evidence that cannot be clarified, a failed verification or an unavailable model."},
]
NOT_ALLOWED = ["Refunds, orders, account changes or any other action on a customer account", "Sending a message to a real channel (every response is returned to the caller, not sent)",
               "Replying without evidence that passed the evidence gate", "Letting the model decide escalation (the policy is deterministic)"]
RELEASE_LIMITATIONS = [
    "The golden set is 197 annotated tweets from one 2017 AppleSupport burst; per-intent counts are small and the intervals are wide.",
    "Second annotator labels came from an AI annotator, not a person; the 50-row human rating packet has 0 completed ratings.",
    "Groundedness and hallucination scores come from an LLM judge, not from people.",
    "Confidence intervals are bootstrap intervals (1,000 resamples, seed 42) over one run; the golden set was run once and never tuned on.",
    "Latency was measured on a single shared local CPU process with the model behind a remote proxy; cost uses list prices, not real billing.",
]


def _read(path: Path) -> dict | list | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _safe_text(v: str) -> str:
    t = redact_pii(v).text
    return t if len(t) <= MAX_TEXT else t[: MAX_TEXT - 1] + "…"


def _sanitize(obj, key: str | None = None):
    """Redact and truncate free text; structure and numbers are served unchanged."""
    if isinstance(obj, dict):
        return {k: _sanitize(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v, key) for v in obj]
    if isinstance(obj, str) and key in TEXT_KEYS:
        return _safe_text(obj)
    return obj


def _pick(d: dict | None, keys: tuple[str, ...]) -> dict | None:
    return None if d is None else {k: d[k] for k in keys if k in d}


def release_view() -> dict:
    metrics = _read(FINAL_DIR / "final_metrics.json")
    if metrics is None:
        raise ApiError(404, "evaluation_not_available", "Release evaluation artifacts are missing (artifacts/final/final_metrics.json).")
    meta = _read(RELEASE_META) or {}
    failure = _read(FINAL_DIR / "failure_modes.json")
    attribution = _read(FINAL_DIR / "evaluation" / "judge_attribution.json")
    perf = _read(FINAL_DIR / "performance" / "perf_final.json")
    risk_report = _read(FINAL_DIR / "risk_experiment" / "report.json")
    risk_decision = _read(FINAL_DIR / "risk_experiment" / "decision.json")
    adversarial, smoke, verification, clean = (_read(FINAL_DIR / f) for f in ("adversarial_suite.json", "api_smoke.json", "verification.json", "clean_env_check.json"))
    profile_keys = ("n", "total_ms", "stages_ms", "mean_llm_calls", "live_calls_total", "cache_hit_rate", "cost_usd_per_request", "timeouts", "retries",
                    "budget_exhausted", "model_drafted_and_verified", "actions")
    return {
        "golden": {
            "dataset": "FROZEN GOLDEN SET",
            "release": {"version": "1.0.0", "pipeline_version": meta.get("pipeline_version"), "config_hash": meta.get("config_hash"), "run_at": meta.get("run_at"),
                        "n": metrics.get("n_golden"), "golden_sha256": metrics.get("golden_sha256"), "n_boot": metrics.get("n_boot"), "seed": metrics.get("seed"),
                        "failed_rows": meta.get("failed"), "model_calls": meta.get("model_calls")},
            "table": metrics.get("table"),
            "evidence_levels": metrics.get("evidence_levels"),
            "autonomous_replies": metrics.get("autonomous_replies"),
            "missed_escalations": _sanitize(metrics.get("missed_escalations")),
            "retrieval_same_resolution_recall_at_5": metrics.get("retrieval_same_resolution_recall_at_5"),
            "decision_changes_vs_phase9_final": metrics.get("decision_changes_vs_phase9_final"),
            "human_evaluation": metrics.get("human_evaluation"),
            "failure_modes": _sanitize(failure),
            "judge_attribution": None if attribution is None else {k: v for k, v in attribution.items() if k != "changed_rows"},
            "by_intent": _sanitize(_read(PRODUCT_DIR / "release_by_intent.json")),
        },
        "dev_experiments": {
            "dataset": "DEV EXPERIMENTS",
            "risk_corroboration": None if risk_decision is None else {
                "decision": risk_decision,
                "report": _pick(risk_report, ("n_dev_rows", "n_labelled_rows", "labels_provenance", "live_model_calls", "status", "model", "outcomes_240", "scores_on_labelled_rows"))},
        },
        "performance": None if perf is None else {
            "dataset": "PERFORMANCE PROFILE (dev pool, not golden)",
            "protocol": perf.get("protocol"), "machine_note": perf.get("machine_note"), "price_per_million_tokens_usd": perf.get("price_per_million_tokens_usd"),
            "live_draft_selection": perf.get("live_draft_selection"),
            "profiles": {name: _pick(perf.get(name), profile_keys) for name in ("no_model", "cached_model", "live_random", "live_draft") if perf.get(name)},
        },
        "checks": {
            "adversarial_suite": _pick(adversarial, ("n_cases", "passed", "failed", "model")),
            "api_smoke": _pick(smoke, ("profile", "n_checks", "passed", "failed")),
            "verification": None if verification is None else {
                "passed": verification.get("passed"), "started": verification.get("started"), "golden": verification.get("golden"),
                "frozen_artifacts": {k: (len(v) if isinstance(v, list) else v) for k, v in (verification.get("frozen_artifacts") or {}).items()},
                "security_scan": {k: v for k, v in (verification.get("security_scan") or {}).items() if not isinstance(v, (list, dict))}},
            "clean_environment": _pick(clean, ("mode", "passed", "failed_steps", "os")),
        },
        "limitations": RELEASE_LIMITATIONS,
        "provenance": {"source": "artifacts/final (release 1.0.0) and artifacts/product/release_by_intent.json; served as stored, nothing recomputed",
                       "text": "example messages are PII-redacted and truncated before they are served"},
    }


def _jsonable(obj):
    return json.loads(json.dumps(obj, default=lambda o: asdict(o) if hasattr(o, "__dataclass_fields__") else list(o) if isinstance(o, (tuple, set)) else str(o)))


def agent_profile(service) -> dict:
    from resolveai.policy import escalation

    agent = service.agent   # 503 while loading or after a failed load
    active = _jsonable(asdict(agent.cfg))
    meta = _read(RELEASE_META) or {}
    evaluated = meta.get("agent_config")
    differences = []
    if evaluated:
        for k in sorted(set(active) | set(evaluated)):
            if active.get(k) != evaluated.get(k):
                differences.append({"field": k, "active": active.get(k), "evaluated": evaluated.get(k),
                                    "note": "traces are written by the API; the evaluation run does not write traces" if k == "write_traces" else None})
    evaluated_pipeline = meta.get("pipeline_version")
    if evaluated_pipeline and evaluated_pipeline != agent.versions.pipeline:
        impact = _read(PRODUCT_DIR / "hardening" / "behaviour_change_impact.json") or {}
        touched = f" {impact['n_rows_touching_any_change']} of {impact['golden_rows']} golden rows reach a changed code path (behaviour_change_impact.json)." if impact else ""
        differences.append({"field": "pipeline_version", "active": agent.versions.pipeline, "evaluated": evaluated_pipeline,
                            "note": "live behaviour changed after the release evaluation (greetings, requests for a person, short replies, capitalization); "
                                    f"the golden run was not repeated, so evaluation numbers describe the evaluated pipeline.{touched}"})
    r = agent.retriever
    llm = getattr(agent, "llm", None)
    return {
        "agent": {"name": "ResolveAI", "state": service.state, "brand": config.BRAND, "versions": agent.versions.model_dump(),
                  "model": {"configured": llm is not None, "enabled": service.settings.use_llm, "name": getattr(llm, "model", None) if llm is not None else None,
                            "role": "proposes intent second opinions, risk flags, drafts and verification verdicts; never decides escalation"}},
        "active": {
            "label": "ACTIVE CONFIGURATION",
            "agent_config": active,
            "retrieval": {**_jsonable(asdict(r.cfg)), "embedding_model": config.EMBED_MODEL},
            "evidence_gate": _jsonable(asdict(r.gate_v3)),
            "rerank_weights": _jsonable(asdict(r.weights)),
            "second_opinion_policy": agent.policy,
            "request_budget_s": service.settings.request_budget_s,
        },
        "evaluated": {"label": "EVALUATION CONFIGURATION", "source": "artifacts/final/evaluation/runs/final_release.meta.json", "agent_config": evaluated,
                      "pipeline_version": meta.get("pipeline_version"), "config_hash": meta.get("config_hash"), "differences": differences},
        "policy": {"version": escalation.POLICY_VERSION, "confidence_floor": escalation.CONFIDENCE_FLOOR, "always_handoff_intents": sorted(escalation.ALWAYS_ESCALATE_INTENTS),
                   "brand_turns_without_progress": escalation.BRAND_TURNS_WITHOUT_PROGRESS, "clarifiable_evidence_reasons": sorted(escalation.CLARIFIABLE_EVIDENCE_REASONS),
                   "rules": escalation.POLICY_RULES, "order": "first matching rule wins"},
        "allowed_actions": ALLOWED_ACTIONS,
        "not_allowed": NOT_ALLOWED,
    }


def knowledge_summary(service) -> dict:
    from resolveai.retrieval.resolution import is_resolution_bearing

    cached = getattr(service, "_knowledge_summary", None)
    if cached is not None:
        return cached
    agent = service.agent
    rows = agent.kb.rows
    n = int(len(rows))
    resolution = rows.brand_reply.map(is_resolution_bearing) if n else rows.brand_reply
    substantive = rows.substantive if "substantive" in rows else None
    dm = rows.dm_handoff if "dm_handoff" in rows else None
    by_intent = []
    if n and "weak_intent" in rows:
        for intent, g in rows.assign(_res=resolution).groupby("weak_intent"):
            by_intent.append({"intent": str(intent), "rows": int(len(g)), "resolution_bearing": int(g._res.sum()),
                              "resolution_bearing_share": round(float(g._res.mean()), 3), "dm_handoff_share": round(float(g.dm_handoff.mean()), 3) if dm is not None else None})
        by_intent.sort(key=lambda x: -x["rows"])
    created = rows.created_at.astype(str) if n else rows.created_at
    body = {
        "dataset": "KNOWLEDGE BASE",
        "rows": n,
        "substantive": int(substantive.sum()) if substantive is not None else None,
        "dm_handoff": int(dm.sum()) if dm is not None else None,
        "resolution_bearing": int(resolution.sum()) if n else 0,
        "resolution_bearing_substantive": int((resolution & substantive).sum()) if n and substantive is not None else None,
        "date_range": {"min": created.min() if n else None, "max": created.max() if n else None},
        "by_weak_intent": by_intent,
        "reply_action_classes": dict(Counter(map(str, rows.action_class)).most_common()) if n and "action_class" in rows else {},
        "outcome_signals": dict(Counter(map(str, rows.outcome)).most_common()) if n and "outcome" in rows else {},
        "manifest": {k: agent.kb.manifest.get(k) for k in ("corpus_hash", "preprocessing_version", "kb_max_created_at", "holdout_min_created_at", "min_reply_chars", "substantive_chars")},
        "indexes": {"dense": sorted(getattr(agent.kb, "dense", {}).keys()), "embedding_model": config.EMBED_MODEL, "search_path": list(agent.retriever.cfg.paths)},
        "definitions": {
            "resolution_bearing": "a non-question sentence in the brand reply states an instruction or a released fix (resolveai.retrieval.resolution.is_resolution_bearing)",
            "substantive": f"not a move-to-DM reply and at least {agent.kb.manifest.get('substantive_chars')} characters",
            "dm_handoff": "the brand reply only moves the customer to a private channel",
            "weak_intent": "keyword intent of the historical customer message (weak label, not the production classifier)",
            "outcome_signals": "weak regex signal from the customer's follow-up; a bonus signal, never a label",
        },
        "source": "knowledge-base rows loaded by the running agent (kb temporal split only; every golden example is later)",
    }
    service._knowledge_summary = body
    return body
