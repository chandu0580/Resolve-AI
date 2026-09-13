# Top end-to-end failure modes (golden set, real examples)

Each mode is grounded in golden rows from `artifacts/evaluation/runs/resolveai_full.jsonl`. Frequency counts are over the 197 rows.
Categories: MODEL (a learned or LLM component), RETRIEVAL, POLICY, DATA/TAXONOMY, EVALUATION.

## 1. LLM risk extractor over-raises `needs_private_info`, turning routine troubleshooting into handoffs  (MODEL FAILURE, then POLICY)
- Examples: g068 "WHY DOES MY PHONE DIE ON 25%" (gold battery_power, no escalation) -> flags `['needs_private_info', 'high_frustration']` -> HUMAN_HANDOFF `private_info`;
  g020 "another keyboard glitch. Fix I.T" -> `['needs_private_info']` -> handoff; g088 "why ios 11.1.2 often self rebooting?" -> handoff.
- Expected: clarify or answer (the annotators marked these should_escalate=false); actual: handoff with reason private_info.
- Component: risk-flags-v2 (GLM) sets `needs_private_info` whenever it thinks a version/device would be needed; policy-v3 treats the flag as a hard reason.
- Frequency: 29 of the 87 unnecessary handoffs carry reason private_info (25 with the LLM flag raised; 5 are non-English rows that never reached the canned redirect because private_info precedes it in the policy order).
  The rules-only ablation (`minus_risk_llm`) has 0.3756 handoff rate vs 0.6193 for the full system, with 0 unsafe autonomous replies and escalation recall 0.7297 vs 0.9459.
- Severity: medium (customer gets a human instead of an answer; nothing unsafe). Fix: define `needs_private_info` for the LLM as "the resolution REQUIRES a serial/IMEI/order/case identifier", not "a device detail would help"; move the canned non_english rule ahead of private_info; measure on dev first.

## 2. Two missed escalations: a redaction token and a word-order gap in the deterministic rules  (MODEL FAILURE: rules)
- g157: "...stranded in Thailand without cellular access on my iPhoneX ... case <PHONE> they erroneously transferred my #..." (gold private_info) -> flags `['high_impact', 'high_frustration']`, intent connectivity at confidence 0.2398 -> CLARIFICATION (low_confidence).
  Root cause: the `needs_private_info` rule lists `<PHONE>` inside a `\b(...)\b` group; `\b` cannot match before `<`, so redaction tokens never fire the rule. The LLM did not raise it either.
- g048: "hey can you check the dm i sent!" (gold repeat_contact, guide rule R1) -> flags `[]` -> CLARIFICATION (insufficient_context). The repeat-contact rule matches "sent a dm" but not "dm i sent".
- Frequency: 2 of 37 should-escalate rows (missed-escalation rate 0.0541); both were clarifications, not autonomous replies, so no unsafe text was sent.
- Severity: high for g157 (a private-identifier case handled as a clarification), low for g048. Fix: `(?<!\w)<(PHONE|EMAIL|ORDER_ID|CARD|LONG_ID)>` outside the word-boundary group; add "dm i sent|the dm" to repeat_contact; add both as regression tests. Not applied in this phase (the evaluated system is the frozen Phase 5 system).

## 3. Evidence gate abstains on almost everything; autonomy is confined to one bug  (RETRIEVAL FAILURE / DATA)
- Only 9 autonomous replies (5 grounded troubleshooting + canned); every STRONG verdict on golden is the iOS-11 "I"/"I.T" autocorrect bug. Evidence levels: `{'INSUFFICIENT': 166, 'WEAK': 24, 'STRONG': 7}`.
- Example: g001 "this iOS update SUCKS! Phone freezes literally every 5 minutes" (performance_crash, no escalation): top evidence cosine below the 0.85 support level -> WEAK -> clarification. The KB has hundreds of freezing complaints, but their replies are questions ("which iOS version?"), not instruction-bearing fixes, so no resolution cluster forms.
- Also: g144 and g160 had STRONG evidence for the autocorrect fix but were handed off for repeat_contact (the customer said the earlier fix "didn't last") - correct per the guide, but it shows the gate and the policy pull in opposite directions on the only well-covered issue.
- Frequency: 190 of 197 rows insufficient; 2 STRONG rows not answered.
- Severity: medium (safe, but the product answers 2.5% of troubleshooting requests). Fix: KB coverage beyond the burst (the brand's own replies rarely contain fixes: 52% are DM handoffs) and reply-side curation; not a threshold change.

## 4. `apps_services` bleeds into `data_loss_sync` and `general_complaint`  (MODEL FAILURE: classifier + taxonomy)
- Confusions (gold -> predicted): {('apps_services', 'data_loss_sync'): 4, ('apps_services', 'general_complaint'): 2, ('keyboard_text_bug', 'general_complaint'): 2, ('hardware_damage', 'connectivity'): 1, ('account_store_repair', 'general_complaint'): 1, ('general_complaint', 'account_store_repair'): 1}. apps_services (38 rows, the largest class) has recall 0.7632; e.g. an iCloud Photos/Music sync question is apps_services under rule R2 but embeds next to data_loss_sync rows.
- Component: BGE+LR classifier trained on silver labels (~71% precision) plus the GLM second opinion; the guide's R2 boundary (app-confined vs data) is not learnable from the silver rules.
- Frequency: 30 intent errors of 197 (accuracy 0.8477); 4 are apps_services -> data_loss_sync.
- Severity: low-medium (intent drives the clarifying question and the retrieval query, not escalation). Fix: hand-labelled dev rows for the R2 boundary; DATA/TAXONOMY as much as model.

## 5. The judge cannot yet be trusted as a quality measure  (EVALUATION FAILURE)
- 27 of 802 judge calls failed to parse (hidden-reasoning truncation) and are excluded from means; the primary judge is the same model family as ResolveAI's drafter and B2.
- Hallucination rate on ResolveAI troubleshooting replies per the judge: 0.0 (n=5); on B2 direct-LLM replies: 0.526; on B1 copied historical replies: 0.17.
- Cross-family check (qwen3.8-27b, n=126): {"n": 126, "weighted_kappa": 0.822, "weighted_kappa_ci": [0.701, 0.911], "spearman_rho": 0.76, "spearman_p": 0.0, "exact_agreement": 0.794, "within_one": 0.937, "mean_human": 4.079, "mean_judge": 4.016, "judge_minus_human": -0.063, "judge_leniency": "neutral"}.
- Human agreement: **RATED**. Until the packet is scored, every judge number in this phase is a model's opinion about model outputs.
- Severity: high for any claim about reply quality; none for the deterministic metrics (intent, escalation, autonomy), which do not use the judge.

## Not a failure, but worth naming
- The 7 `vague_hostile` and 5 `safety` handoffs on gold non-escalate rows are the LLM risk flags reading frustration as abuse or danger ("dead phone", "kill my battery"); the policy takes the safe side by design.
