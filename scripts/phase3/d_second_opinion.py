"""Phase 3-D: GLM-5.2 second-opinion experiment. Policy fixed BEFORE running (no tuning on golden):
  consult the LLM only when the classifier band is LOW or MEDIUM (with-context variant);
  adopt the LLM intent only if it is among the classifier's top-3; otherwise keep the classifier's intent.
Compares classifier-only vs classifier+second-opinion on golden (once) and on the 30 hand-labelled smoke rows.
All calls go through LLMClient (SHA-256 cache, PII guard, timeout, structured validation). No hidden reasoning is stored.
  python scripts/phase3/d_second_opinion.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field

import resolveai  # noqa: F401
from resolveai.evaluation import load_golden
from resolveai.intelligence.classifier import IntentService
from resolveai.intelligence.context import build_context, parse_context
from resolveai.llm import LLMClient, LLMUnavailable, OpenAICompatibleProvider
from resolveai.models.taxonomy import INTENT_NAMES, INTENTS

OUT = Path("artifacts/intelligence")
PROMPT_VERSION = "intent-second-opinion-v1"
INTENT_LIST = "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())
SYS = "You classify AppleSupport customer tweets into exactly one intent. Answer only with the JSON requested."


class Opinion(BaseModel):
    intent: str = Field(description="one of the intent names")
    confidence: float = Field(ge=0, le=1)


def ask(client: LLMClient, bundle) -> Opinion | None:
    ctx = ""
    if bundle.issue_text:
        ctx = f"\nEarlier customer message: {bundle.issue_text}"
    if bundle.prior_brand:
        ctx += f"\nLast brand reply: {bundle.prior_brand[0]}"
    msgs = [{"role": "system", "content": SYS},
            {"role": "user", "content": f"Intents:\n{INTENT_LIST}\n\nRules: label the customer's main requested resolution; the corrupted 'I' glyph or 'I.T' means keyboard_text_bug; "
                                        f"a crash confined to one app is apps_services, device-wide is performance_crash; accessories without physical fault are not hardware_damage; "
                                        f"no concrete symptom -> general_complaint; not a support request -> other.{ctx}\nCurrent customer message: {bundle.current}\n\n"
                                        f'Return JSON: {{"intent": <name>, "confidence": <0-1>}}'}]
    try:
        o = client.structured(msgs, Opinion, prompt_version=PROMPT_VERSION, max_tokens=400)
        return o if o.intent in INTENT_NAMES else None
    except LLMUnavailable:
        return None


def evaluate(rows, svc: IntentService, client: LLMClient, label_key: str):
    recs, t0 = [], time.perf_counter()
    for r in rows:
        b = build_context(r["customer_message"], parse_context(r.get("context", "")))
        base = svc.classify(b)
        final, op, applied = base.intent, None, False
        if base.confidence_band in ("LOW", "MEDIUM"):
            o = ask(client, b)
            if o is not None:
                op = o.intent
                if o.intent in [t[0] for t in base.top3] and o.intent != base.intent:
                    final, applied = o.intent, True
                elif o.intent == base.intent:
                    applied = False
        recs.append({"id": r.get("gid", r.get("id")), "gold": r[label_key], "classifier": base.intent, "band": base.confidence_band, "llm": op, "final": final, "applied": applied,
                     "correct_classifier": base.intent == r[label_key], "correct_final": final == r[label_key], "correct_llm_alone": (op == r[label_key]) if op else None,
                     "short": len(r["customer_message"]) < 40, "multi_turn": bool(r.get("context")), "multi_intent": bool(r.get("multi_intent", False)), "consulted": base.confidence_band in ("LOW", "MEDIUM")})
    return recs, time.perf_counter() - t0


def summarise(recs):
    def acc(rs, k):
        return round(sum(1 for r in rs if r[k]) / len(rs), 4) if rs else None
    out = {"n": len(recs), "consulted": sum(r["consulted"] for r in recs), "applied": sum(r["applied"] for r in recs),
           "accuracy_classifier": acc(recs, "correct_classifier"), "accuracy_with_second_opinion": acc(recs, "correct_final"),
           "consulted_subset": {"n": sum(r["consulted"] for r in recs), "classifier": acc([r for r in recs if r["consulted"]], "correct_classifier"), "with_second_opinion": acc([r for r in recs if r["consulted"]], "correct_final"),
                                 "llm_alone": acc([r for r in recs if r["consulted"] and r["llm"]], "correct_llm_alone")},
           "slices": {}}
    for s in ("short", "multi_turn", "multi_intent"):
        rs = [r for r in recs if r[s]]
        if rs:
            out["slices"][s] = {"n": len(rs), "classifier": acc(rs, "correct_classifier"), "with_second_opinion": acc(rs, "correct_final")}
    changes = [r for r in recs if r["applied"]]
    out["changes"] = {"n": len(changes), "fixed": sum(1 for r in changes if r["correct_final"] and not r["correct_classifier"]), "broke": sum(1 for r in changes if r["correct_classifier"] and not r["correct_final"])}
    return out


def main() -> None:
    svc = IntentService()
    client = LLMClient(provider=OpenAICompatibleProvider())
    gold = load_golden()
    grows = [dict(gid=g.gid, customer_message=g.customer_message, context=g.context, intent=g.intent, multi_intent=bool(g.multi_intent)) for g in gold.itertuples()]
    smoke = [json.loads(line) for line in Path("data/dev/smoke_dev.jsonl").read_text(encoding="utf-8").splitlines()]
    res = {}
    for name, rows in (("smoke_dev_30", smoke), ("golden_197", grows)):
        recs, secs = evaluate(rows, svc, client, "intent")
        res[name] = summarise(recs) | {"seconds": round(secs, 1)}
        (OUT / f"second_opinion_{name}.jsonl").write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
        print(name, json.dumps(res[name], indent=1))
    res["usage"] = client.usage.as_dict()
    res["policy"] = "consult at LOW/MEDIUM band; adopt LLM intent only if in classifier top-3"
    (OUT / "second_opinion.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("usage:", res["usage"])


if __name__ == "__main__":
    main()
