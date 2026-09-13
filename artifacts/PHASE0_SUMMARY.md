# ResolveAI Phase 0: System & Data Reconnaissance -- summary for review

Status: complete. No production agent code was written in this phase. All scripts are under `scripts/phase0/`
and every number below is regenerable from the raw Kaggle file (downloadable with kagglehub, no account).

## 1. Dataset profile (details: `dataset_recon/dataset_profile.md`)
2.81M tweets, 108 brands, 800k reconstructed threads, effectively **Oct - 3 Dec 2017**. Customers anonymised
to numeric ids, brands keep handles. Thread graph is 99.8% self-consistent; 3.9k orphan links. Median thread
2 tweets, p99 15, with viral mega-threads up to 1,390. Half of inbound tweets are follow-ups, not first contact.
`tweet_id` is **not** chronological (Spearman 0.33 with time).

## 2. Data-quality findings (details: `dataset_recon/data_quality_findings.md`)
15 findings, each mapped to a design consequence. The ones that change the architecture: URLs and images are
unrecoverable (need a `clarify` strategy); brand replies are 20% verbatim templates (never string-match replies);
agent signatures like `^EC` must be stripped; a weak "was it resolved" label is derivable from the customer's
next turn for ~6-10% of pairs (enables outcome-aware retrieval).

## 3. Leakage risks (details: `dataset_recon/leakage_risks.md`)
Ten risks with measurements and mitigations. Biggest three: id-based splits are secretly random (use temporal);
30% of holdout-period customers were seen earlier (report a customer-disjoint variant); judge and drafter are the
same model family (human kappa study is mandatory).

## 4. Brand ranking (details: `brand_analysis/brand_ranking.md`)
All 108 brands scored on 8 criteria under 6 weightings, then two further checks the numbers can't do: reading real
pairs, and a regex measure of *what kind* of reply each brand gives. Numeric top-3 was Tesco / SpotifyCares /
British_Airways, but those brands resolve by collecting identifiers, so nothing is auto-resolvable.
Only consumer-tech brands have real troubleshooting corpora.

**Recommended: AppleSupport** (largest troubleshooting corpus ~10k replies, 56% handoff so escalation is a real
decision, 106k pairs). Runner-up: AskPlayStation (best auto/escalate balance, 5x smaller).
The earlier informal Apple pick did *not* survive the numeric ranking on its own; it was confirmed only by the
auto-resolvability criterion, and the report will say so.

## 5. Technology comparison and recommended stack (details: `technology_recon/`)
Adopt: pandas/parquet; bge-small embeddings (MiniLM fallback, decided by a Phase-1 retrieval test); FAISS exact +
BM25 with rank fusion; outcome-aware rerank (custom) + optional cross-encoder behind a flag; embedding+LR intent
classifier with TF-IDF and keyword baselines and LLM few-shot comparison; GLM via OpenAI SDK with disk cache;
custom typed state-machine orchestrator; deterministic policy engine; custom eval harness (sklearn, scipy
bootstrap, own judge, Cohen's kappa); JSONL traces + `trace show`; FastAPI + Typer; pytest.

Rejected with stated re-entry triggers: LangGraph, LlamaIndex, any vector DB, Ragas, DeepEval, MLflow,
LangSmith, Langfuse.

## 6. Proposed architecture (details: `architecture/system_architecture.md`)
Six components: ingestion/reconstruction -> knowledge base -> agent loop (10 ordered steps, one redraft branch)
-> observability -> interfaces -> evaluation. A separate **Trust/Policy layer** provides input gates (safety,
language, empty/abuse), output gates (groundedness, no commitments, format, privacy), the ordered decision
rules, and a handoff packet for humans. LLM is called in exactly three places (risk flags, draft, optional
second-opinion intent); everything that decides is deterministic Python.

## 7. Evaluation strategy (details: `evaluation_design/`)
Golden set of 150-250 from the temporal holdout, stratified by weak-label intent + multi-turn + short + targeted
edge cases, labelled twice for self-agreement. Headline: intent macro-F1; escalation recall on must-escalate at
fixed precision plus cost-weighted accuracy; reply quality via a 4-dimension judge rubric validated by a 60-example
human study (weighted kappa, pairwise agreement, both-order position test). Two baselines each for intent, reply,
escalation, plus four ablations. Bootstrap CIs everywhere. Five "misleading headline" items already identified.

Reproducibility: shipped subsample + golden set + committed LLM cache; `reproduce` runs from cache in ~5 min,
live re-run ~15-20 min with a key; run manifests with config hash and versions.

## 8. Unresolved decisions (need your call or a Phase-1 experiment)
| # | decision | options | my default if you don't object |
|---|---|---|---|
| 1 | Brand | AppleSupport vs AskPlayStation | AppleSupport |
| 2 | LLM model id | `glm-5.2` (your key) vs `glm-5.3` / `glm-5.3-flash` (what Z.ai docs list now) | smoke-test `glm-5.2`; fall back to 5.3 if not served; flash variant for the judge if cost matters |
| 3 | Training labels for the classifier | LLM silver labels on ~3-4k KB rows (fast, noisy) vs hand-label ~800 (slow, clean) | silver + 100-row manual noise check |
| 4 | Judge model | same GLM as drafter (self-preference bias) vs a second provider | same GLM; disclosed; human kappa carries the credibility |
| 5 | Holdout window | 5 days (7.7k pairs, burst-dominated) vs 14 days | 5 days, plus report label distribution |
| 6 | Embedding model | bge-small vs MiniLM | decided by Phase-1 recall@5 test |
| 7 | Cross-encoder rerank | keep vs drop | decided by ablation on judge score |
| 8 | Escalation ground truth | hand label only vs also use historical DM as weak reference | hand label is truth; DM agreement reported as a secondary number |
| 9 | Pre-existing code | `resolveai/` already has schemas, intents, retrieval, escalation, llm client, ingestion written before this phase | keep as Phase-1 seed and refactor to the architecture; or delete and restart clean. Your call. |
| 10 | Docker | ship a Dockerfile or not | ship, but README primary path is pip |

## Artifact index
```
artifacts/
  PHASE0_SUMMARY.md                     <- this file
  dataset_recon/   dataset_profile.md, dataset_profile.json, data_quality_findings.md,
                   leakage_risks.md, leakage.json, resolution_signal.json, threads.parquet (local only)
  brand_analysis/  brand_stats.csv (108 brands), brand_ranking.csv, ranking_sensitivity.csv,
                   auto_resolvability.csv, brand_ranking.md
  technology_recon/ technology_comparison.md, recommended_stack.md
  architecture/    system_architecture.md
  evaluation_design/ evaluation_strategy.md, reproducibility.md
scripts/phase0/    01_dataset_profile.py ... 06_auto_resolvability.py
```
