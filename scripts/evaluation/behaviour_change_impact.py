"""Which golden rows reach a code path changed after the release evaluation. Read-only, deterministic, no model, no labels.

  python scripts/evaluation/behaviour_change_impact.py

Release 1.0.0 was evaluated once on the frozen golden set with pipeline-v6.1 / policy-v3.1. The final product pass changed live
behaviour (pipeline-v6.3 / policy-v3.3): a bare greeting gets a template without retrieval, an explicit request for a person is a
handoff, thanks and bare acknowledgements are separated and worded differently, a LOW-confidence "non-English" guess asks the
customer to restate instead of sending the English-only redirect, a message in a non-Latin script gets the language redirect,
a short reply is classified with the issue it answers, capitalization
and repeated "!" are no longer frustration signals, and matching keys are Unicode-normalised. The golden run is deliberately NOT
repeated (the set is not used for tuning). Instead this script reports, for each change, which golden rows even reach the changed
input path, using only the customer message and its thread. It never reads the annotations.
Writes artifacts/product/hardening/behaviour_change_impact.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.agent import risk  # noqa: E402
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.intelligence import conversation_acts as acts  # noqa: E402
from resolveai.intelligence.classifier import IntentService  # noqa: E402
from resolveai.intelligence.context import SHORT_TOKENS, build_context, content_tokens, parse_context  # noqa: E402
from resolveai.intelligence.silver import CLOSURE as OLD_CLOSURE  # noqa: E402  (the closure pattern policy-v3.1 used)
from resolveai.policy.escalation import CONFIDENCE_FLOOR  # noqa: E402
from resolveai.trust.injection import PATTERNS, detect_injection  # noqa: E402
from resolveai.trust.pii import redact_pii  # noqa: E402

OUT = ROOT / "artifacts" / "product" / "hardening" / "behaviour_change_impact.json"
# the v6.1 forms of the changed rules, reproduced verbatim for the comparison
OLD_SHORT_REPLY = re.compile(r"^\s*(yes|no|yeah|yep|nope|ok(ay)?|still (happening|not working|same|broken|nothing)|same (issue|problem|thing)|tried (that|it|everything)|"
                             r"(it )?(doesn.?t|didn.?t|does not|did not) work|not working|nothing (changed|happened|works)|done|sent|i did|already did|no luck|same here)\b[\s.!?]*$", re.I)
OLD_SHOUTING = re.compile(r"\b[A-Z]{6,}\b")
_OLD_ADDRESSEE = r"(?:there|all|everyone|team|folks|guys|friends?|apple|apple ?support|resolve ?ai|support)"
OLD_GREETING = re.compile(rf"^(?:{_OLD_ADDRESSEE} )?(?:hi+|hello+|hey+|hiya|howdy|yo|greetings|good (?:morning|afternoon|evening|day))(?: {_OLD_ADDRESSEE})*$")
OLD_EXCLAMATIONS = re.compile(r"!{3,}")
KEYS = ("frustration_flag_removed", "greeting_only", "human_request", "closure_now_matches", "ack_in_thread_no_longer_closure",
        "short_reply_status_changed", "short_reply_classified_with_issue", "injection_detection_changed",
        "non_english_low_confidence_no_longer_redirected", "bare_acknowledgement_wording_changed",
        "non_latin_script_now_redirected", "greeting_addressee_widened")


def main() -> int:
    golden = load_golden()   # hash-verified
    intents = IntentService()
    out: dict[str, list[str]] = {k: [] for k in KEYS}
    for row in golden.itertuples():
        message = redact_pii(row.customer_message).text
        ctx = parse_context(row.context)
        ctx = ctx.model_copy(update={"turns": [t.model_copy(update={"text": redact_pii(t.text).text}) for t in ctx.turns]})
        bundle = build_context(message, ctx)
        flags = risk.extract_rules(bundle)
        old_text = " ".join([bundle.current, *bundle.prior_customer])
        if (OLD_SHOUTING.search(old_text) or OLD_EXCLAMATIONS.search(old_text)) and not flags.high_frustration:
            out["frustration_flag_removed"].append(row.gid)
        if acts.is_greeting_only(bundle.current):
            out["greeting_only"].append(row.gid)
        if acts.requests_human(bundle.current):
            out["human_request"].append(row.gid)
        history = any(t.role == "customer" for t in ctx.turns)
        if acts.is_gratitude(bundle.current) and not OLD_CLOSURE.match(bundle.current):
            out["closure_now_matches"].append(row.gid)
        if OLD_CLOSURE.match(bundle.current) and not acts.is_gratitude(bundle.current) and history:
            out["ack_in_thread_no_longer_closure"].append(row.gid)
        old_short = content_tokens(bundle.current) < SHORT_TOKENS or bool(OLD_SHORT_REPLY.match(bundle.current))
        if old_short != bundle.is_short_reply:
            out["short_reply_status_changed"].append(row.gid)
        if bundle.is_short_reply and bundle.issue_text:
            out["short_reply_classified_with_issue"].append(row.gid)
        joined = "\n".join([bundle.current, *bundle.prior_customer, *bundle.prior_brand])
        if any(p.search(joined) for _, p in PATTERNS) != detect_injection(joined).detected:
            out["injection_detection_changed"].append(row.gid)
        # the language redirect now sits after the confidence floor, so a LOW-confidence non_english guess clarifies instead
        intent = intents.classify(bundle)
        if intent.intent == "non_english" and (intent.confidence_band == "LOW" or intent.confidence < CONFIDENCE_FLOOR):
            out["non_english_low_confidence_no_longer_redirected"].append(row.gid)
        # a bare acknowledgement now gets its own closing line instead of the "you're welcome" template
        if (intent.intent == "other" and acts.is_acknowledgement(bundle.current) and not acts.is_gratitude(bundle.current)
                and not any(t.role == "customer" for t in ctx.turns)):
            out["bare_acknowledgement_wording_changed"].append(row.gid)
        # a message written mostly in a non-Latin script now gets the language redirect instead of an English clarification
        if acts.is_non_latin_script(bundle.current):
            out["non_latin_script_now_redirected"].append(row.gid)
        # "hey bro" / "hi mate" are greetings now that the addressee list is wider
        if acts.is_greeting_only(bundle.current) and not OLD_GREETING.match(acts.act_key(bundle.current)):
            out["greeting_addressee_widened"].append(row.gid)
    touched = sorted(set().union(*out.values()))
    report = {"golden_rows": len(golden), "evaluated_pipeline": "pipeline-v6.1 / policy-v3.1", "current_pipeline": "pipeline-v6.3 / policy-v3.3",
              "method": "deterministic input-level check of which golden rows reach a code path changed in the final product pass; "
                        "the golden run was not repeated, no model was called and no annotation was read",
              "counts": {k: len(v) for k, v in out.items()}, "n_rows_touching_any_change": len(touched), "rows_touching_any_change": touched, "gids": out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "n_rows_touching_any_change": len(touched)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
