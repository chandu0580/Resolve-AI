"""Phase 1-A: LLM smoke-test benchmark. Picks the model by evidence, not preference (locked decision 3).

For every candidate model reachable through the configured OpenAI-compatible endpoint, run a fixed battery over
data/dev/smoke_dev.jsonl (30 hand-labelled examples, disjoint from the golden set) and measure:
  structured-output reliability, intent accuracy, evidence-extraction grounding, grounded-reply compliance,
  escalation agreement, latency, tokens/cost, failure rate.

Run:  python scripts/phase1/a_llm_smoke.py [--models glm-5.2,glm-5.3-flash] [--no-cache]
Writes: artifacts/llm_smoke/results.json, results.md, raw/<model>.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import time
from pathlib import Path

from openai import OpenAI

from resolveai import config
from resolveai.models.taxonomy import INTENT_NAMES, INTENTS

DEV = Path("data/dev/smoke_dev.jsonl")
OUT = Path("artifacts/llm_smoke")

# Candidate = (provider, model). Provider credentials come from .env; a provider with no key is skipped.
PROVIDERS = {
    "primary": (config.LLM_BASE_URL, config.LLM_API_KEY),
    "gemini": (os.getenv("GEMINI_BASE_URL", ""), os.getenv("GEMINI_API_KEY", "")),
    "groq": (os.getenv("GROQ_BASE_URL", ""), os.getenv("GROQ_API_KEY", "")),
}
DEFAULT_CANDIDATES = [
    ("primary", config.LLM_MODEL),
    ("gemini", "gemini-2.5-flash"), ("gemini", "gemini-3.5-flash-lite"), ("gemini", "gemini-3.8-flash"),
    ("groq", "openai/gpt-oss-120b"), ("groq", "openai/gpt-oss-20b"), ("groq", "qwen/qwen3.8-27b"),
]
# USD per 1M tokens (input, output), list prices where known. None => tokens only.
PRICE = {"glm-5.2": (1.0, 3.2), "gemini-2.5-flash": (0.30, 2.50), "gemini-3.5-flash-lite": (0.10, 0.40), "gemini-3.8-flash": None,
         "openai/gpt-oss-120b": (0.15, 0.75), "openai/gpt-oss-20b": (0.10, 0.50), "qwen/qwen3.8-27b": None}
FORBIDDEN = re.compile(r"\b(refund|replace(ment)? for free|we will fix|guarantee|compensat|within \d+ (hours|days))\b", re.I)

INTENT_LIST = "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())
SYS = "You are the AppleSupport Twitter agent. Answer only in the JSON format requested."


def load_dev() -> list[dict]:
    return [json.loads(line) for line in DEV.read_text(encoding="utf-8").splitlines() if line.strip()]


class Runner:
    def __init__(self, provider: str, model: str, use_cache: bool):
        base_url, key = PROVIDERS[provider]
        self.provider, self.model, self.use_cache = provider, model, use_cache
        self.client = OpenAI(api_key=key, base_url=base_url, timeout=90)
        self.cache_dir = config.CACHE_DIR / "smoke" / provider / model.replace("/", "__")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.calls: list[dict] = []

    def call(self, task: str, messages: list[dict], json_mode: bool = True, max_tokens: int = 400) -> dict:
        # sha256, not hash(): Python salts str hashes per process, which silently defeated the cache on reruns.
        digest = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()[:24]
        key = self.cache_dir / f"{task}_{digest}.json"
        if self.use_cache and key.exists():
            rec = json.loads(key.read_text(encoding="utf-8"))
            rec["cached"] = True
            self.calls.append(rec)
            return rec
        kw = dict(model=self.model, messages=messages, temperature=0, max_tokens=max_tokens)
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        t0 = time.perf_counter()
        rec = {"task": task, "cached": False}
        try:
            r = self.client.chat.completions.create(**kw)
            rec.update(
                content=r.choices[0].message.content or "",
                latency_ms=(time.perf_counter() - t0) * 1000,
                tokens_in=getattr(r.usage, "prompt_tokens", 0),
                tokens_out=getattr(r.usage, "completion_tokens", 0),
                error="",
            )
        except Exception as e:  # noqa: BLE001
            rec.update(content="", latency_ms=(time.perf_counter() - t0) * 1000, tokens_in=0, tokens_out=0, error=f"{type(e).__name__}: {e}"[:300])
        key.write_text(json.dumps(rec), encoding="utf-8")
        self.calls.append(rec)
        return rec


def parse_json(s: str) -> dict | None:
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:  # noqa: BLE001
                return None
        return None


def t_intent(r: Runner, ex: dict) -> dict:
    msgs = [
        {"role": "system", "content": SYS},
        {"role": "user", "content": f"Intents:\n{INTENT_LIST}\n\nCustomer message: {ex['customer_message']}\nContext: {ex.get('context') or 'none'}\n\nReturn JSON: {{\"intent\": <one of the intent names>, \"confidence\": <0-1>}}"},
    ]
    rec = r.call("intent", msgs, max_tokens=600)
    js = parse_json(rec["content"]) or {}
    ok = isinstance(js.get("intent"), str) and js["intent"] in INTENT_NAMES and isinstance(js.get("confidence"), (int, float))
    return {"schema_ok": ok, "correct": ok and js["intent"] == ex["intent"], "pred": js.get("intent")}


def t_evidence(r: Runner, ex: dict) -> dict:
    ev = "\n".join(f"[{i+1}] {e}" for i, e in enumerate(ex["evidence"]))
    msgs = [
        {"role": "system", "content": SYS},
        {"role": "user", "content": f"Customer message: {ex['customer_message']}\n\nHistorical AppleSupport replies to similar issues:\n{ev}\n\nExtract the concrete troubleshooting steps or information requests that appear in the evidence and are relevant to this customer. Do not invent steps. Return JSON: {{\"steps\": [{{\"text\": str, \"source\": <evidence number>}}]}}"},
    ]
    rec = r.call("evidence", msgs, max_tokens=900)
    js = parse_json(rec["content"]) or {}
    steps = js.get("steps") if isinstance(js.get("steps"), list) else None
    if steps is None:
        return {"schema_ok": False, "grounded_rate": 0.0, "n_steps": 0}
    grounded = []
    for s in steps:
        src = s.get("source") if isinstance(s, dict) else None
        text = s.get("text", "") if isinstance(s, dict) else ""
        if isinstance(src, int) and 1 <= src <= len(ex["evidence"]):
            words = set(re.findall(r"[a-z]{4,}", text.lower()))
            evw = set(re.findall(r"[a-z]{4,}", ex["evidence"][src - 1].lower()))
            grounded.append(len(words & evw) / max(1, len(words)) >= 0.4)
        else:
            grounded.append(False)
    return {"schema_ok": True, "grounded_rate": (sum(grounded) / len(grounded)) if grounded else 1.0, "n_steps": len(steps)}


def t_reply(r: Runner, ex: dict) -> dict:
    ev = "\n".join(f"[{i+1}] {e}" for i, e in enumerate(ex["evidence"]))
    msgs = [
        {"role": "system", "content": SYS},
        {"role": "user", "content": f"Customer message: {ex['customer_message']}\nContext: {ex.get('context') or 'none'}\n\nEvidence (how AppleSupport handled similar issues):\n{ev}\n\nWrite the public reply tweet. Rules: <=280 characters, warm and concise like AppleSupport, only suggest steps present in the evidence, never promise refunds/replacements/timelines, do not include URLs or @handles. Return JSON: {{\"reply\": str}}"},
    ]
    rec = r.call("reply", msgs, max_tokens=700)
    js = parse_json(rec["content"]) or {}
    reply = js.get("reply") if isinstance(js.get("reply"), str) else ""
    words = set(re.findall(r"[a-z]{5,}", reply.lower()))
    evw = set(re.findall(r"[a-z]{5,}", " ".join(ex["evidence"]).lower()))
    return {
        "schema_ok": bool(reply),
        "len_ok": 0 < len(reply) <= 280,
        "no_url": "http" not in reply and "t.co" not in reply,
        "no_handle": "@" not in reply,
        "no_promise": not FORBIDDEN.search(reply),
        "overlap": (len(words & evw) / max(1, len(words))) if words else 0.0,
        "reply": reply,
    }


def t_escalation(r: Runner, ex: dict) -> dict:
    msgs = [
        {"role": "system", "content": SYS},
        {"role": "user", "content": f"Customer message: {ex['customer_message']}\nContext: {ex.get('context') or 'none'}\n\nDecide whether AppleSupport can resolve this with a public troubleshooting reply (auto_handle) or whether it must move to a human via DM (escalate) because it needs account/serial/order details, involves physical damage or repair, safety, legal threats, or the customer already tried the standard steps. Return JSON: {{\"decision\": \"auto_handle\"|\"escalate\", \"reason\": str}}"},
    ]
    rec = r.call("escalation", msgs, max_tokens=600)
    js = parse_json(rec["content"]) or {}
    d = js.get("decision")
    ok = d in ("auto_handle", "escalate") and isinstance(js.get("reason"), str) and len(js["reason"]) > 5
    return {"schema_ok": ok, "correct": ok and (d == "escalate") == bool(ex["should_escalate"]), "pred": d}


def bench(provider: str, model: str, dev: list[dict], use_cache: bool) -> dict:
    r = Runner(provider, model, use_cache)
    res = {"intent": [], "evidence": [], "reply": [], "escalation": []}
    for ex in dev:
        res["intent"].append(t_intent(r, ex))
        res["evidence"].append(t_evidence(r, ex))
        res["reply"].append(t_reply(r, ex))
        res["escalation"].append(t_escalation(r, ex))
    live = [c for c in r.calls if not c["cached"]]
    lat = [c["latency_ms"] for c in r.calls if not c["error"]]
    tin, tout = sum(c["tokens_in"] for c in r.calls), sum(c["tokens_out"] for c in r.calls)
    price = PRICE.get(model)
    n = len(dev)
    m = {
        "model": model,
        "provider": provider,
        "n_examples": n,
        "n_calls": len(r.calls),
        "live_calls": len(live),
        "failure_rate": sum(1 for c in r.calls if c["error"]) / max(1, len(r.calls)),
        "schema_valid_rate": statistics.mean([x["schema_ok"] for k in res for x in res[k]]),
        "intent_accuracy": statistics.mean([x["correct"] for x in res["intent"]]),
        "evidence_grounded_rate": statistics.mean([x["grounded_rate"] for x in res["evidence"]]),
        "reply_compliance": statistics.mean([all((x["len_ok"], x["no_url"], x["no_handle"], x["no_promise"])) for x in res["reply"]]),
        "reply_evidence_overlap": statistics.mean([x["overlap"] for x in res["reply"]]),
        "escalation_accuracy": statistics.mean([x["correct"] for x in res["escalation"]]),
        "latency_p50_ms": statistics.median(lat) if lat else None,
        "latency_p95_ms": sorted(lat)[int(0.95 * (len(lat) - 1))] if lat else None,
        "tokens_in": tin,
        "tokens_out": tout,
        "cost_usd_per_100_msgs": round((tin * price[0] + tout * price[1]) / 1e6 / n * 100, 4) if price else None,
        "sample_errors": [c["error"] for c in r.calls if c["error"]][:3],
    }
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    with (OUT / "raw" / f"{provider}__{model.replace('/', '__')}.jsonl").open("w", encoding="utf-8") as f:
        for ex, i, e, p, s in zip(dev, res["intent"], res["evidence"], res["reply"], res["escalation"], strict=False):
            f.write(json.dumps({"id": ex["id"], "intent": i, "evidence": e, "reply": p, "escalation": s}) + "\n")
    return m


def discover(provider: str) -> list[str]:
    base_url, key = PROVIDERS[provider]
    try:
        return sorted(m.id.removeprefix("models/") for m in OpenAI(api_key=key, base_url=base_url, timeout=30).models.list().data)
    except Exception as e:  # noqa: BLE001
        print(f"[{provider}] models.list() unavailable ({type(e).__name__})")
        return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="", help="comma list of provider:model, e.g. primary:glm-5.2,groq:openai/gpt-oss-20b")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    dev = load_dev()
    cands = [tuple(x.split(":", 1)) for x in a.models.split(",")] if a.models else DEFAULT_CANDIDATES
    listed = {p: discover(p) for p in {c[0] for c in cands} if PROVIDERS[p][1]}
    results = []
    for provider, model in cands:
        if not PROVIDERS[provider][1]:
            print(f"\n== {provider}:{model} skipped (no key)")
            continue
        if listed.get(provider) and model not in listed[provider]:
            print(f"\n== {provider}:{model} not listed by endpoint; probing anyway")
        print(f"\n== {provider}:{model}")
        probe = Runner(provider, model, not a.no_cache).call("probe", [{"role": "user", "content": "Return JSON {\"ok\": true}"}], max_tokens=200)
        if probe["error"]:
            print("  not served / error:", probe["error"])
            results.append({"model": model, "provider": provider, "failure_rate": 1.0, "sample_errors": [probe["error"]]})
            continue
        r = bench(provider, model, dev, use_cache=not a.no_cache)
        results.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "sample_errors"}, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps({"providers": {p: PROVIDERS[p][0] for p in PROVIDERS}, "listed_models": listed, "results": results}, indent=2))
    cols = ["provider", "model", "failure_rate", "schema_valid_rate", "intent_accuracy", "evidence_grounded_rate", "reply_compliance", "reply_evidence_overlap", "escalation_accuracy", "latency_p50_ms", "latency_p95_ms", "tokens_out", "cost_usd_per_100_msgs"]
    lines = ["# LLM smoke-test results", "", f"Dev set: {len(dev)} hand-labelled examples x 4 tasks (intent, evidence extraction, grounded reply, escalation) = {4*len(dev)} calls per model.", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in results:
        lines.append("| " + " | ".join(str(round(r.get(c), 3)) if isinstance(r.get(c), float) else str(r.get(c, "")) for c in cols) + " |")
    lines += ["", "Errors (first 3 per model):", ""] + [f"- {r['provider']}:{r['model']}: {r.get('sample_errors')}" for r in results if r.get("sample_errors")]
    (OUT / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print("\nwrote", OUT / "results.md")


if __name__ == "__main__":
    main()
