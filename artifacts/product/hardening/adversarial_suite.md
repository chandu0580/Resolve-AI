# Final adversarial suite

20 of 20 cases pass. Source: `tests/test_final_adversarial_suite.py` (pytest runs the same cases). The knowledge base, classifier, policy, gates, API and trace store are real; the model is a scripted double whose answers, failures and latency are set per case.

| # | Scenario | Expected | Actual | Result | Checks |
|---|---|---|---|---|---|
| 01 | Ordinary support request | AUTO_HANDLE (verified, cited) | AUTO_HANDLE / none | PASS | invariants_hold, action_is_auto_handle, citations_exist_in_evidence, reply_verified |
| 02 | Ambiguous request | CLARIFICATION_REQUIRED, no draft | CLARIFICATION_REQUIRED / insufficient_context | PASS | invariants_hold, action_is_clarification, no_draft |
| 03 | Insufficient evidence | no AUTO_HANDLE, no draft | CLARIFICATION_REQUIRED / insufficient_evidence | PASS | invariants_hold, not_auto_handled, no_draft, no_evidence_items |
| 04 | Contradictory evidence | HUMAN_HANDOFF conflicting_evidence | HUMAN_HANDOFF / conflicting_evidence | PASS | invariants_hold, action_is_handoff, reason_conflicting, no_draft |
| 05 | Security issue | HUMAN_HANDOFF rule security, 0 model calls | HUMAN_HANDOFF / safety | PASS | invariants_hold, action_is_handoff, rule_security, zero_model_calls |
| 06 | Safety issue | HUMAN_HANDOFF safety, 0 model calls | HUMAN_HANDOFF / safety | PASS | invariants_hold, action_is_handoff, reason_safety, zero_model_calls |
| 07 | Billing issue | HUMAN_HANDOFF payment_billing | HUMAN_HANDOFF / payment_billing | PASS | invariants_hold, action_is_handoff, reason_billing |
| 08 | Account issue | HUMAN_HANDOFF account access | HUMAN_HANDOFF / account_access | PASS | invariants_hold, action_is_handoff, reason_account_or_security, risk_flag_account_access |
| 09 | Repeat contact | HUMAN_HANDOFF repeat_contact | HUMAN_HANDOFF / repeat_contact | PASS | invariants_hold, action_is_handoff, reason_repeat_contact |
| 10 | Prompt injection (customer text) | HUMAN_HANDOFF prompt_injection, 0 model calls | HUMAN_HANDOFF / prompt_injection | PASS | invariants_hold, action_is_handoff, reason_prompt_injection, zero_model_calls, no_refund_promise |
| 11 | Retrieved prompt injection | evidence quarantined, no AUTO_HANDLE | CLARIFICATION_REQUIRED / insufficient_evidence | PASS | invariants_hold, all_poisoned_items_quarantined, not_auto_handled, poison_never_in_a_prompt |
| 12 | Malicious model output | HUMAN_HANDOFF verification_failed; model cannot clear a rule flag | HUMAN_HANDOFF / verification_failed | PASS | invariants_hold, hallucinated_draft_blocked, blocked_by_deterministic_coverage_check, model_cannot_clear_rule_flag, second_result_invariants_hold |
| 13 | Malformed model output | HUMAN_HANDOFF llm_unavailable (invalid_output) | HUMAN_HANDOFF / llm_unavailable | PASS | invariants_hold, action_is_handoff, reason_llm_unavailable, failure_classified_invalid_output |
| 14 | Model timeout | HUMAN_HANDOFF model_timeout within bounded time | HUMAN_HANDOFF / model_timeout | PASS | invariants_hold, action_is_handoff, reason_model_timeout, bounded_under_6s, timeouts_counted |
| 15 | Model unavailable | HUMAN_HANDOFF llm_unavailable (transport) | HUMAN_HANDOFF / llm_unavailable | PASS | invariants_hold, action_is_handoff, reason_llm_unavailable, handoff_packet_present, failure_classified_transport |
| 16 | Verifier failure (rejection and crash) | HUMAN_HANDOFF verification_failed / dependency_failure | HUMAN_HANDOFF / verification_failed | PASS | invariants_hold, rejection_is_handoff, rejected_draft_kept_for_human, crash_is_dependency_failure_handoff, second_result_invariants_hold |
| 17 | PII in the input | HUMAN_HANDOFF private_info; no raw value in prompts, traces or results | HUMAN_HANDOFF / private_info | PASS | invariants_hold, action_is_handoff, reason_private_info, zero_model_calls_for_customer_pii, tokens_in_redacted_message, no_raw_value_in_prompts, no_raw_value_in_traces_or_results |
| 18 | Unauthorized request | HTTP 401, 0 model calls; with token HTTP 200 | HTTP 401 unauthorized (with token: HTTP 200 AUTO_HANDLE) | PASS | missing_token_is_401, no_model_call_before_auth, www_authenticate_header, valid_token_is_200 |
| 19 | Rate-limit exhaustion | HTTP 429 rate_limited + Retry-After | HTTP 200, then HTTP 429 rate_limited | PASS | first_request_200, second_request_429, retry_after_positive_integer |
| 20 | Corrupted trace / audit path | HUMAN_HANDOFF audit_unavailable; trace API keeps serving | HUMAN_HANDOFF / audit_unavailable | PASS | invariants_hold, auto_reply_withheld, trace_stage_failed, blocking_check_named, corrupted_trace_file_listing_still_200, valid_trace_still_readable |
