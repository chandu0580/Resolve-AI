/**
 * API types. Everything the FastAPI service types in OpenAPI is re-exported from the generated schema (npm run gen:api), so the
 * UI never guesses a response shape. The three endpoints that return plain dictionaries (evaluation summary, config, demo
 * scenarios) are declared below from the JSON the backend actually serves; tests parse the captured responses against them.
 */
import type { components } from "./schema";

type S = components["schemas"];

/**
 * Response bodies. Pydantic fields with defaults (including default_factory lists) are optional in the generated schema, but
 * FastAPI serializes every field of a response model, defaults included. Responses are therefore typed with every property
 * present (null stays null); tests/api-contract.test.ts checks this against real captured responses.
 */
type Serialized<T> = T extends readonly (infer U)[] ? Serialized<U>[] : T extends object ? { [K in keyof T]-?: Serialized<T[K]> } : T;

export type ResolveRequest = S["ResolveRequest"];
export type ResolveResponse = Serialized<S["ResolveResponse"]>;
export type Action = ResolveResponse["action"];
export type Outcome = Serialized<S["OutcomeView"]>;
export type ResponseView = Serialized<S["ResponseView"]>;
export type IntentResult = Serialized<S["IntentResult"]>;
export type EvidenceSet = Serialized<S["EvidenceSet"]>;
export type EvidenceItem = Serialized<S["EvidenceItem"]>;
export type EvidenceRef = Serialized<S["EvidenceRef"]>;
export type ResolutionCandidate = Serialized<S["ResolutionCandidate"]>;
export type RiskFlags = Serialized<S["RiskFlags"]>;
export type VerificationResult = Serialized<S["VerificationResult"]>;
export type ClarificationPacket = Serialized<S["ClarificationPacket"]>;
export type HandoffPacket = Serialized<S["HandoffPacket"]>;
export type HistoricalExample = Serialized<S["HistoricalExample"]>;
export type RuntimeVersions = Serialized<S["RuntimeVersions"]>;
export type AgentTrace = Serialized<S["AgentTrace"]>;
export type TraceEvent = Serialized<S["TraceEvent"]>;
export type TraceSummary = Serialized<S["TraceSummary"]>;
export type TraceListResponse = Serialized<S["TraceListResponse"]>;
export type ReadinessResponse = Serialized<S["ReadinessResponse"]>;
export type HealthResponse = Serialized<S["HealthResponse"]>;
export type ErrorBody = Serialized<S["ErrorBody"]>;

export interface Bootstrap {
  point: number;
  ci_low: number;
  ci_high: number;
  n: number;
  n_boot: number;
  seed: number;
}

export interface CostLatency {
  n: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  llm_calls_per_message: number;
  live_calls_per_message: number;
  tokens_in_per_message: number;
  tokens_out_per_message: number;
  estimated_cost_usd_per_message: number;
  failed_calls: number;
}

export interface Headline {
  system: string;
  n: number;
  golden_sha256: string;
  intent_accuracy: Bootstrap;
  intent_macro_f1: Bootstrap;
  escalation_recall: Bootstrap;
  escalation_f1: Bootstrap;
  escalation_precision: number;
  missed_escalations: number;
  false_escalations: number;
  auto_handle_rate: number;
  clarification_rate: number;
  handoff_rate: number;
  safe_auto_handle_rate: Bootstrap;
  safe_auto_handle_count: number;
  unsafe_auto_handle_count: number;
  grounded_auto_handle_count: number;
  judge: Record<string, number> | null;
  judge_hallucination_rate: number | null;
  cost_latency: CostLatency;
  caveat: string;
}

export interface SystemSummary {
  description: string;
  intent: { accuracy: number; macro_f1: number };
  escalation: { precision: number; recall: number; f1: number; fp: number; fn: number };
  autonomy: {
    auto_handle_rate: number;
    clarification_rate: number;
    handoff_rate: number;
    safe_auto_handle_count: number;
    unsafe_auto_handle_count: number;
    grounded_auto_handle_count: number;
    correct_non_autonomous_count: number;
    unnecessary_non_autonomous_count: number;
  };
  cost_latency: CostLatency;
  judge: Record<string, number> | null;
}

export interface PairwiseResult {
  n: number;
  judge_failures: number;
  win: number;
  tie: number;
  loss: number;
  win_rate: number | null;
  loss_rate: number | null;
  question: string;
}

export interface JudgeSystemQuality {
  n_scored: number;
  n_parsed: number;
  judge_failures: number;
  means: Record<string, number | null>;
  bootstrap: Record<string, Bootstrap | null>;
  rates: Record<string, number | null>;
  by_response_kind?: Record<string, Record<string, number>>;
}

export interface EvaluationSummary {
  headline: Headline;
  systems: Record<string, SystemSummary>;
  pairwise_judge: Record<string, PairwiseResult>;
  human_study: string | null;
  caveats: string;
  agreement?: { human?: { status?: string; n_examples?: number; n_fully_rated?: number }; cross_family?: { n?: number; note?: string } };
  retrieval?: {
    same_resolution_recall: { protocol: string; phase2_customer_index_gate_v2: Record<string, number>; phase5_pair_rerank_gate_v3: Record<string, number> };
    resolution_bearing_rank: { definition: string; phase2_customer_index: Record<string, number>; phase5_pair_rerank: Record<string, number> };
    same_intent_retrieval: { phase2: number; phase5: number; definition: string };
    evidence_sufficiency_agent_run: { levels: Record<string, number>; sufficient_rate: number };
    gate_precision_estimate: { source: string; chosen: string; table: Record<string, { n_sufficient: number; coverage: number; precision_resolves_or_partial: number | null }> };
    coverage: Record<string, number>;
    limitations: string[];
  };
  reply_quality?: { primary: { judge_model: string; systems: Record<string, JudgeSystemQuality> }; rubric_version?: string };
  misleading_headline_md?: string;
  statistical_uncertainty_md?: string;
  provenance?: { golden_rows: number; golden_sha256: string; source: string };
}

export interface DemoScenario {
  id: string;
  title: string;
  llm: "live" | "any" | "unavailable";
  description: string;
  conversation: { role: "customer" | "brand"; text: string }[];
  expect: {
    action?: Action;
    not_action?: Action;
    reason_code_in?: string[];
    max_llm_calls?: number;
    evidence_sufficient?: boolean;
    has_citations?: boolean;
    has_handoff?: boolean;
    has_clarification?: boolean;
    question_excludes?: string[];
  };
}

export interface RuntimeConfig {
  service: {
    env: string;
    cors_origins: string[];
    use_llm: boolean;
    write_traces: boolean;
    trace_store: { kind: string; dir: string };
    rate_limit_per_minute: number;
    read_rate_limit_per_minute?: number;
    rate_limit_scope?: string;
    auth?: { required: boolean; scheme: string };
    queue_timeout_s?: number;
    request_budget_s?: number;
    max_queue: number;
    docs_enabled: boolean;
    limits: { max_body_bytes: number; max_message_chars: number; max_turn_chars: number; max_turns: number; max_total_chars: number };
  };
  llm: { configured: boolean; enabled: boolean; model: string; provider: string; temperature: number; timeout_s: number; max_retries: number };
  embedding_model: string;
  brand: string;
  agent_state: string;
  versions?: RuntimeVersions;
}

/* ---------------------------------------------------------------- /evaluation/release (frozen release artifacts, served as stored) */

export interface MetricCell {
  resolveai: number | null;
  baseline: number | null;
  resolveai_ci?: Bootstrap | null;
  difference?: { difference: number; ci_low: number; ci_high: number; interval_excludes_zero: boolean } | null;
  n_resolveai?: number;
  n_baseline?: number;
  n_paired?: number;
}

export interface PerfStat {
  n: number;
  p50: number | null;
  p95: number | null;
  p99: number | null;
  max: number | null;
  mean: number | null;
}

export interface PerfProfile {
  n: number;
  total_ms: PerfStat;
  stages_ms: Record<string, PerfStat>;
  mean_llm_calls: number;
  live_calls_total: number;
  cache_hit_rate: number | null;
  cost_usd_per_request: { mean: number; p50: number; p95: number };
  timeouts: number;
  retries: number;
  budget_exhausted: number;
  model_drafted_and_verified: number;
  actions: Record<string, number>;
}

export interface IntentReleaseRow {
  intent: string;
  rows: number;
  evidence_levels: Record<string, number>;
  sufficient_share: number;
  auto_handled: number;
  clarifications: number;
  handoffs: number;
  handoff_share: number;
  unnecessary_handoffs: number;
  missed_escalations: number;
  top_reasons: Record<string, number>;
  knowledge_gap_candidate: boolean;
  examples: { gid: string; action: string; reason_code: string; evidence_level: string; message: string }[];
}

export interface JudgeBlock {
  n: number;
  n_both_parsed: number;
  hallucination_flags_phase9: number;
  hallucination_flags_release: number;
  groundedness_mean_phase9: number | null;
  groundedness_mean_release: number | null;
  judge_failures_phase9: number;
  judge_failures_release: number;
}

export interface FailureModes {
  n: number;
  unnecessary_handoffs: { total: number; by_reason_code: Record<string, number>; examples: Record<string, { gid: string; message?: string; [k: string]: unknown }[]> };
  missed_escalations: { gid: string; gold_reason: string; action: string; reason_code: string; risk_flags: string[]; message: string }[];
  evidence_levels: Record<string, number>;
  strong_evidence_rows: { gid: string; intent_gold: string; action: string; reason_code: string; message: string }[];
  autonomous_replies: { gid: string; kind: string; intent_gold: string }[];
  intent_errors: number;
  top_intent_confusions: { gold: string; predicted: string; count: number }[];
  judge_flagged_templates: { text: string; hallucination_flags: number }[];
  non_english_rows_handed_off: { gid: string; reason_code: string; message: string }[];
}

export interface ReleaseEvaluation {
  golden: {
    dataset: string;
    release: {
      version: string;
      pipeline_version: string | null;
      config_hash: string | null;
      run_at: string | null;
      n: number;
      golden_sha256: string;
      n_boot: number;
      seed: number;
      failed_rows: number | null;
      model_calls: number | null;
    };
    table: Record<string, Record<string, MetricCell>> | null;
    evidence_levels: Record<string, number> | null;
    autonomous_replies: { gid: string; kind: string; safe: string }[] | null;
    missed_escalations: unknown;
    retrieval_same_resolution_recall_at_5: Record<string, number> | null;
    decision_changes_vs_phase9_final: unknown;
    human_evaluation: { packet_rows: number; fully_rated_rows: number; status: string } | null;
    failure_modes: FailureModes | null;
    judge_attribution: {
      n: number;
      identical_responses: JudgeBlock;
      changed_responses: JudgeBlock;
      changed_by_kind_transition: Record<string, JudgeBlock & { gids: string[] }>;
      release_hallucination_flags_by_response_kind: Record<string, { flags: number; parsed: number }>;
    } | null;
    by_intent: { dataset: string; n: number; gap_rule: { min_rows: number; max_sufficient_share: number; min_handoff_share: number }; by_intent: IntentReleaseRow[]; note: string; source: string } | null;
  };
  dev_experiments: {
    dataset: string;
    risk_corroboration: {
      decision: { candidate: string; accepted: boolean; risk_corroborate: string[]; decision: string; evidence: string[]; labels: string; preregistration_sha256: string; golden_touched: boolean };
      report: {
        n_dev_rows: number;
        n_labelled_rows: number;
        labels_provenance: string;
        live_model_calls: number;
        status: string;
        model: { calls: number; fallback_rate: number; rows_model_raised_needs_private_info: number; of_which_rule_corroborated: number };
        outcomes_240: Record<string, Record<string, number>>;
        scores_on_labelled_rows: Record<string, { tp: number; fp: number; fn: number; tn: number; precision: number; recall: number; f1: number; auto_candidates_on_should_escalate_rows: number }>;
      } | null;
    } | null;
  };
  performance: {
    dataset: string;
    protocol: string;
    machine_note: string;
    price_per_million_tokens_usd: { input: number; output: number; note: string };
    live_draft_selection: { scanned: number; selected: number; rule: string };
    profiles: Record<string, PerfProfile>;
  } | null;
  checks: {
    adversarial_suite: { n_cases: number; passed: number; failed: number; model: string } | null;
    api_smoke: { profile: string; n_checks: number; passed: number; failed: number } | null;
    verification: { passed: boolean; started: string; golden: { verified: boolean; rows: number; sha256: string }; frozen_artifacts: Record<string, number | boolean>; security_scan: Record<string, unknown> } | null;
    clean_environment: { mode: string; passed: boolean; failed_steps: unknown; os: string } | null;
  };
  limitations: string[];
  provenance: { source: string; text: string };
}

/* ---------------------------------------------------------------- /agent/profile (read-only configuration) */

export interface PolicyRule {
  rule: string;
  reason_code: string;
  outcome: "handoff" | "clarify" | "clarify_or_handoff" | "template_reply" | "auto_reply";
  when: string;
}

export interface AgentProfile {
  agent: { name: string; state: string; brand: string; versions: RuntimeVersions; model: { configured: boolean; enabled: boolean; name: string | null; role: string } };
  active: {
    label: string;
    agent_config: Record<string, unknown>;
    retrieval: Record<string, unknown>;
    evidence_gate: Record<string, unknown>;
    rerank_weights: Record<string, unknown>;
    second_opinion_policy: string;
    request_budget_s: number | null;
  };
  evaluated: {
    label: string;
    source: string;
    agent_config: Record<string, unknown> | null;
    pipeline_version: string | null;
    config_hash: string | null;
    differences: { field: string; active: unknown; evaluated: unknown; note: string | null }[];
  };
  policy: {
    version: string;
    confidence_floor: number;
    always_handoff_intents: string[];
    brand_turns_without_progress: number;
    clarifiable_evidence_reasons: string[];
    rules: PolicyRule[];
    order: string;
  };
  allowed_actions: { action: Action; label: string; response_kinds: string[]; requires: string }[];
  not_allowed: string[];
}

/* ---------------------------------------------------------------- /knowledge/summary (aggregates only) */

export interface KnowledgeSummary {
  dataset: string;
  rows: number;
  substantive: number | null;
  dm_handoff: number | null;
  resolution_bearing: number;
  resolution_bearing_substantive: number | null;
  date_range: { min: string | null; max: string | null };
  by_weak_intent: { intent: string; rows: number; resolution_bearing: number; resolution_bearing_share: number; dm_handoff_share: number | null }[];
  reply_action_classes: Record<string, number>;
  outcome_signals: Record<string, number>;
  manifest: Record<string, string | number | null>;
  indexes: { dense: string[]; embedding_model: string; search_path: string[] };
  definitions: Record<string, string>;
  source: string;
}
