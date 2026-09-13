"""Phase 6-B: LLM-as-judge scoring with the frozen rubric (rubric-v1 / judge-abs-v1 / judge-pair-v1).
  python scripts/phase6/b_judge.py --smoke                     # parse check on 3 DEV drafts (never golden), prints raw JSON
  python scripts/phase6/b_judge.py --absolute resolveai_full B1_simple_ml B2_direct_llm B0_trivial
  python scripts/phase6/b_judge.py --pairwise resolveai_full:B1_simple_ml resolveai_full:B2_direct_llm
  python scripts/phase6/b_judge.py --judge groq --absolute resolveai_full ... --gids data/human_eval/_packet_key.json   # second-family subset
Every call is cached (SHA-256 of model + prompt version + messages); failures are recorded, never dropped.
Writes artifacts/evaluation/judge_results.jsonl (absolute, appended per system; de-duplicated on gid+system+judge_model)
       artifacts/evaluation/pairwise_results.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import resolveai  # noqa: F401
from resolveai.evaluation.judge import JUDGE_PROMPT_VERSION, PAIR_PROMPT_VERSION, RUBRIC_VERSION, absolute_messages, judge_one, pairwise_one
from resolveai.evaluation.records import SystemRecord, read_records
from resolveai.llm import DiskCache, LLMClient, OpenAICompatibleProvider

OUT = Path("artifacts/evaluation")
RUNS = OUT / "runs"
GROQ_MODEL = "qwen/qwen3.8-27b"   # second model family; free tier limit 1000 output tokens/min -> paced


class PacedProvider(OpenAICompatibleProvider):
    """Retries on 429 with backoff so a rate-limited free tier still completes (no silent drops)."""

    def complete(self, model, messages, *, temperature, max_tokens, json_mode, timeout_s):
        last = None
        for attempt in range(6):
            try:
                return super().complete(model, messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode, timeout_s=timeout_s)
            except Exception as e:  # noqa: BLE001
                last = e
                if "429" in str(e) or "rate" in str(e).lower():
                    time.sleep(8 * (attempt + 1))
                    continue
                raise
        raise last


def make_client(which: str) -> LLMClient:
    if which == "groq":
        from dotenv import load_dotenv

        load_dotenv(".env")
        prov = PacedProvider(api_key=os.getenv("GROQ_API_KEY"), base_url=os.getenv("GROQ_BASE_URL"))
        return LLMClient(provider=prov, model=GROQ_MODEL, cache=DiskCache(), timeout_s=60)
    return LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())


def append_dedup(path: Path, rows: list[dict], keys: tuple[str, ...]) -> None:
    old = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []
    seen = {tuple(r.get(k) for k in keys) for r in rows}
    kept = [r for r in old if tuple(r.get(k) for k in keys) not in seen]
    path.write_text("\n".join(json.dumps(r) for r in kept + rows) + "\n", encoding="utf-8")


def smoke(client: LLMClient) -> None:
    recs = [json.loads(x) for x in Path("artifacts/resolution/draft_experiment.jsonl").read_text(encoding="utf-8").splitlines()][:3]
    for r in recs:
        rec = SystemRecord(gid=str(r["id"]), system="dev_smoke", message=r["message"], context=r.get("context") or "", intent_pred=r["intent"], escalate_pred=False, action="AUTO_HANDLE",
                           response=r["B_v2"]["text"] or "(no draft)", response_kind="troubleshoot", evidence=[{"evidence_id": e["id"], "customer_message": "", "brand_reply": e["reply"]} for e in r["evidence"]])
        print("PROMPT CHARS:", len(absolute_messages(rec)[1]["content"]))
        print(json.dumps(judge_one(client, rec, prompt_version=JUDGE_PROMPT_VERSION + "+smoke"), indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--absolute", nargs="*", default=[])
    ap.add_argument("--pairwise", nargs="*", default=[], help="x:y system pairs")
    ap.add_argument("--judge", default="glm", choices=["glm", "groq"])
    ap.add_argument("--gids", default=None, help="JSON file with a list (or packet key) restricting the rows")
    a = ap.parse_args()
    client = make_client(a.judge)
    if a.smoke:
        smoke(client)
        return
    gids = None
    if a.gids:
        raw = json.loads(Path(a.gids).read_text(encoding="utf-8"))
        gids = {x["gid"] for x in raw.values()} if isinstance(raw, dict) else set(raw)
    for system in a.absolute:
        recs = read_records(RUNS / f"{system}.jsonl")
        if gids:
            recs = [r for r in recs if r.gid in gids]
        rows, t0 = [], time.perf_counter()
        for k, r in enumerate(recs):
            rows.append(judge_one(client, r))
            if (k + 1) % 25 == 0:
                print(f"  {system} [{a.judge}]: {k + 1}/{len(recs)} failed={sum(x['failed'] for x in rows)}", flush=True)
        append_dedup(OUT / "judge_results.jsonl", rows, ("gid", "system", "judge_model"))
        print(f"{system} [{client.model}]: {len(rows)} scored, {sum(x['failed'] for x in rows)} failed, {time.perf_counter() - t0:.0f}s", flush=True)
    for pair in a.pairwise:
        x, y = pair.split(":")
        rx = {r.gid: r for r in read_records(RUNS / f"{x}.jsonl")}
        ry = {r.gid: r for r in read_records(RUNS / f"{y}.jsonl")}
        rows, t0 = [], time.perf_counter()
        for k, gid in enumerate(rx):
            if gids and gid not in gids:
                continue
            rows.append(pairwise_one(client, rx[gid], ry[gid]))
            if (k + 1) % 25 == 0:
                print(f"  {pair} [{a.judge}]: {k + 1}/{len(rx)}", flush=True)
        append_dedup(OUT / "pairwise_results.jsonl", rows, ("gid", "system_x", "system_y", "judge_model"))
        print(f"{pair} [{client.model}]: {len(rows)} compared, {sum(x['failed'] for x in rows)} failed, {time.perf_counter() - t0:.0f}s", flush=True)
    (OUT / "judge_config.json").write_text(json.dumps({"rubric_version": RUBRIC_VERSION, "absolute_prompt_version": JUDGE_PROMPT_VERSION, "pairwise_prompt_version": PAIR_PROMPT_VERSION,
                                                       "primary_judge": {"model": make_client("glm").model, "temperature": 0.0, "max_tokens": 1200}, "secondary_judge": {"model": GROQ_MODEL, "temperature": 0.0, "max_tokens": 1200, "provider": "groq", "note": "second model family; subset only (rate limited)"}}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
