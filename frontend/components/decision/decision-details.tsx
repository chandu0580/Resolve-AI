import { Card, KeyValues, Mono } from "@/components/ui/card";
import { EvidenceSufficiency } from "@/components/decision/evidence-sufficiency";
import { IntentSummary } from "@/components/decision/intent-summary";
import { OutputGateChecklist } from "@/components/decision/output-gate";
import { RiskFlagList } from "@/components/decision/risk-flags";
import type { ResolveResponse } from "@/lib/api/types";
import { activeRiskFlags } from "@/lib/handoff-summary";
import { reasonMeta } from "@/lib/labels";

/** Intent, evidence, risk and policy, then the output gate: the structured inputs behind the banner and the explanation. */
export function DecisionDetails({ result }: { result: ResolveResponse }) {
  const { outcome, intent, evidence, risk } = result;
  return (
    <>
      <div className="grid gap-4 min-[1780px]:grid-cols-2 md:max-xl:grid-cols-2">
        <Card title="Intent" headingLevel={3}>
          <IntentSummary intent={intent} />
        </Card>
        <Card title="Evidence sufficiency" headingLevel={3}>
          <EvidenceSufficiency evidence={evidence} />
        </Card>
        <Card title="Risk" headingLevel={3}>
          <RiskFlagList flags={activeRiskFlags(risk as unknown as Record<string, unknown>)} source={risk.source} />
        </Card>
        <Card title="Policy" headingLevel={3}>
          <KeyValues
            items={[
              { label: "Decision reason", value: reasonMeta(outcome.reason_code).label },
              { label: "Rule that fired", value: <Mono>{outcome.rule}</Mono> },
              { label: "Policy version", value: <Mono>{outcome.policy_version}</Mono> },
              { label: "Automatic reply allowed", value: outcome.autonomous_response_allowed ? "Yes" : "No" },
            ]}
          />
          <p className="mt-3 text-xs text-ink-3">The policy is deterministic code. The model never decides whether to escalate.</p>
        </Card>
      </div>
      <Card title="Output gate" description="An automatic reply requires every check. Anything else becomes a clarification or a handoff.">
        <OutputGateChecklist gate={outcome.output_gate} blocking={outcome.blocking_checks} />
      </Card>
    </>
  );
}
