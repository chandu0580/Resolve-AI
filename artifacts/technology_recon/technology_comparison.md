# Technology comparison, layer by layer

Rule applied throughout: a dependency earns its place only if it does something we would otherwise
have to write *and* that code would be non-trivial or error-prone. "Looks production-grade" is not a reason.

Scale facts that drive every choice: one brand, ~20k shipped pairs (~100k available), messages <= 280 chars,
CPU-only laptop, one LLM API, a grader who will reproduce results in < 15 min and interview the author live.

## 1. Data processing / storage
| option | verdict | why |
|---|---|---|
| pandas + parquet/CSV | **use** | 2.8M-row raw file profiles in ~2 min; processed subsets are < 10 MB. Everyone can read it. |
| polars / DuckDB | no | Faster, but nothing here is slow enough to matter; adds a second dataframe dialect to explain live. |
| SQLite / Postgres | no | No concurrent writers, no relational queries beyond a join. Traces go to JSONL. |

## 2. Intent classification
| option | verdict | why |
|---|---|---|
| keyword rules | baseline only | The "trivial" baseline and weak-label bootstrap. |
| TF-IDF + logistic regression | baseline | The "simple" baseline; strong on this data because vocabulary is very topical. |
| sentence-embedding + logistic regression | **primary** | Calibrated probabilities (needed by the escalation gate), ~1 ms inference, trains in seconds, explainable. |
| SetFit / fine-tuned small transformer | stretch | Likely +2-4 F1, but training data is silver-labelled; gains may be noise. Ablation candidate for "next week". |
| LLM zero/few-shot | comparison + fallback | Compare on golden set; use as second opinion when the classifier is uncertain. Slow and uncalibrated, so never the only path. |

Labelling strategy: golden set is hand-labelled; training set is LLM-silver-labelled (few-shot with the labelling
guide) on ~3-4k kb rows, with a manual check on 100 of them to measure silver label noise. This is a decision-log item.

## 3. Embeddings
| model | dims | notes |
|---|---|---|
| all-MiniLM-L6-v2 | 384 | Already cached offline; fastest; weakest retrieval quality. |
| **bge-small-en-v1.5** | 384 | Materially better retrieval on MTEB than MiniLM at the same size/speed. Default choice. |
| gte-small / e5-small-v2 | 384 | Similar class; no reason to prefer. |
| nomic-embed-text-v1.5 / bge-base | 768 | Better but ~3x slower on CPU; corpus is small enough that quality gain probably won't show on 280-char tweets. Ablation candidate. |
| API embeddings (OpenAI, Voyage) | no | Adds a second paid dependency and breaks offline reproduction. |

Decision is empirical: Phase 1 runs a retrieval sanity eval (same-intent recall@5 on the golden set) for MiniLM vs bge-small and keeps the winner.

## 4. Retrieval
| option | verdict | why |
|---|---|---|
| FAISS IndexFlatIP (exact) | **use** | 20k x 384 floats = 30 MB, exact search in < 1 ms. Approximate indexes solve a problem we don't have. |
| numpy dot product | acceptable | Equivalent at this size; FAISS chosen because it's already installed and serialises cleanly. |
| BM25 (rank_bm25) hybrid | **use** | Product tokens ("iOS 11.1", "Apple Music", "iPhone X") are exact-match signals dense models blur. Reciprocal-rank fusion is 10 lines. |
| Chroma / Qdrant / pgvector / Weaviate | **no** | A vector DB adds a server, a client, persistence semantics and a schema for a static, in-memory, 30 MB corpus. Zero demonstrated purpose. |
| LlamaIndex | **no** | Its value is document loading/chunking/query engines over heterogeneous docs. Our "documents" are one CSV of tweets; the whole retrieval layer is ~80 lines. |

## 5. Reranking
| option | verdict | why |
|---|---|---|
| cross-encoder/ms-marco-MiniLM-L-6-v2 | **use, behind a flag** | ~40 ms for 20 candidates on CPU. Reorders semantically close but topically wrong neighbours. Ablated in eval; kept only if it moves judge scores. |
| bge-reranker-base | alternative | Better but ~4x slower; try only if the small one shows a gain. |
| **outcome-aware rerank (custom)** | **use** | Data-derived: prefer historical replies that were (a) substantive rather than "DM us" and (b) followed by a positive customer follow-up. This is the only thing that makes "grounded in how the brand resolved it" literally true. See dataset_recon/resolution_signal.json. |
| LLM rerank | no | Cost/latency for marginal gain over the above. |

## 6. LLM provider
| option | verdict | why |
|---|---|---|
| GLM-5.2 via Z.ai (`https://api.z.ai/api/paas/v4/`, OpenAI-compatible) | **use** | User has the key. OpenAI SDK with `base_url` means the provider is a config value. |
| Anthropic / OpenAI | swap-in | Same code path; only the base URL and model id change. |
| Local model (Ollama) | no | Not needed; reproduction runs from cached responses, not live calls. |

**Unresolved:** Z.ai's current quick-start lists `glm-5.3` and `glm-5.3-flash`; `glm-5.2` still appears on third-party routers. Phase 1 starts with a 1-call smoke test that also checks JSON-mode support. Sources: [Z.ai quick start](https://docs.z.ai/guides/overview/quick-start), [Requesty model page](https://www.requesty.ai/models/zai/glm-5.2), [apidog guide](https://apidog.com/blog/glm-5-2-api/).

## 7. Agent orchestration
| option | verdict | why |
|---|---|---|
| LangGraph | **no** | Our loop is: classify -> retrieve -> assess risk -> draft -> verify -> decide -> (one redraft if verification fails) -> emit. That is a DAG with a single conditional retry. LangGraph's value (persistent checkpoints, parallel branches, human-in-the-loop interrupts across processes, streaming) is unused here, and it makes "explain your code live" harder because control flow lives in a framework. |
| LangChain / CrewAI / AutoGen | no | Same argument, more abstraction. |
| **custom typed state machine** | **use** | A pydantic `AgentState`, an ordered list of `Step` callables, each step appends a trace span. ~150 lines, fully unit-testable, and the interviewer can read it top to bottom. |

Trigger to revisit: if Phase 2 needs multi-turn memory across sessions with resumable checkpoints, LangGraph becomes justified.

## 8. Evaluation
| option | verdict | why |
|---|---|---|
| Ragas | **no** | Its metrics (faithfulness, context precision/recall) assume QA over documents with a ground-truth answer. Our grounding target is "consistent with how the brand historically responded", and the reference replies are themselves noisy (52% "DM us" for Apple). We'd end up overriding every metric. |
| DeepEval | no | Nice pytest integration, but the custom rubric + human-agreement study is the actual deliverable; the framework would wrap ~100 lines of our own code. |
| promptfoo | no | YAML-driven prompt comparison; we need Python-level access to retrieval and policy outputs. |
| **custom harness**: scikit-learn metrics, scipy bootstrap CIs, own LLM-judge with rubric, Cohen's kappa vs human | **use** | Every number is one function the author wrote and can defend. |

Sources reviewed: [DeepEval comparison](https://deepeval.com/blog/top-5-llm-evaluation-frameworks), [Braintrust on DeepEval alternatives](https://www.braintrust.dev/articles/deepeval-alternatives-2026), [MLM on eval frameworks](https://machinelearningmastery.com/llm-evaluation-frameworks-compared-how-to-actually-measure-what-your-model-does/).

## 9. Tracing / observability
| option | verdict | why |
|---|---|---|
| LangSmith | **no** | SaaS, LangChain-oriented, adds an account + key for graders. |
| Langfuse (self-host) | no | Needs Postgres + ClickHouse; disproportionate. |
| Arize Phoenix | optional later | Single local process, OpenTelemetry-native. Reasonable *if* someone wants a UI; not needed for the deliverable. |
| MLflow | **no** | We have no hyper-parameter sweeps; eval runs are versioned as JSON files under `reports/runs/`. |
| **built-in structured traces** | **use** | Every agent run writes one JSON record: per-step inputs/outputs, latency, tokens, retrieved ids, gate verdicts, final decision. A `trace show <run_id>` CLI renders it. This is what the failure analysis is written from. |

Sources reviewed: [SigNoz comparison](https://signoz.io/comparisons/llm-observability-tools/), [Langfuse vs Phoenix](https://langfuse.com/resources/engineering/best-phoenix-arize-alternatives), [MarkTechPost roundup](https://www.marktechpost.com/2026/08/09/top-llm-observability-and-evaluation-platforms-in-2026-langfuse-langsmith-braintrust-arize-and-more-compared/).

## 10. Serving / CLI
| option | verdict | why |
|---|---|---|
| FastAPI + uvicorn | **use** | Already installed; shares pydantic models with the agent; `/resolve`, `/health`, `/trace/{id}`. |
| Typer CLI | **use** | `resolveai ingest / build-kb / run / eval / reproduce / trace`. |
| Streamlit / Gradio demo | no | Not a deliverable; the API + CLI demonstrate the agent. |
| Docker | optional | A Dockerfile is cheap insurance for "runs on the grader's machine", but the primary path stays `pip install -r requirements.txt`. |

## Embedding/reranker sources
[BentoML embedding guide](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models), [PremAI MTEB ranking](https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/), [Tensoria benchmark](https://tensoria.fr/en/blog/embedding-models-2026-guide).
