"""Resolution intelligence (Phase 5): resolution-centred reranking, resolution clusters, evidence consistency,
resolution confidence, and the four-state sufficiency gate (gate-v3).

Vocabulary
- GENERAL relevance: the historical CUSTOMER message resembles the query (cos_customer).
- RESOLUTION relevance: the historical BRAND REPLY prescribes a concrete resolution (action class in RESOLUTION_ACTIONS,
  substantive, not a handoff) and resembles what resolved similar issues (cos_reply / cos_pair).
- Clusters are action classes (see cluster_resolutions).
- The outcome regex stays a weak, bounded bonus (hand-checked precision 0.72), never a label.

Reranker score (all terms in [0,1]; weights documented in RerankWeights, tuned on DEV only, frozen in rerank_weights.json):
  score = w_customer*cos_customer + w_reply*max(cos_reply, cos_pair) + w_intent*intent_match + w_resolution*resolution_relevance
        + w_quality*reply_quality + w_outcome*outcome_bonus - w_dup*duplicate - w_dm*dm_handoff - w_same*same_customer
The outcome bonus swing is bounded by 1.5*w_outcome (default 0.015 score = a 0.04 customer-cosine gap); it can never overturn a larger semantic difference.

Resolution confidence (measurable; not an LLM probability):
  rc = 0.30*top_cluster_share + 0.25*min(1, independent_support/3) + 0.25*top_resolution_similarity + 0.20*(1 - conflict)
       - 0.30*[customer_history_risk] - 1.0*[insufficient_query]
Gate-v3 levels (thresholds calibrated on DEV): STRONG >= t_strong, SUFFICIENT >= t_sufficient, WEAK >= t_weak, else INSUFFICIENT.
A case is SUFFICIENT only if the top cluster is consistent (share >= min_top_share) and has >= min_support independent
resolution-bearing cases at or above the support similarity.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from resolveai.intelligence.classifier import CANONICAL_TERMS
from resolveai.intelligence.silver import GLYPH
from resolveai.retrieval.bm25 import tokenize
from resolveai.schemas.evidence import EvidenceItem, ResolutionCandidate, SufficiencySignals

GATE_VERSION = "gate-v3"
RESOLUTION_ACTIONS = {"update", "restart", "reset", "settings", "article"}
_W_PATH = Path(__file__).with_name("rerank_weights.json")
_G_PATH = Path(__file__).with_name("gate_v3_config.json")
_WORD = re.compile(r"[a-z]{4,}")
_STEP = re.compile(r"\b(settings ?>|go to|tap|toggle|restart|update|reset|reinstall|sign out|back up|hold|press|check|turn (on|off))\b", re.I)
# A reply is RESOLUTION-BEARING only if a non-question sentence states an instruction or a released fix. The Phase-1 weak
# `action_class` labels "Which iOS 11 version are you running?" as `update` (it matches "ios 11"); the hand-check of the
# first gate-v3 calibration (gate_v3_handcheck.md) showed ~half of the "resolution clusters" were such questions.
_INSTRUCTION = re.compile(
    r"\b(updat(e|ed|ing) (to|your|the)|install(ing)? (the|ios|it)|back(ing)? ?up (and|your|the)|restart(ing)? (the|your|it)|let'?s (restart|update|reset|try|be sure)"
    r"|try (restarting|updating|resetting|these|this|the)|reset (all|network|the|your)|force (restart|close|quit)|follow (the|these) steps|steps (here|in this|outlined|below)"
    r"|check( out)?:?\s*(this|the|these|<url>)|(released|includes|contains) (an? )?(update|fix)|fix(ed)? (in|with) (the |a )?(latest|recent|an|ios|update)|work ?around"
    r"|settings ?> ?general ?> ?(software update|reset)|turn (off|on) (the|your|[a-z]+ (and|or))|toggle|adjustments?)(?!\w)", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+")


def is_resolution_bearing(reply: str) -> bool:
    """True when at least one sentence that is NOT a question carries an instruction / released-fix statement."""
    for s in _SENT.split((reply or "").strip()):
        s = s.strip()
        if s and not s.endswith("?") and _INSTRUCTION.search(s):
            return True
    return False


# ------------------------------------------------------------------ reranker -------------------------------------------
@dataclass(frozen=True)
class RerankWeights:
    w_customer: float = 0.35
    w_reply: float = 0.25
    w_intent: float = 0.10
    w_resolution: float = 0.20
    w_quality: float = 0.05
    w_outcome: float = 0.01   # max swing 0.015 score = 0.04 customer-cosine; the outcome regex is a weak bonus, never a label
    w_dup: float = 0.15
    w_dm: float = 0.20
    w_same: float = 0.30
    version: str = "rerank-v1"

    @classmethod
    def load(cls) -> RerankWeights:
        if _W_PATH.exists():
            d = json.loads(_W_PATH.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        return cls()

    def save(self, path: Path = _W_PATH) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def reply_quality(reply: str) -> float:
    """0-1: does the reply state a concrete step? length-normalised, capped."""
    steps = len(_STEP.findall(reply or ""))
    length = min(len(reply or ""), 240) / 240
    return round(min(1.0, 0.5 * length + 0.25 * min(steps, 2)), 3)


def outcome_bonus(outcome: str, substantive: bool) -> float:
    if not substantive:
        return 0.0
    return {"positive": 1.0, "mixed": 0.3, "negative": -0.5}.get(outcome, 0.0)


def rerank(cands: list[dict], w: RerankWeights, query_intent: str | None) -> list[dict]:
    """cands: dicts with cos_customer, cos_reply, cos_pair, weak_intent, action_class, substantive, dm_handoff, outcome,
    reply, same_customer. Adds `rerank` and `resolution_relevance`, sorts desc, marks duplicates by normalised reply."""
    seen: set[str] = set()
    for c in cands:
        key = re.sub(r"\s+", " ", (c["reply"] or "").lower()).strip()
        c["duplicate"] = key in seen
        seen.add(key)
        c["resolution_relevance"] = bool(c["substantive"] and c["action_class"] in RESOLUTION_ACTIONS and is_resolution_bearing(c["reply"]))
        c["reply_quality"] = reply_quality(c["reply"])
        c["intent_match"] = bool(query_intent) and c["weak_intent"] == query_intent
        c["rerank"] = (w.w_customer * c["cos_customer"] + w.w_reply * max(c["cos_reply"], c["cos_pair"]) + w.w_intent * float(c["intent_match"])
                       + w.w_resolution * float(c["resolution_relevance"]) + w.w_quality * c["reply_quality"]
                       + w.w_outcome * outcome_bonus(c["outcome"], c["substantive"]) - w.w_dup * float(c["duplicate"])
                       - w.w_dm * float(c["dm_handoff"]) - w.w_same * float(c.get("same_customer", False)))
    return sorted(cands, key=lambda c: (-c["rerank"], c["doc"]))


# ------------------------------------------------------------------ clusters + consistency ------------------------------
def _reply_words(t: str) -> set[str]:
    return {x for x in _WORD.findall((t or "").lower())}


def cluster_resolutions(items: list[EvidenceItem], *, min_sim: float, jaccard: float = 0.0) -> list[ResolutionCandidate]:
    """Group resolution-bearing items (substantive, resolution action class, customer-side similarity >= min_sim, not the
    same customer) by ACTION CLASS - the resolution taxonomy (update / restart / reset / settings / article). Reply-text
    sub-clustering was tried first and split five 'update' replies with different wording into five singletons, which
    made every case 'mixed'; the action class is the unit a human would call "the same fix". Each cluster keeps every
    source id; the representative is the most step-bearing, most similar reply. `jaccard` is kept for API compatibility."""
    res = [i for i in items if i.quality.resolution_relevance and i.quality.semantic_relevance >= min_sim and not i.quality.same_customer]
    groups: dict[str, list[EvidenceItem]] = defaultdict(list)
    for it in res:
        groups[it.quality.action_class].append(it)
    total = len(res) or 1
    out = []
    for action, g in groups.items():
        rep = max(g, key=lambda i: (reply_quality(i.brand_reply), i.quality.semantic_relevance))
        out.append(ResolutionCandidate(action_class=action, representative_reply=rep.brand_reply, representative_id=rep.evidence_id, evidence_ids=[i.evidence_id for i in g],
                                       support_count=len(g), mean_similarity=round(sum(i.quality.semantic_relevance for i in g) / len(g), 3),
                                       positive_outcomes=sum(1 for i in g if i.outcome == "positive"), share=round(len(g) / total, 3)))
    return sorted(out, key=lambda c: (-c.support_count, -c.mean_similarity))


def consistency_of(cands: list[ResolutionCandidate], min_top_share: float) -> str:
    if not cands:
        return "no_resolution"
    return "consistent" if cands[0].share >= min_top_share else "mixed_resolution"


# ------------------------------------------------------------------ confidence + gate v3 ---------------------------------
@dataclass(frozen=True)
class GateV3Config:
    support_similarity: float = 0.85   # a resolution-bearing case counts as support at/above this (customer-side cosine); gate-v2 level, never lowered
    min_support: int = 2                # independent resolution-bearing cases for SUFFICIENT
    min_top_share: float = 0.6          # top cluster must hold this share of resolution-bearing support
    t_weak: float = 0.35
    t_sufficient: float = 0.55
    t_strong: float = 0.75
    min_query_tokens: int = 3
    require_symptom_term: bool = True   # query must name a symptom/feature (see SYMPTOM_TERMS); vague complaints cannot be answered by any evidence
    relevance_floor: float = 0.55      # below this top cosine nothing is even 'usable' (engine QUALITY_USABLE)
    version: str = GATE_VERSION

    @classmethod
    def load(cls) -> GateV3Config:
        if _G_PATH.exists():
            d = json.loads(_G_PATH.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        return cls()

    def save(self, path: Path = _G_PATH) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def content_tokens(query: str) -> int:
    return sum(1 for t in tokenize(query) if not t.startswith("<"))


# Query specificity (Phase 5). A vague complaint ("my phone keeps bugging out", "why is my phone tripping??") retrieves
# vague historical complaints, and in this KB those were answered with the November-2017 autocorrect workaround, so the
# evidence looked STRONG and consistent. No evidence can answer a query that states no symptom, so gate-v3 requires at
# least one symptom/product-feature term (the classifier's canonical terms + common iOS symptom words + the "I" glyph).
# Product names alone (iphone, ipad, mac) do not count. Measured on dev in scripts/phase5/a_retrieval_resolution.py.
SYMPTOM_TERMS: frozenset[str] = frozenset({w for ws in CANONICAL_TERMS.values() for w in ws} | {
    "update", "updated", "updating", "ios", "glitch", "glitching", "glitchy", "bug", "buggy", "stuck", "unresponsive", "lagging", "laggy",
    "notification", "notifications", "alarm", "alarms", "sound", "volume", "touch", "touchscreen", "overheating", "overheat", "hot", "deleted", "delete", "missing", "lost",
    "sync", "syncing", "download", "downloading", "install", "installing", "error", "messages", "message", "texts", "text", "calls", "call", "email", "emails", "calendar",
    "camera", "photo", "video", "videos", "airpods", "watch", "keyboard", "autocorrect", "letter", "typing", "wallpaper", "lock", "unlock", "faceid", "face", "touchid",
    "fingerprint", "brightness", "display", "flicker", "flickering", "shutdown", "shutting", "reboot", "rebooting", "restarts", "restarting", "loading", "load", "login",
    "password", "passcode", "apps", "app", "music", "spotify", "youtube", "instagram", "snapchat", "twitter", "facebook", "whatsapp", "netflix", "podcast", "podcasts",
    "safari", "siri", "mail", "maps", "wifi", "bluetooth", "hotspot", "data", "signal", "lte", "carrier", "sim", "icloud", "backup", "restore", "storage", "space",
    "contacts", "notes", "reminders", "clock", "timer", "screenshot", "screenshots", "haptic", "vibrate", "vibration", "speaker", "microphone", "mic", "headphones", "jack",
    "charging", "charge", "charger", "battery", "drain", "draining", "percent", "cable", "lightning", "port", "airplay", "carplay", "homekit", "airdrop", "handoff",
    "imessage", "facetime", "emoji", "emojis", "gif", "gifs", "font", "fonts", "autofill", "predictive", "dictation", "spelling", "capital", "lowercase", "uppercase",
    "broken", "upgrade", "upgraded", "upgrading", "sierra", "mojave", "beta", "symbol", "question", "mark", "box", "autocorrecting", "corrects", "correcting",
    "enable", "disable", "disabling", "enabling",
})
_GLYPH_TEXT = re.compile(r"(\bI\.T\b|\bA\s?\[\?\]|\bA\s?⏰)", re.I)   # the autocorrect bug written out: "I.T", "A[?]", "A⏰"


def symptom_tokens(query: str) -> int:
    n = sum(1 for t in tokenize(query) if t in SYMPTOM_TERMS)
    return n + (1 if (GLYPH.search(query or "") or _GLYPH_TEXT.search(query or "")) else 0)


def resolution_confidence(top_share: float, support: int, top_res_sim: float, conflict: bool, customer_history_risk: bool, insufficient_query: bool) -> float:
    rc = 0.30 * top_share + 0.25 * min(1.0, support / 3) + 0.25 * max(0.0, top_res_sim) + 0.20 * (0.0 if conflict else 1.0)
    rc -= 0.30 * float(customer_history_risk) + 1.0 * float(insufficient_query)
    return round(max(0.0, min(1.0, rc)), 3)


def decide_v3(items: list[EvidenceItem], cfg: GateV3Config, query_intent: str | None = None, query: str = "") -> dict:
    """Returns dict(level, sufficient, reason, confidence, consistency, candidates, signals)."""
    top = items[: 5]
    sims = [i.quality.semantic_relevance for i in top]
    top_sim = sims[0] if sims else 0.0
    n_tokens = content_tokens(query)
    n_symptom = symptom_tokens(query)
    intents = Counter(i.quality.candidate_intent for i in top)
    modal, modal_n = (intents.most_common(1)[0] if intents else ("", 0))
    cands = cluster_resolutions(items, min_sim=cfg.support_similarity)
    support = sum(c.support_count for c in cands)
    same = sum(1 for i in top if i.quality.same_customer and i.substantive)
    cons = consistency_of(cands, cfg.min_top_share)
    conflict = cons == "mixed_resolution"
    top_res_sim = cands[0].mean_similarity if cands else 0.0
    chr_ = bool(same) and same >= max(1, support)
    insufficient_q = n_tokens < cfg.min_query_tokens or (cfg.require_symptom_term and n_symptom == 0)
    rc = resolution_confidence(cands[0].share if cands else 0.0, support, top_res_sim, conflict, chr_, insufficient_q)
    sig = SufficiencySignals(n_retrieved=len(items), n_relevant=sum(1 for i in items if i.quality.quality != "weak"), query_content_tokens=n_tokens, query_symptom_tokens=n_symptom, top_similarity=top_sim,
                             similarity_margin=(sims[0] - sims[2]) if len(sims) >= 3 else 0.0, intent_agreement=(modal_n / len(top)) if top else 0.0, modal_intent=modal,
                             query_intent_agreement=(sum(1 for i in top if i.quality.intent_match) / len(top)) if (top and query_intent) else None,
                             support_count=support, resolution_bearing=sum(c.positive_outcomes for c in cands), action_classes={c.action_class: c.support_count for c in cands},
                             conflicting=conflict, same_customer_count=same)
    # ordered reasons
    if insufficient_q:
        level, reason = "INSUFFICIENT", "insufficient_query"
    elif not items or top_sim < cfg.relevance_floor:
        level, reason = "INSUFFICIENT", "no_relevant_evidence"
    elif chr_:
        level, reason = "INSUFFICIENT", "customer_history_risk"
    elif not cands:
        level, reason = ("WEAK", "insufficient_resolution_evidence") if rc >= cfg.t_weak or top_sim >= cfg.support_similarity else ("INSUFFICIENT", "weak_similarity")
    elif conflict:
        level, reason = "WEAK", "mixed_resolution"
    elif support < cfg.min_support or rc < cfg.t_sufficient:
        level, reason = "WEAK", "weak_resolution_evidence"
    elif rc >= cfg.t_strong:
        level, reason = "STRONG", "strong_consistent_evidence"
    else:
        level, reason = "SUFFICIENT", "strong_consistent_evidence"
    return {"level": level, "sufficient": level in ("SUFFICIENT", "STRONG"), "reason": reason, "confidence": rc, "consistency": cons, "candidates": cands, "signals": sig}
