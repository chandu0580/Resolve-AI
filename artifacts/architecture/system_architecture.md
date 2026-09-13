# ResolveAI system architecture (proposed, Phase 0)

## Goals restated
Given one customer message (plus any prior turns), produce a structured outcome that a support lead would
trust: the intent, a reply drafted in the brand's voice grounded in how the brand actually resolved similar
issues, and an auditable auto-handle / escalate decision with a reason. Every run must be traceable and
every number about the system must be reproducible.

## Component map
```
                        +----------------------------------------------+
  raw twcs.csv -------> | 1. Ingestion & Conversation Reconstruction   |--> pairs.csv (kb / holdout)
                        |   thread graph, pairing, cleaning, splits,   |--> outcome labels (resolved?)
                        |   outcome derivation, subsampling            |
                        +----------------------------------------------+
                                          |
                                          v
                        +----------------------------------------------+
                        | 2. Knowledge Base                             |  embeddings + FAISS + BM25
                        |   historical (message -> reply, outcome)      |  rebuilt in < 1 min
                        +----------------------------------------------+
                                          |
 customer message -+                      v
 + context --------+->+--------------------------------------------------------------------+
                      | 3. Agent loop  (typed AgentState, ordered steps, one retry branch) |
                      |                                                                    |
                      |  a. normalise   -> clean text, detect language, strip PII          |
                      |  b. input gates -> safety / language / abuse / empty  (Trust layer)|
                      |  c. classify    -> intent + calibrated confidence (+LLM 2nd opinion|
                      |                    when confidence < tau)                          |
                      |  d. retrieve    -> hybrid search, outcome-aware rerank, top-k      |
                      |  e. assess risk -> LLM extracts RiskFlags (private info, legal,    |
                      |                    repeat contact, damage, frustration, actionable)|
                      |  f. plan        -> response strategy: troubleshoot / clarify /     |
                      |                    canned / handoff                                |
                      |  g. draft       -> LLM writes reply from strategy + evidence       |
                      |  h. output gates-> verifier: grounded? no promises? length? tone?  |
                      |                    URL whitelist? (Trust layer) -> fail => redraft |
                      |                    once -> still failing => force escalate         |
                      |  i. decide      -> deterministic policy over intent, flags, gates  |
                      |  j. emit        -> AgentResult + HandoffPacket (if escalated)      |
                      +--------------------------------------------------------------------+
                                          |
                     +--------------------+---------------------+
                     v                    v                     v
              4. Observability      5. Interfaces          6. Evaluation harness
              JSONL trace/run       Typer CLI, FastAPI     golden set, baselines,
              per-step spans        /resolve /trace        judge, kappa, failure dump
```

## 1. Ingestion & conversation reconstruction
- Parse the raw CSV; build the parent->child graph using `in_response_to_tweet_id` (99.8% consistent with `response_tweet_id`; 3.9k orphan references dropped).
- A **pair** = (customer tweet, brand reply that answers it). Context = up to 4 prior turns walked up the parent chain.
- **Outcome label** per pair, derived from what the customer said *after* the reply: `positive` (thanks/worked/fixed), `negative` (still/didn't work/already tried), `none`. This is what makes retrieval "resolution-aware".
- Splits are **temporal**: KB = everything before the cutoff, holdout = last N days. Row order and tweet_id are *not* chronological (Spearman 0.33), so any id/row split is silently random.
- Ship a fixed-seed ~20k subsample; the full processed file is rebuilt locally from the raw CSV by one command.

## 2. Knowledge base
- Index over *customer messages*; payload is the brand's real reply, its outcome label, DM-handoff flag, tweet ids.
- Hybrid dense (bge-small) + BM25, fused by reciprocal rank. Rerank: outcome-aware score = similarity x (1 + bonus_substantive + bonus_positive_followup - penalty_dm). Optional cross-encoder behind a flag.
- Corpus excludes pure "DM us" one-liners as *grounding* evidence but keeps them as *statistics* (per-intent DM prior feeds the policy).

## 3. Agent loop
- `AgentState` (pydantic) carries everything; each `Step` is a pure function `state -> state` that also appends a span. Steps are listed in one place; the only branch is the single redraft after a failed output gate.
- LLM is used in exactly three places: risk-flag extraction, drafting, and optional second-opinion classification. Everything that *decides* is deterministic Python so it can be unit-tested and explained.
- Response strategies (planner) are a small enum chosen by rules: `troubleshoot` (known steps exist in evidence), `clarify` (intent clear, device/version unknown), `canned` (non-English, thanks), `handoff` (escalated: reply is a warm handoff line, not a solution).

## Trust / Policy layer (explicit, separate module)
Input gates (before any LLM call):
- Safety: self-harm / threat lexicon + LLM flag => escalate immediately with a fixed compassionate reply template.
- Language: non-English => canned redirect (as the brand historically does).
- Empty / emoji-only / pure abuse with no issue => clarify or handoff.

Output gates (after drafting):
- Groundedness: every concrete instruction in the draft must appear in the retrieved evidence or in a whitelisted step list (restart, update, settings paths, official help URLs). Checked by an LLM verifier call *and* a lexical URL/claim check.
- No commitments: refunds, replacements, timelines, "we will fix" are forbidden phrases.
- Format: <= 280 chars, no @-mentions, no invented URLs, brand tone.
- Privacy: never ask for passwords, card numbers; may ask to DM.

Decision policy: ordered rules (safety -> legal -> intent class -> private-info/damage -> repeat contact -> low confidence -> frustrated-vague -> default auto). First matching rule wins; rule name is returned. Per-intent historical DM rate is a documented prior, not a rule.

Handoff packet (when escalated): intent, confidence, risk flags, one-line summary, suggested opening line, top-3 evidence replies, the rule that fired. This is what a human agent would actually receive.

## 4. Observability
One JSON record per run: run_id, timestamp, config hash, model ids, per-step spans (inputs hash, outputs, latency ms, tokens if LLM), gate verdicts, final decision. `resolveai trace show <run_id>` pretty-prints. Eval runs reference trace ids so every failure in the report links to a full trace.

## 5. Interfaces
- CLI (Typer): `ingest`, `build-kb`, `resolve "<text>"`, `batch <file>`, `eval`, `reproduce`, `trace show`.
- API (FastAPI): `POST /resolve`, `GET /trace/{id}`, `GET /health`. Same pydantic models.

## 6. Evaluation harness
See `evaluation_design/evaluation_strategy.md`.

## What is deliberately out of scope
Multi-session customer memory, actually sending tweets, actual DM handling, image attachments (many tweets reference screenshots we cannot see), non-English support beyond redirect, fine-tuning the LLM.
