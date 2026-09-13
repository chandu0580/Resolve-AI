# Recommended stack

| layer | choice | one-line reason |
|---|---|---|
| language / runtime | Python 3.11+ (3.13 works locally) | ecosystem; grader familiarity |
| data | pandas, parquet, one shipped CSV subsample | nothing here is big |
| intent | bge-small embeddings -> logistic regression (calibrated); TF-IDF+LR and keyword rules as baselines; LLM few-shot as comparison/fallback | calibrated confidence feeds the policy gate |
| embeddings | `BAAI/bge-small-en-v1.5` (MiniLM fallback, decided by Phase-1 retrieval eval) | best quality at 384-d CPU speed |
| retrieval | FAISS exact + BM25, reciprocal-rank fusion | product tokens need lexical match |
| rerank | outcome-aware heuristic (substantive + positive follow-up) + optional cross-encoder behind a flag | makes "historically resolved" literal |
| LLM | GLM-5.2 (or 5.3, to confirm) via OpenAI SDK + disk cache | user's key; provider is config |
| orchestration | custom typed state machine (`AgentState` + ordered steps) | readable, testable, no framework tax |
| trust / policy | deterministic rule engine over LLM-extracted risk flags + output verifier | auditable decisions |
| evaluation | custom harness: sklearn, scipy bootstrap, LLM judge, Cohen's kappa | every number is defensible |
| observability | JSONL traces with per-step spans + `trace show` CLI | enough to write the failure analysis |
| serving | FastAPI + Typer | already installed, shares schemas |
| tests | pytest on policy rules, gates, retrieval, schemas | policy layer must be unit-tested |

Explicitly **not** adopted (with the trigger that would change the answer):
- LangGraph: revisit if multi-session resumable state is needed.
- LlamaIndex: revisit if heterogeneous documents (help-centre articles, PDFs) join the KB.
- Vector DB: revisit above ~1M vectors or with concurrent writers.
- Ragas / DeepEval: revisit if a standard document-QA faithfulness metric becomes the target.
- MLflow / LangSmith / Langfuse: revisit with a team and > 1 concurrent experimenter.

New runtime dependencies this implies beyond what is installed: `rank_bm25`, `typer`, `pytest`. Everything else
(pandas, scikit-learn, sentence-transformers, faiss-cpu, openai, fastapi, pydantic) is already present.
