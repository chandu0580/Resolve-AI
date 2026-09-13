"""Grounded-response verifier: deterministic lexical checks always; GLM-5.2 support check for troubleshooting drafts.
A response with any BLOCKING issue is never sent. Returns schemas.VerificationResult."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from resolveai.intelligence.classifier import CANONICAL_TERMS
from resolveai.llm import LLMClient, LLMUnavailable
from resolveai.schemas.core import DraftResponse, EvidenceSet, IntentResult, VerificationIssue, VerificationResult
from resolveai.trust.pii import contains_unredacted_pii

VERIFY_PROMPT_VERSION = "verify-v2"   # v2 (Phase 5): the drafter replaces evidence links with "the steps on our support site"; the judge is told this is allowed
FORBIDDEN = re.compile(r"\b(refund|replace(ment)? (for free|at no cost)|we will (fix|replace|refund)|guarantee|compensat|within \d+ (hours|days)|free (repair|replacement))\b", re.I)
INTERNAL = re.compile(r"\b(evidence|retriev(al|ed)|classifier|confidence (score|band)|policy|trace|intent|embedding|model output|dataset|knowledge base|similar(ity)? score)\b", re.I)
PLACEHOLDER = re.compile(r"<(EMAIL|PHONE|ORDER_ID|CARD|LONG_ID|url)>", re.I)
MIN_COVERAGE = 0.25
_WORD = re.compile(r"[a-z]{5,}")
_STOP = {"please", "thanks", "thank", "there", "would", "could", "should", "about", "which", "where", "their", "these", "those", "iphone", "apple", "phone", "device"}


class SupportSchema(BaseModel):
    supported: bool = Field(description="every concrete instruction or claim in the reply appears in the evidence")
    unsupported_claims: list[str] = Field(default_factory=list)
    invented_steps: bool = False
    off_topic: bool = False


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def lexical_checks(draft: DraftResponse, evidence: EvidenceSet, intent: IntentResult) -> tuple[list[VerificationIssue], float, list[str]]:
    issues: list[VerificationIssue] = []
    t = draft.text
    if not (20 <= len(t) <= 280):
        issues.append(VerificationIssue(check="length", severity="blocking", detail=f"{len(t)} chars"))
    if "http" in t.lower() or "t.co/" in t.lower():
        issues.append(VerificationIssue(check="no_url", severity="blocking", detail="contains a URL"))
    if "@" in t:
        issues.append(VerificationIssue(check="no_handle", severity="blocking", detail="contains an @handle"))
    if FORBIDDEN.search(t):
        issues.append(VerificationIssue(check="no_promise", severity="blocking", detail=FORBIDDEN.search(t).group(0)))
    if INTERNAL.search(t):
        issues.append(VerificationIssue(check="no_internal_metadata", severity="blocking", detail=INTERNAL.search(t).group(0)))
    if contains_unredacted_pii(t) or PLACEHOLDER.search(t):
        issues.append(VerificationIssue(check="no_pii", severity="blocking", detail="PII or redaction placeholder in reply"))
    by_id = {it.evidence_id: it for it in evidence.items}
    refs = [r for r in draft.evidence_ids if r in by_id]
    if draft.strategy.value == "troubleshoot":
        if not refs:
            issues.append(VerificationIssue(check="evidence_refs", severity="blocking", detail="no valid evidence references"))
        cited = " ".join(by_id[r].brand_reply for r in refs)
        rw = _words(t)
        coverage = (len(rw & _words(cited)) / len(rw)) if rw else 0.0
        if refs and coverage < MIN_COVERAGE:
            issues.append(VerificationIssue(check="evidence_coverage", severity="blocking", detail=f"coverage {coverage:.2f} < {MIN_COVERAGE}"))
        own = CANONICAL_TERMS.get(intent.intent, set())
        foreign = {w for k, ws in CANONICAL_TERMS.items() if k != intent.intent for w in ws} - own
        hits = foreign & set(re.findall(r"[a-z]+", t.lower()))
        if len(hits) >= 2 and not (own & set(re.findall(r"[a-z]+", t.lower()))):
            issues.append(VerificationIssue(check="intent_consistency", severity="warning", detail=f"reply terms {sorted(hits)[:4]} belong to other intents"))
    else:
        coverage = 1.0
    return issues, round(coverage, 3), refs


def verify(client: LLMClient | None, draft: DraftResponse, evidence: EvidenceSet, intent: IntentResult, *, use_llm: bool = True) -> VerificationResult:
    issues, coverage, refs = lexical_checks(draft, evidence, intent)
    method = "lexical"
    if draft.strategy.value == "troubleshoot" and not any(i.severity == "blocking" for i in issues) and use_llm:
        if client is None:
            issues.append(VerificationIssue(check="llm_support_check", severity="blocking", detail="verifier model unavailable; cannot confirm support"))
        else:
            by_id = {it.evidence_id: it for it in evidence.items}
            cited = "\n".join(f"- {by_id[r].brand_reply}" for r in refs)
            msgs = [{"role": "system", "content": "You audit whether a support reply is fully supported by the evidence. Answer only with JSON."},
                    {"role": "user", "content": f"Reply:\n{draft.text}\n\nEvidence replies it must be supported by:\n{cited}\n\nIs every concrete instruction, fact or claim in the reply present in the evidence? "
                                                f"Asking the customer for a detail (device, version) is allowed. Referring to 'the steps on our support site' in place of a link that appears in the evidence is allowed. Return JSON: {{\"supported\": bool, \"unsupported_claims\": [str], \"invented_steps\": bool, \"off_topic\": bool}}"}]
            try:
                out = client.structured(msgs, SupportSchema, prompt_version=VERIFY_PROMPT_VERSION, max_tokens=800)
                method = "lexical+llm"
                if not out.supported or out.invented_steps:
                    issues.append(VerificationIssue(check="llm_support_check", severity="blocking", detail="; ".join(out.unsupported_claims)[:300] or "invented steps"))
                if out.off_topic:
                    issues.append(VerificationIssue(check="llm_off_topic", severity="blocking", detail="reply does not address the customer's issue"))
            except LLMUnavailable as e:
                issues.append(VerificationIssue(check="llm_support_check", severity="blocking", detail=f"verifier unavailable: {str(e)[:120]}"))
    blocking = any(i.severity == "blocking" for i in issues)
    sev = "blocking" if blocking else "warning" if any(i.severity == "warning" for i in issues) else "info" if issues else "none"
    return VerificationResult(verified=not blocking, issues=issues, severity=sev, evidence_refs=refs, coverage=coverage, method=method, attempts=draft.attempts)
