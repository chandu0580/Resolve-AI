"""Phase 1-D: inter-annotator agreement (v1.0 passes) and the freeze step.

  python scripts/phase1/d_agreement.py            # A vs B agreement on the v1.0 passes -> agreement_report.json
  python scripts/phase1/d_agreement.py --freeze   # golden_adjudicated.csv -> golden_final.csv + golden_freeze_manifest.json

Provenance recorded in the manifest: Annotator B was an isolated AI annotator, not an independent human.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from resolveai import config

G = config.GOLDEN_DIR
LABELS = ["intent", "should_escalate", "escalation_reason"]
FLAGS = ["taxonomy_gap", "insufficient_context", "multi_intent", "evidence_unavailable"]
PROVENANCE = ("Annotator B was an isolated AI annotator, not an independent human. Cohen's kappa must never be described as "
              "human-human agreement; it is evidence of consistency under the annotation guide. Human adjudication of "
              "disagreements is the credibility step.")


def norm_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().map({"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False})


def compare() -> None:
    a = pd.read_csv(G / "golden_annotatorA.csv")
    b = pd.read_csv(G / "golden_annotatorB.csv")
    m = a.merge(b[["gid", *LABELS, "note"]], on="gid", suffixes=("_A", "_B"))
    m["should_escalate_A"], m["should_escalate_B"] = norm_bool(m.should_escalate_A), norm_bool(m.should_escalate_B)
    both = m[m.should_escalate_A & m.should_escalate_B]
    rep = {
        "provenance": PROVENANCE,
        "n": len(m),
        "intent_kappa": round(cohen_kappa_score(m.intent_A, m.intent_B), 3),
        "intent_agreement": round((m.intent_A == m.intent_B).mean(), 3),
        "escalation_kappa": round(cohen_kappa_score(m.should_escalate_A, m.should_escalate_B), 3),
        "escalation_agreement": round((m.should_escalate_A == m.should_escalate_B).mean(), 3),
        "reason_agreement_when_both_escalate": round((both.escalation_reason_A == both.escalation_reason_B).mean(), 3),
    }
    dis = m[(m.intent_A != m.intent_B) | (m.should_escalate_A != m.should_escalate_B)]
    dis[["gid", "context", "customer_message", "intent_A", "intent_B", "should_escalate_A", "should_escalate_B", "escalation_reason_A", "escalation_reason_B", "note_A", "note_B"]].to_csv(
        G / "golden_disagreements.csv", index=False
    )
    rep["disagreements"] = len(dis)
    idis = dis[dis.intent_A != dis.intent_B]
    rep["intent_only_disagreements"] = int(((dis.intent_A != dis.intent_B) & (dis.should_escalate_A == dis.should_escalate_B)).sum())
    rep["escalation_only_disagreements"] = int(((dis.intent_A == dis.intent_B) & (dis.should_escalate_A != dis.should_escalate_B)).sum())
    rep["both"] = int(((dis.intent_A != dis.intent_B) & (dis.should_escalate_A != dis.should_escalate_B)).sum())
    conf = pd.crosstab(idis.intent_A, idis.intent_B).stack()
    rep["intent_confusions"] = {f"{x} -> {y}": int(n) for (x, y), n in conf[conf > 0].sort_values(ascending=False).head(10).items()}
    (G / "agreement_report.json").write_text(json.dumps(rep, indent=2, default=str))
    print(json.dumps(rep, indent=2, default=str))


def sha256_file(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze() -> None:
    adj = pd.read_csv(G / "golden_adjudicated.csv", dtype=str, keep_default_na=False)
    assert len(adj) == 197 and adj.gid.is_unique and adj.customer_tweet_id.is_unique
    assert (adj[LABELS] != "").all().all(), "adjudicated file has empty labels"
    kb = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", usecols=["customer_tweet_id", "split", "created_at"])
    assert not set(adj.customer_tweet_id.astype(int)) & set(kb[kb.split == "kb"].customer_tweet_id), "golden overlaps kb"
    assert pd.to_datetime(adj.created_at).min() > pd.to_datetime(kb[kb.split == "kb"].created_at).max(), "golden not strictly after kb"
    cols = ["gid", "customer_tweet_id", "brand_tweet_id", "created_at", "context", "customer_message", "brand_reply", "n_context_turns",
            "customer_seen_in_kb", *LABELS, *FLAGS, "adjudication_rule", "note"]
    out = adj[cols]
    out.to_csv(G / "golden_final.csv", index=False)
    agreement = json.loads((G / "agreement_report.json").read_text(encoding="utf-8"))
    esc = out.should_escalate.str.lower().eq("true")
    manifest = {
        "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "file": "golden_final.csv",
        "sha256": sha256_file(G / "golden_final.csv"),
        "rows": int(len(out)),
        "guide_version": "1.1",
        "guide_sha256": sha256_file(G / "ANNOTATION_GUIDE.md"),
        "source_split": "holdout (temporal, final 5 days), never in kb",
        "sampling": json.loads((G / "golden_sampling_report.json").read_text(encoding="utf-8")),
        "annotation": {
            "annotator_A": "Claude, main session, guide v1.0",
            "annotator_B": "Claude, isolated agent session given only guide v1.0 + unlabelled rows",
            "provenance_statement": PROVENANCE,
            "v1_0_agreement": {k: agreement[k] for k in ("n", "intent_kappa", "intent_agreement", "escalation_kappa", "escalation_agreement", "reason_agreement_when_both_escalate", "disagreements")},
            "v1_1_adjudication": "scripts/phase1/d2_apply_v11.py (rules R1-R7), diff in golden_v11_diff.csv, report in ADJUDICATION_REPORT.md",
        },
        "label_distribution": {
            "intent": out.intent.value_counts().to_dict(),
            "should_escalate_true": int(esc.sum()),
            "escalation_reason": out[esc].escalation_reason.value_counts().to_dict(),
            "flags": {f: int(out[f].str.lower().eq("true").sum()) for f in FLAGS},
        },
        "invariant": "Frozen. Model development must never modify this file; resolveai.evaluation.golden.load_golden verifies the hash.",
    }
    (G / "golden_freeze_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"frozen golden_final.csv rows={len(out)} sha256={manifest['sha256'][:16]}...")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    if ap.parse_args().freeze:
        freeze()
    else:
        compare()
