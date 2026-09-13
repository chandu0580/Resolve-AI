# Verifier block analysis (Phase 5-D, DEV drafts)

12 of 26 drafts were blocked; 12 labelled by an AI annotator.

| label | n |
|---|---|
| FALSE_BLOCK | 5 |
| TRUE_BLOCK | 6 |
| UNCERTAIN | 1 |

TRUE_BLOCK rate 0.5, FALSE_BLOCK rate 0.417, UNCERTAIN 0.083.

By blocking check: `{"llm_support_check": {"FALSE_BLOCK": 5, "TRUE_BLOCK": 3}, "evidence_refs": {"TRUE_BLOCK": 2}, "evidence_coverage": {"TRUE_BLOCK": 1}, "draft_failed": {"UNCERTAIN": 1}}`
By arm: `{"A_v1": {"FALSE_BLOCK": 1, "TRUE_BLOCK": 6}, "B_v2": {"FALSE_BLOCK": 4, "UNCERTAIN": 1}}`
Passed-draft sample: `{"n": 12, "labels": {"TRUE_PASS": 12}}`