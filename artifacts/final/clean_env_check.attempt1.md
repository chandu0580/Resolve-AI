# Clean-clone check: attempt 1 (failed, kept as evidence)

`scripts/final/h_clean_env_check.py` copied the 629 committable files into a new temporary directory. It created a fresh virtual
environment with no `.env`, no `.cache` and an isolated model cache, and installed `requirements-dev.txt`.

| Step | Result | Duration |
|---|---|---|
| git init | OK | 0 s |
| create virtual environment | OK | 35 s |
| `pip install -r requirements-dev.txt` | OK | 984 s |
| `pytest` | **FAIL**: "Interrupted: 14 errors during collection" | 39 s |
| `python -m resolveai demo --no-llm` | **FAIL**: `ModuleNotFoundError: No module named 'rank_bm25'` | 3 s |
| final verification | **FAIL**: `ModuleNotFoundError: No module named 'rank_bm25'` | 18 s |
| `npm ci`, `npm run lint` | OK | 80 s, 110 s |
| typecheck, test, build, API start | not recorded: the run was stopped once the cause was known | — |

**Cause.** `resolveai/retrieval/bm25.py` imports `rank_bm25`, but `requirements.txt` did not declare it. The development machine
had it installed, so no local test could reveal the gap.

**Audit.** An import audit of `resolveai/`, `tests/`, `scripts/evaluate.py` and `scripts/final/` found one more directly imported
but undeclared package: `scipy`. It arrives transitively through scikit-learn, but is now declared explicitly. `starlette` stays
transitive, because FastAPI pins it.

**Fix.** `requirements.txt` now declares `rank-bm25>=0.2.2` and `scipy>=1.11`. The re-run on a new clean copy is recorded in
`clean_env_check.json`.
