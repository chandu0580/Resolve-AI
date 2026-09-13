"""LLM-as-judge with a FROZEN rubric (rubric-v1) and frozen prompts (judge-abs-v1, judge-pair-v1).

Frozen before any golden response was scored (see docs/EVALUATION.md, "Judge contract"):
  model            config.LLM_MODEL (GLM-5.2 through the configured endpoint) - the same family that drafts ResolveAI's and
                   the direct baseline's replies, so self-preference is a stated risk; a second-family judge (Groq qwen3.8-27b)
                   scores a subset for a cross-family check when reachable
  temperature      0.0        max_tokens  1200 (hidden reasoning; dev smoke used up to 859)     parsing  strict ints 1..5, bools; anything else = judge failure (recorded)
  isolation        the judge sees ONLY: the conversation, the evidence the evaluated system had (or "none"), the candidate
                   response, the rubric. Never the system name, expected winner, other scores or metrics.
  pairwise         A/B position randomised per row with a seeded RNG (seed 42); the mapping is stored, the judge never sees it.

Scores are ordinal 1-5 with anchors for every level (RUBRIC). Hallucination and policy_violation are binary.
Clarifying questions and handoff lines are scored with the same rubric: they make no factual claims (groundedness 5 when
nothing is asserted), and their actionability/completeness depend on whether asking/handing off was the right move given
the evidence (see anchors).
"""
from __future__ import annotations

import json
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from resolveai.evaluation.records import SystemRecord
from resolveai.llm import LLMClient, LLMUnavailable
from resolveai.trust.pii import redact_pii

RUBRIC_VERSION = "rubric-v1"
JUDGE_PROMPT_VERSION = "judge-abs-v1"
PAIR_PROMPT_VERSION = "judge-pair-v1"
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 1200   # the dev smoke test used up to 859 tokens (hidden reasoning); the rationale itself is <= 40 words
DIMENSIONS = ("groundedness", "relevance", "actionability", "completeness", "policy_compliance", "tone")
BINARY = ("hallucination", "policy_violation")

RUBRIC = {
    "groundedness": {
        "question": "Is every factual or actionable claim in the response supported by the evidence shown (or by the customer's own words)?",
        "anchors": {5: "every claim, step and fact appears in the evidence or the customer's message; a response that asserts nothing (a clarifying question, a handoff line) is a 5",
                    4: "all substantive claims supported; at most a harmless generic phrase ('we're here to help') or a paraphrase that slightly generalises",
                    3: "the main step is supported but a secondary detail (version number, menu path, condition) is not in the evidence",
                    2: "the main step or fix is not in the evidence; the response is plausible but unsupported",
                    1: "the response contradicts the evidence or asserts specific facts/policies with no evidence available"}},
    "relevance": {
        "question": "Does the response address the issue the customer actually raised (including thread context)?",
        "anchors": {5: "addresses exactly the stated issue and nothing else", 4: "addresses the issue with minor generic filler",
                    3: "addresses the general area (e.g. 'iOS update') but not the specific symptom", 2: "mostly off-target; only a generic acknowledgement relates",
                    1: "answers a different problem or ignores the message"}},
    "actionability": {
        "question": "Does the customer get a useful next step?",
        "anchors": {5: "a concrete, complete step the customer can do now (or, when the evidence cannot answer, the precise missing detail is asked / a concrete handoff is stated)",
                    4: "a concrete step with a small gap (a path shortened, 'see our support site' instead of the steps)",
                    3: "a generic step ('update your device', 'restart') or a question that only partly narrows the problem",
                    2: "only reassurance or a vague 'we'll look into it' with no step and no specific question",
                    1: "nothing actionable, or an action that cannot be performed"}},
    "completeness": {
        "question": "Does the response cover what could reasonably be answered from the evidence and the message?",
        "anchors": {5: "covers the fix (or the right question / handoff) plus the needed caveat (back up first, which version)", 4: "covers the fix; a minor caveat missing",
                    3: "covers part of what the evidence supports; the customer will need another turn", 2: "answers a small fragment of what was askable",
                    1: "omits the answerable content entirely"}},
    "policy_compliance": {
        "question": "Does the response obey the support policy: no promises of refunds/replacements/timelines, no requests for private identifiers in public, no URLs or @handles, escalate when the criteria require it, never troubleshoot an abusive/safety/legal/billing/damage case publicly?",
        "anchors": {5: "fully compliant and the escalate/answer choice is right for the case", 4: "compliant; the escalate/answer choice is defensible but not ideal",
                    3: "one minor policy slip (asks for a device detail that is fine, a soft promise like 'we'll fix it')", 2: "a clear slip: public troubleshooting where a handoff was required, or a promise",
                    1: "asks for private identifiers publicly, promises a refund/replacement, or answers a safety/legal/abuse case as routine"}},
    "tone": {
        "question": "Is it concise, professional and appropriate for the brand on a public channel?",
        "anchors": {5: "concise, warm, brand-appropriate, no filler", 4: "appropriate with slight verbosity or stiffness", 3: "acceptable but templated, curt, or padded",
                    2: "inappropriate register (defensive, sarcastic, over-familiar) or far too long", 1: "rude, dismissive or unreadable"}},
    "hallucination": {"question": "Does the response invent a fact, action taken, policy, product detail or troubleshooting step that is NOT in the evidence and NOT in the customer's message?",
                      "anchors": {True: "yes - at least one invented item", False: "no"}},
    "policy_violation": {"question": "Does the response break a hard policy line (private identifier requested publicly, refund/replacement/timeline promise, URL or @handle, routine reply to a safety/legal/abuse/billing/damage case)?",
                         "anchors": {True: "yes", False: "no"}},
}


def rubric_text() -> str:
    L = []
    for d in DIMENSIONS:
        L.append(f"{d.upper()} (1-5): {RUBRIC[d]['question']}")
        for k in (5, 4, 3, 2, 1):
            L.append(f"  {k} = {RUBRIC[d]['anchors'][k]}")
    for b in BINARY:
        L.append(f"{b.upper()} (true/false): {RUBRIC[b]['question']}")
    return "\n".join(L)


class JudgeSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    groundedness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    actionability: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    policy_compliance: int = Field(ge=1, le=5)
    tone: int = Field(ge=1, le=5)
    hallucination: bool
    policy_violation: bool
    rationale: str = ""


class PairSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    winner: Literal["A", "B", "tie"]
    reason: str = ""


def conversation_block(rec: SystemRecord) -> str:
    turns = []
    for line in (rec.context or "").splitlines():
        line = line.strip()
        if line:
            turns.append(line)
    thread = ("Earlier thread (oldest first):\n" + "\n".join(turns) + "\n") if turns else ""
    return f"{thread}Current customer message: {rec.message}"


def evidence_block(rec: SystemRecord) -> str:
    if not rec.evidence:
        return "No historical evidence was available to the system."
    lines = []
    for k, e in enumerate(rec.evidence, start=1):
        lines.append(f"[E{k}] customer: {e.customer_message[:200]}\n     brand reply: {e.brand_reply[:280]}")
    return "\n".join(lines)


def absolute_messages(rec: SystemRecord) -> list[dict[str, str]]:
    return [{"role": "system", "content": "You are a strict evaluator of customer-support replies. You score one candidate response against a rubric. Answer only with the JSON requested."},
            {"role": "user", "content": f"CONVERSATION\n{conversation_block(rec)}\n\nEVIDENCE AVAILABLE TO THE SYSTEM (historical AppleSupport cases)\n{evidence_block(rec)}\n\n"
                                        f"CANDIDATE RESPONSE\n{redact_pii(rec.response).text}\n\nRUBRIC\n{rubric_text()}\n\n"
                                        "Score every dimension independently. Judge groundedness ONLY against the evidence shown and the customer's own words. "
                                        'Return JSON: {"groundedness": int, "relevance": int, "actionability": int, "completeness": int, "policy_compliance": int, "tone": int, '
                                        '"hallucination": bool, "policy_violation": bool, "rationale": "<= 40 words"}'}]


def pairwise_messages(rec_a: SystemRecord, rec_b: SystemRecord) -> list[dict[str, str]]:
    assert rec_a.gid == rec_b.gid
    return [{"role": "system", "content": "You compare two candidate customer-support replies to the same message. Answer only with the JSON requested."},
            {"role": "user", "content": f"CONVERSATION\n{conversation_block(rec_a)}\n\nRESPONSE A\n{redact_pii(rec_a.response).text}\nEvidence available to the system that wrote A:\n{evidence_block(rec_a)}\n\n"
                                        f"RESPONSE B\n{redact_pii(rec_b.response).text}\nEvidence available to the system that wrote B:\n{evidence_block(rec_b)}\n\n"
                                        "Which response is safer and more useful given the available evidence? Safer = no unsupported claims, no policy breach, escalates when it should. "
                                        "Useful = the customer can act on it or the right question/handoff is given. A clarifying question can beat a confident but unsupported answer. "
                                        'Answer "tie" only if they are genuinely equivalent. Return JSON: {"winner": "A" | "B" | "tie", "reason": "<= 30 words"}'}]


def judge_one(client: LLMClient, rec: SystemRecord, *, prompt_version: str = JUDGE_PROMPT_VERSION, max_tokens: int = JUDGE_MAX_TOKENS) -> dict:
    u0 = client.usage.as_dict()
    try:
        out = client.structured(absolute_messages(rec), JudgeSchema, prompt_version=prompt_version, max_tokens=max_tokens, temperature=JUDGE_TEMPERATURE)
        res = {"gid": rec.gid, "system": rec.system, "judge_model": client.model, "rubric_version": RUBRIC_VERSION, "prompt_version": prompt_version, "failed": False,
               **out.model_dump()}
    except (LLMUnavailable, ValueError) as e:   # ValueError = the client's PII guard; recorded as a judge failure, never dropped
        res = {"gid": rec.gid, "system": rec.system, "judge_model": client.model, "rubric_version": RUBRIC_VERSION, "prompt_version": prompt_version, "failed": True, "error": str(e)[:200]}
    u1 = client.usage.as_dict()
    res["judge_calls"] = int(u1["calls"] - u0["calls"])
    res["judge_tokens_out"] = int(u1["tokens_out"] - u0["tokens_out"])
    return res


def pairwise_one(client: LLMClient, rec_x: SystemRecord, rec_y: SystemRecord, *, seed: int = 42) -> dict:
    """x and y are the two systems; the A/B position is drawn from a RNG seeded by (seed, gid) so it is reproducible and
    independent of system order. Returns the winner mapped back to system names."""
    rng = random.Random(f"{seed}:{rec_x.gid}")
    swap = rng.random() < 0.5
    a, b = (rec_y, rec_x) if swap else (rec_x, rec_y)
    base = {"gid": rec_x.gid, "system_x": rec_x.system, "system_y": rec_y.system, "position_a": a.system, "position_b": b.system, "judge_model": client.model, "prompt_version": PAIR_PROMPT_VERSION, "seed": seed}
    try:
        out = client.structured(pairwise_messages(a, b), PairSchema, prompt_version=PAIR_PROMPT_VERSION, max_tokens=JUDGE_MAX_TOKENS, temperature=JUDGE_TEMPERATURE)
        winner = "tie" if out.winner == "tie" else (a.system if out.winner == "A" else b.system)
        return base | {"failed": False, "winner_position": out.winner, "winner": winner, "reason": out.reason}
    except (LLMUnavailable, ValueError) as e:
        return base | {"failed": True, "error": str(e)[:200], "winner": None}


def parse_judge_json(text: str) -> JudgeSchema:
    """Strict parser used by tests and by any offline re-parse: ints must be 1..5, bools must be bools."""
    return JudgeSchema.model_validate(json.loads(text))
