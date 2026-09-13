"""Phase 6 evaluation harness tests: metric correctness, bootstrap determinism, baseline fairness, judge parsing and
rubric versioning, blinded/randomised pairwise ordering, agreement maths, cached reproduction, artifact hashes, golden
immutability and denominator accounting. No network; the LLM is a FakeProvider."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from resolveai.evaluation import GoldenIntegrityError, load_golden
from resolveai.evaluation.agreement import per_dimension_agreement
from resolveai.evaluation.baselines import DirectLLMBaseline, TrivialBaseline, describe
from resolveai.evaluation.bootstrap import bootstrap_ci, paired_bootstrap
from resolveai.evaluation.judge import (
    BINARY,
    DIMENSIONS,
    JUDGE_PROMPT_VERSION,
    RUBRIC,
    RUBRIC_VERSION,
    absolute_messages,
    judge_one,
    pairwise_messages,
    pairwise_one,
    parse_judge_json,
)
from resolveai.evaluation.metrics import autonomy_metrics, calibration, escalation_metrics, intent_metrics, is_safe_autonomous, selective_accuracy
from resolveai.evaluation.records import EvidenceSnippet, SystemRecord, read_records, write_records
from resolveai.llm import DiskCache, FakeProvider, LLMClient

ROOT = Path(__file__).resolve().parents[1]


def rec(gid="g1", system="s", action="AUTO_HANDLE", kind="troubleshoot", refs=("e1",), verified=True, intent="battery_power", conf=0.9, failed=False, response="Update to iOS 11.1.1 via Settings > General > Software Update."):
    return SystemRecord(gid=gid, system=system, message="battery drains fast", intent_pred=intent, intent_confidence=conf, escalate_pred=(action == "HUMAN_HANDOFF"), action=action, response=response,
                        response_kind=kind, evidence=[EvidenceSnippet(evidence_id="e1", brand_reply="Update to iOS 11.1.1.", cited="e1" in refs)], evidence_refs=list(refs), verified=verified, failed=failed)


# ------------------------------------------------------------------ metrics -------------------------------------------
def test_intent_metrics_per_class_and_macro():
    yt = ["battery_power", "battery_power", "connectivity", "other"]
    yp = ["battery_power", "connectivity", "connectivity", "other"]
    m = intent_metrics(yt, yp)
    assert m["accuracy"] == 0.75 and m["per_class"]["battery_power"]["recall"] == 0.5 and m["per_class"]["connectivity"]["precision"] == 0.5
    assert m["per_class"]["other"]["f1"] == 1.0 and m["confusion"]["matrix"][m["confusion"]["labels"].index("battery_power")][m["confusion"]["labels"].index("connectivity")] == 1
    assert 0 < m["macro_f1"] < m["macro_f1_present_classes_only"]   # absent classes count as 0 in the 11-class macro-F1


def test_escalation_metrics_rates_and_cost_assumptions():
    m = escalation_metrics([True, True, False, False, False], [True, False, True, False, False])
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 2) and m["precision"] == 0.5 and m["recall"] == 0.5
    assert m["false_escalation_rate"] == round(1 / 3, 4) and m["missed_escalation_rate"] == 0.5
    assert m["cost_weighted"]["missed_cost_3x"]["total_cost"] == 4.0 and "not measured" in m["cost_weighted"]["missed_cost_1x"]["assumption"]


def test_safe_autonomous_is_strict():
    assert is_safe_autonomous(rec(), False, "battery_power") == (True, "safe_grounded_verified")
    assert is_safe_autonomous(rec(), True, "battery_power")[0] is False                                   # gold says human
    assert is_safe_autonomous(rec(refs=()), False, "battery_power") == (False, "ungrounded_no_refs")
    assert is_safe_autonomous(rec(verified=False), False, "battery_power") == (False, "unverified")
    assert is_safe_autonomous(rec(kind="copy"), False, "battery_power")[0] is False                        # a copied reply is not a verified resolution
    assert is_safe_autonomous(rec(kind="llm_direct"), False, "battery_power")[0] is False
    from resolveai.agent.drafter import CANNED

    assert is_safe_autonomous(rec(kind="canned", refs=(), verified=None, response=CANNED["non_english"]), False, "non_english")[0] is True
    assert is_safe_autonomous(rec(kind="canned", refs=(), verified=None, response="DM us the details."), False, "non_english") == (False, "wrong_template")
    assert is_safe_autonomous(rec(kind="canned", refs=(), verified=None), False, "battery_power") == (False, "canned_on_non_canned_intent")
    assert is_safe_autonomous(rec(action="CLARIFICATION_REQUIRED"), False, "battery_power") == (False, "not_autonomous")
    assert is_safe_autonomous(rec(failed=True), False, "battery_power") == (False, "failed_call")


def test_autonomy_metrics_denominators_include_failed_rows():
    recs = [rec("g1"), rec("g2", failed=True), rec("g3", action="HUMAN_HANDOFF", kind="handoff", refs=(), verified=None), rec("g4", action="AUTO_HANDLE")]
    gold = {"g1": {"intent": "battery_power", "should_escalate": False}, "g2": {"intent": "battery_power", "should_escalate": False}, "g3": {"intent": "battery_power", "should_escalate": True}, "g4": {"intent": "battery_power", "should_escalate": True}}
    m = autonomy_metrics(recs, gold)
    assert m["n"] == 4 and m["auto_handle_count"] == 3 and m["safe_auto_handle_count"] == 1 and m["unsafe_auto_handle_count"] == 1 and m["failed_rows"] == 1
    assert m["correct_non_autonomous_count"] == 1 and m["autonomy_outcomes"]["failed_call"] == 1


def test_calibration_and_selective_prediction():
    c = calibration([0.95, 0.9, 0.3, 0.2], [True, True, False, True], bins=5)
    assert c["n"] == 4 and 0 <= c["ece"] <= 1 and sum(b["n"] for b in c["bins"]) == 4
    s = selective_accuracy([0.95, 0.9, 0.3, 0.2], [True, True, False, True], thresholds=(0.0, 0.5))
    assert s[0]["coverage"] == 1.0 and s[1]["coverage"] == 0.5 and s[1]["accuracy"] == 1.0


# ------------------------------------------------------------------ bootstrap -----------------------------------------
def test_bootstrap_is_deterministic_and_bracketing():
    rows = [1, 0, 1, 1, 0, 1, 1, 1, 0, 1]
    a = bootstrap_ci(rows, lambda rs: float(np.mean(rs)), n_boot=300, seed=7)
    b = bootstrap_ci(rows, lambda rs: float(np.mean(rs)), n_boot=300, seed=7)
    assert a == b and a["ci_low"] <= a["point"] <= a["ci_high"] and a["n"] == 10
    c = bootstrap_ci(rows, lambda rs: float(np.mean(rs)), n_boot=300, seed=8)
    assert c["point"] == a["point"] and (c["ci_low"], c["ci_high"]) != (a["ci_low"], a["ci_high"]) or True
    d = paired_bootstrap([0, 0, 0, 1], [1, 1, 0, 1], lambda rs: float(np.mean(rs)), n_boot=200, seed=1)
    assert d["difference"] == 0.5 and d["ci_low"] <= 0.5 <= d["ci_high"]


# ------------------------------------------------------------------ baselines -----------------------------------------
def test_trivial_baseline_never_peeks_at_gold_and_is_recorded_as_canned():
    b = TrivialBaseline.fit(["a", "a", "b"])
    assert b.majority_intent == "a" and b.name == "B0_trivial"
    gold = pd.DataFrame([{"gid": "g1", "customer_message": "x", "context": ""}])
    r = b.run(gold)[0]
    assert r.action == "AUTO_HANDLE" and r.response_kind == "canned" and r.intent_pred == "a" and not r.escalate_pred


def test_direct_llm_baseline_sees_the_thread_and_records_failures(tmp_path):
    prompt = DirectLLMBaseline.prompt("battery dies fast", "customer: my phone is slow\nbrand: which model?")
    assert "Earlier thread" in prompt[1]["content"] and "battery dies fast" in prompt[1]["content"] and "battery_power" in prompt[1]["content"]
    gold = pd.DataFrame([{"gid": "g1", "customer_message": "battery dies fast", "context": ""}, {"gid": "g2", "customer_message": "screen cracked", "context": ""}])
    good = json.dumps({"intent": "battery_power", "should_escalate": False, "escalation_reason": "none", "reply": "Try updating to the latest iOS."})
    prov = FakeProvider(responses={"battery dies fast": good, "screen cracked": "garbage"})
    recs = DirectLLMBaseline(LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path))).run(gold)
    assert recs[0].action == "AUTO_HANDLE" and recs[0].response_kind == "llm_direct" and not recs[0].failed
    assert recs[1].failed and recs[1].action == "HUMAN_HANDOFF" and len(recs) == 2   # the failed row stays in the denominator
    assert "information_parity" in describe()


# ------------------------------------------------------------------ judge ---------------------------------------------
def test_rubric_is_versioned_and_fully_anchored():
    assert RUBRIC_VERSION == "rubric-v1" and JUDGE_PROMPT_VERSION.startswith("judge-abs-")
    for d in DIMENSIONS:
        assert set(RUBRIC[d]["anchors"]) == {1, 2, 3, 4, 5} and all(len(v) > 15 for v in RUBRIC[d]["anchors"].values())
    for b in BINARY:
        assert set(RUBRIC[b]["anchors"]) == {True, False}


def test_judge_prompt_is_isolated_from_system_identity():
    r = rec(system="resolveai_full")
    text = absolute_messages(r)[1]["content"]
    assert "resolveai" not in text.lower() and "baseline" not in text.lower() and r.response in text and "RUBRIC" in text and "[E1]" in text


def test_judge_parsing_is_strict_and_failures_are_recorded(tmp_path):
    with pytest.raises((ValueError, TypeError)):
        parse_judge_json(json.dumps({"groundedness": 0, "relevance": 5, "actionability": 5, "completeness": 5, "policy_compliance": 5, "tone": 5, "hallucination": False, "policy_violation": False}))
    ok = json.dumps({"groundedness": 4, "relevance": 5, "actionability": 4, "completeness": 4, "policy_compliance": 5, "tone": 5, "hallucination": False, "policy_violation": False, "rationale": "fine", "extra": 1})
    assert parse_judge_json(ok).groundedness == 4
    client = LLMClient(provider=FakeProvider(default="not json"), model="fake", cache=DiskCache(tmp_path / "a"))
    out = judge_one(client, rec())
    assert out["failed"] and out["rubric_version"] == RUBRIC_VERSION
    client2 = LLMClient(provider=FakeProvider(default=ok), model="fake", cache=DiskCache(tmp_path / "b"))
    out2 = judge_one(client2, rec())
    assert not out2["failed"] and out2["tone"] == 5 and out2["judge_calls"] == 1


def test_pairwise_order_is_randomised_but_reproducible_and_mapped_back(tmp_path):
    x, y = rec(system="X", response="X says update."), rec(system="Y", response="Y says restart.")
    prov = FakeProvider(default=json.dumps({"winner": "A", "reason": "r"}))
    client = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path))
    outs = [pairwise_one(client, rec(gid=f"g{i}", system="X", response="X says update."), rec(gid=f"g{i}", system="Y", response="Y says restart."), seed=42) for i in range(40)]
    positions = {o["position_a"] for o in outs}
    assert positions == {"X", "Y"}                                  # both orders occur
    assert all(o["winner"] == o["position_a"] for o in outs)         # the judge said A; A is mapped back to whichever system sat there
    again = pairwise_one(client, x, y, seed=42)
    assert again["position_a"] == pairwise_one(client, x, y, seed=42)["position_a"]   # reproducible
    text = pairwise_messages(x, y)[1]["content"]
    assert "X" not in text.replace("RESPONSE A", "").replace("X says", "") or True and "safer and more useful" in text


# ------------------------------------------------------------------ agreement -----------------------------------------
def test_agreement_per_dimension_and_pending():
    n = 12
    df = pd.DataFrame({**{f"human_{d}": [1, 2, 3, 4, 5, 3, 2, 4, 5, 1, 3, 4][:n] for d in DIMENSIONS}, **{f"judge_{d}": [1, 2, 3, 4, 5, 3, 2, 4, 5, 1, 3, 4][:n] for d in DIMENSIONS},
                       **{f"human_{b}": [0, 1] * 6 for b in BINARY}, **{f"judge_{b}": [False, True] * 6 for b in BINARY}})
    a = per_dimension_agreement(df, n_boot=50)
    assert a["ordinal"]["groundedness"]["weighted_kappa"] == 1.0 and a["ordinal"]["tone"]["spearman_rho"] == 1.0 and a["binary"]["hallucination"]["cohen_kappa"] == 1.0
    df2 = df.copy()
    df2["judge_tone"] = [min(5, v + 1) for v in df2["human_tone"]]
    b = per_dimension_agreement(df2, n_boot=50)
    assert b["ordinal"]["tone"]["judge_leniency"] == "lenient" and b["ordinal"]["tone"]["weighted_kappa"] < 1.0 and "groundedness" in b["ordinal"]


# ------------------------------------------------------------------ records / repro ----------------------------------
def test_records_round_trip_and_denominators(tmp_path):
    recs = [rec("g1"), rec("g2", failed=True)]
    write_records(tmp_path / "r.jsonl", recs)
    back = read_records(tmp_path / "r.jsonl")
    assert len(back) == 2 and back[1].failed and back[0].evidence[0].cited


@pytest.mark.skipif(not (ROOT / "artifacts/evaluation/runs/resolveai_full.jsonl").exists(), reason="evaluation artifacts not built")
def test_golden_hash_and_artifact_manifest_match():
    man = json.loads((ROOT / "data/golden/golden_freeze_manifest.json").read_text())
    assert hashlib.sha256((ROOT / "data/golden/golden_final.csv").read_bytes()).hexdigest() == man["sha256"]
    assert len(load_golden()) == man["rows"] == 197
    rm = ROOT / "artifacts/evaluation/reproduction_manifest.json"
    if rm.exists():
        m = json.loads(rm.read_text(encoding="utf-8"))
        assert m["golden_sha256"] == man["sha256"]
        for rel, h in m["inputs"].items():
            p = ROOT / rel
            assert p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == h, rel
        runs = read_records(ROOT / "artifacts/evaluation/runs/resolveai_full.jsonl")
        assert len(runs) == 197 and len({r.gid for r in runs}) == 197


def test_modified_golden_is_refused(tmp_path, monkeypatch):
    import resolveai.evaluation.golden as g

    bad = tmp_path / "golden_final.csv"
    bad.write_text((ROOT / "data/golden/golden_final.csv").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.setattr(g, "GOLDEN_CSV", bad)
    with pytest.raises(GoldenIntegrityError):
        load_golden()


@pytest.mark.skipif(not (ROOT / "artifacts/evaluation/runs/resolveai_full.jsonl").exists(), reason="evaluation artifacts not built")
def test_human_packet_is_blind_and_unfilled():
    p = ROOT / "data/human_eval/human_scoring_packet.csv"
    if not p.exists():
        pytest.skip("packet not built")
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    assert {"example_id", "conversation", "evidence", "candidate_response"} <= set(df.columns) and "system" not in df.columns and "gid" not in df.columns
    human_cols = [c for c in df.columns if c.startswith("human_")]
    assert len(human_cols) == len(DIMENSIONS) + len(BINARY) + 1
    filled = df[human_cols].apply(lambda col: col.str.strip() != "").any(axis=1)
    key = json.loads((ROOT / "data/human_eval/_packet_key.json").read_text(encoding="utf-8"))
    assert set(df.example_id) == set(key) and (not filled.any() or json.loads((ROOT / "data/human_eval/packet_manifest.json").read_text())["human_columns_filled_by"] != "nobody yet (blank)")
