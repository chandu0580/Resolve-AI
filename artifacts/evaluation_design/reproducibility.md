# Reproducibility strategy (target: headline numbers in < 15 min on a laptop, no Kaggle account)

1. **Shipped data**: `data/processed/apple_pairs.csv`-style subsample (~7 MB, fixed seed) and the golden set are committed. The raw 516 MB file is only needed to *rebuild* the subsample (`resolveai ingest`, ~2 min after a kagglehub download that needs no login).
2. **Cached LLM calls**: every LLM request is cached on disk keyed by (model, messages, temperature); the cache directory for the golden-set evaluation is committed (expected < 20 MB). `resolveai reproduce` runs the whole evaluation from cache in ~3–5 min; deleting the cache and setting an API key re-runs it live in ~15–20 min.
3. **Determinism**: temperature 0, fixed seeds for sampling/splits/training, pinned `requirements.txt`, embedding model pinned by name+revision. Bootstrap CIs use a fixed RNG.
4. **Run manifests**: each eval run writes `reports/runs/<timestamp>/` with config hash, package versions, model ids, metrics JSON, per-example predictions and trace ids. The README quotes numbers *from* a committed manifest.
5. **Two-tier README commands**: `make reproduce` (cache, no key) and `make eval-live` (needs key). Both print the same table.
6. **Tests**: `pytest` covers the policy rules, output gates, retrieval fusion, and schema round-trips, so a grader can verify behaviour without the LLM.
7. **Environment**: one `requirements.txt`; optional Dockerfile. Known local quirk: a broken TensorFlow install on the dev machine requires `USE_TF=0`; set in the package init so it never leaks into instructions.
