"""Final product hardening: grounding audit of every automatic response available, without any model call. Read-only.

  python scripts/evaluation/grounding_audit.py

1. Release golden run (artifacts/final/evaluation/runs/final_release.jsonl), every AUTO_HANDLE row:
   - drafted replies: at least one citation, every citation a retrieved case, the gate judged the evidence sufficient (SUFFICIENT or
     STRONG), verification passed, the row was not annotated for escalation;
   - templates: no citations and the text is one of the fixed templates.
2. Captured API responses (frontend/tests/fixtures/resolve_*.json) whose action is AUTO_HANDLE: the same checks, plus every
   output-gate check passed and, where the captured trace belongs to the same request, the trace records the final decision,
   verification and the output gate, retrieved the cited cases, and stores no reply text.
Writes artifacts/product/hardening/grounding_audit.json. Exit code 1 on any failed check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.agent import drafter  # noqa: E402
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.evaluation.records import read_records  # noqa: E402
from resolveai.evaluation.reporting import gold_map  # noqa: E402

RUN = ROOT / "artifacts" / "final" / "evaluation" / "runs" / "final_release.jsonl"
FIXTURES = ROOT / "frontend" / "tests" / "fixtures"
OUT = ROOT / "artifacts" / "product" / "hardening" / "grounding_audit.json"
TEMPLATES = {t.strip() for t in drafter.CANNED.values()}


def audit_release() -> list[dict]:
    gm = gold_map(load_golden())
    rows = []
    for r in read_records(RUN):
        if r.action != "AUTO_HANDLE":
            continue
        ids = {e.evidence_id for e in r.evidence}
        template = r.response.strip() in TEMPLATES
        if template:
            checks = {"no_citations": not r.evidence_refs, "fixed_template_text": True}
        else:
            checks = {"has_citations": bool(r.evidence_refs), "citations_are_retrieved_cases": set(r.evidence_refs) <= ids,
                      "evidence_sufficient": bool(r.evidence_sufficient) and r.evidence_level in ("SUFFICIENT", "STRONG"), "verified": r.verified is True}
        checks["not_annotated_for_escalation"] = not gm[r.gid]["should_escalate"]
        rows.append({"gid": r.gid, "kind": "template" if template else "drafted", "evidence_level": r.evidence_level, "citations": len(r.evidence_refs), "checks": checks, "passed": all(checks.values())})
    return rows


def audit_fixtures() -> list[dict]:
    traces = {}
    for p in FIXTURES.glob("trace_*.json"):
        t = json.loads(p.read_text(encoding="utf-8"))
        traces[t["trace_id"]] = t
    rows = []
    for p in sorted(FIXTURES.glob("resolve_*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("action") != "AUTO_HANDLE":
            continue
        refs = [x["evidence_id"] for x in r["response"]["evidence_refs"]]
        ids = {i["evidence_id"] for i in r["evidence"]["items"]}
        drafted = r["response"]["kind"] == "auto_reply"
        checks = {"output_gate_all_passed": all(r["outcome"]["output_gate"].values()) and not r["outcome"]["blocking_checks"]}
        if drafted:
            checks |= {"has_citations": bool(refs), "citations_are_retrieved_cases": set(refs) <= ids, "evidence_sufficient": r["evidence"]["sufficient"] and r["evidence"]["sufficiency_level"] in ("SUFFICIENT", "STRONG"),
                       "verified": bool(r.get("verification") and r["verification"]["verified"])}
        else:
            checks |= {"no_citations": not refs}
        t = traces.get(r["trace_id"])
        if t:
            names = [e["name"] for e in t["events"]]
            retrieved = next((e.get("data", {}).get("evidence_ids") or [] for e in t["events"] if e["name"] == "retrieval_completed"), [])
            checks |= {"trace_final_decision": t.get("final_decision") == "AUTO_HANDLE", "trace_records_verification_and_gate": "response_verified" in names and "output_allowed" in names,
                       "trace_retrieved_the_cited_cases": set(refs) <= set(retrieved), "trace_stores_no_reply_text": r["response"]["text"] not in json.dumps(t)}
        rows.append({"fixture": p.name, "kind": "drafted" if drafted else "template", "citations": len(refs), "trace_checked": bool(t), "checks": checks, "passed": all(checks.values())})
    return rows


def main() -> int:
    release, fixtures = audit_release(), audit_fixtures()
    report = {"release_run": {"source": str(RUN.relative_to(ROOT)).replace("\\", "/"), "automatic_responses": len(release), "drafted": sum(r["kind"] == "drafted" for r in release),
                              "templates": sum(r["kind"] == "template" for r in release), "failed": [r for r in release if not r["passed"]], "rows": release},
              "captured_api_responses": {"automatic_responses": len(fixtures), "failed": [r for r in fixtures if not r["passed"]], "rows": fixtures},
              "note": "Grounded means supported by retrieved historical cases and verified; it does not mean the fix solved the customer's problem."}
    report["passed"] = not report["release_run"]["failed"] and not report["captured_api_responses"]["failed"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"release_automatic": len(release), "drafted": report["release_run"]["drafted"], "templates": report["release_run"]["templates"],
                      "release_failed": len(report["release_run"]["failed"]), "fixtures_automatic": len(fixtures), "fixtures_failed": len(report["captured_api_responses"]["failed"]), "passed": report["passed"]}, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
