"""Dataset manifest and golden freeze manifest are present, complete and consistent with the files they describe."""
import hashlib
import json

import pytest

from resolveai import config

DM = config.PROCESSED_DIR / "dataset_manifest.json"
GM = config.GOLDEN_DIR / "golden_freeze_manifest.json"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.skipif(not DM.exists(), reason="run python -m resolveai.data.manifest")
def test_dataset_manifest_complete_and_hashes_match():
    m = json.loads(DM.read_text(encoding="utf-8"))
    for k in ("source", "brand", "preprocessing_version", "seed", "row_counts", "split_boundaries", "pii", "artifacts"):
        assert k in m, k
    assert m["brand"] == config.BRAND and m["seed"] == config.SEED and m["preprocessing_version"] == config.PREPROCESSING_VERSION
    assert m["row_counts"]["subsample"] == 20000 and m["row_counts"]["subsample_split"] == {"kb": 18000, "holdout": 2000}
    assert m["split_boundaries"]["kb_max_created_at"] < m["split_boundaries"]["holdout_min_created_at"]
    assert m["artifacts"]["apple_pairs.csv"]["sha256"] == sha(config.PROCESSED_DIR / "apple_pairs.csv")


@pytest.mark.skipif(not GM.exists(), reason="golden set not frozen")
def test_golden_freeze_manifest_matches_file_and_records_provenance():
    from resolveai.evaluation import load_golden

    m = json.loads(GM.read_text(encoding="utf-8"))
    assert m["rows"] == 197 and m["guide_version"] == "1.1"
    assert m["sha256"] == sha(config.GOLDEN_DIR / "golden_final.csv")
    assert m["guide_sha256"] == sha(config.GOLDEN_DIR / "ANNOTATION_GUIDE.md")
    assert "not an independent human" in m["annotation"]["provenance_statement"]
    g = load_golden()  # verifies hash on load
    assert len(g) == 197 and g.intent.notna().all() and g.escalation_reason.notna().all()


@pytest.mark.skipif(not GM.exists(), reason="golden set not frozen")
def test_modified_golden_is_detected(tmp_path, monkeypatch):
    from resolveai.evaluation import GoldenIntegrityError, golden

    tampered = tmp_path / "golden_final.csv"
    tampered.write_bytes((config.GOLDEN_DIR / "golden_final.csv").read_bytes() + b"\n")
    monkeypatch.setattr(golden, "GOLDEN_CSV", tampered)
    with pytest.raises(GoldenIntegrityError):
        golden.load_golden()


def test_the_documented_policy_rule_count_matches_the_code():
    """Docs and reports quote "N ordered rules"; a stale N is the kind of detail an interviewer spots. This keeps every
    committed mention equal to len(POLICY_RULES)."""
    import re
    from pathlib import Path

    from resolveai.policy.escalation import POLICY_RULES

    root = Path(__file__).resolve().parents[1]
    n = len(POLICY_RULES)
    pat = re.compile(r"\b(\d+) ordered (?:deterministic )?(?:policy )?rules\b|\bnumber \d+ of (\d+)\b|\bthe last of (\d+) ordered\b")
    wrong = []
    for f in [root / "README.md", *(root / "docs").glob("*.md"), *(root / "artifacts" / "final").glob("*.md"), *(root / "artifacts" / "product").glob("*.md")]:
        for m in pat.finditer(f.read_text(encoding="utf-8")):
            got = next(g for g in m.groups() if g)
            if int(got) != n:
                wrong.append(f"{f.relative_to(root)}: {m.group(0)!r} (policy has {n})")
    assert not wrong, wrong
