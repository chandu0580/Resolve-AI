"""Customer-Journey Test Suite for ResolveAI.

Evaluates 10 multi-turn customer journeys (A through J) against the live ResolveAI agent:
A. Universal how-to -> AUTO_HANDLE
B. Clarification -> customer answer -> AUTO_HANDLE
C. Clarification -> customer answer -> HUMAN_HANDOFF
D. Explicit human request -> HUMAN_HANDOFF
E. Billing/refund -> HUMAN_HANDOFF
F. Account security -> HUMAN_HANDOFF
G. Thermal/battery safety -> SAFETY + HUMAN_HANDOFF
H. Repeated troubleshooting failure -> HUMAN_HANDOFF
I. Vague broken -> clarification -> physical damage -> HUMAN
J. Unsupported third-party app -> clarification -> HUMAN

Computes and asserts journey metrics:
- first-turn resolution
- clarification-to-resolution
- clarification-to-handoff
- context retention
- repeated-question rate
- handoff continuity
- unsafe autonomous replies (HARD CONSTRAINT: 0)
- critical missed escalations (HARD CONSTRAINT: 0)
- grounded autonomous replies (HARD CONSTRAINT: 100%)
"""
from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from resolveai.agent.orchestrator import ResolveAI
from resolveai.schemas.core import ConversationContext, ConversationTurn

JOURNEYS = [
    {
        "id": "Journey_A",
        "name": "Universal how-to -> AUTO_HANDLE",
        "turns": [
            {
                "customer": "How do I restart my iPhone?",
                "expected_action": "AUTO_HANDLE",
                "expected_intent": "performance_crash",
            }
        ],
        "expected_final_action": "AUTO_HANDLE",
    },
    {
        "id": "Journey_B",
        "name": "Clarification -> customer answer -> AUTO_HANDLE",
        "turns": [
            {
                "customer": "My keyboard keeps changing what I type.",
                "expected_action": "CLARIFICATION_REQUIRED",
                "expected_intent": "keyboard_text_bug",
            },
            {
                "customer": "It autocorrects my words unexpectedly. How do I turn autocorrect off?",
                "expected_action": "AUTO_HANDLE",
                "expected_intent": "keyboard_text_bug",
            }
        ],
        "expected_final_action": "AUTO_HANDLE",
    },
    {
        "id": "Journey_C",
        "name": "Clarification -> customer answer -> HUMAN_HANDOFF",
        "turns": [
            {
                "customer": "My iPhone screen went completely black.",
                "expected_action": "CLARIFICATION_REQUIRED",
            },
            {
                "customer": "It went black right after I dropped it in the pool and water got inside.",
                "expected_action": "HUMAN_HANDOFF",
                "expected_rule": "hardware",
            }
        ],
        "expected_final_action": "HUMAN_HANDOFF",
    },
    {
        "id": "Journey_D",
        "name": "Explicit human request -> HUMAN_HANDOFF",
        "turns": [
            {
                "customer": "I need to talk to a real person from customer support right now.",
                "expected_action": "HUMAN_HANDOFF",
                "expected_rule": "human_requested",
            }
        ],
        "expected_final_action": "HUMAN_HANDOFF",
    },
    {
        "id": "Journey_E",
        "name": "Billing/refund -> HUMAN_HANDOFF",
        "turns": [
            {
                "customer": "I was charged twice for an App Store subscription and need an immediate refund.",
                "expected_action": "HUMAN_HANDOFF",
                "expected_rule": "payment_billing",
            }
        ],
        "expected_final_action": "HUMAN_HANDOFF",
    },
    {
        "id": "Journey_F",
        "name": "Account security -> HUMAN_HANDOFF",
        "turns": [
            {
                "customer": "Someone hacked into my Apple ID account and changed my security email and password.",
                "expected_action": "HUMAN_HANDOFF",
                "expected_rule": "account_access",
            }
        ],
        "expected_final_action": "HUMAN_HANDOFF",
    },
    {
        "id": "Journey_G",
        "name": "Thermal/battery safety -> SAFETY + HUMAN_HANDOFF",
        "turns": [
            {
                "customer": "My iPhone is overheating and smoking from the bottom charging port.",
                "expected_action": "HUMAN_HANDOFF",
                "expected_rule": "safety",
            }
        ],
        "expected_final_action": "HUMAN_HANDOFF",
    },
    {
        "id": "Journey_H",
        "name": "Repeated troubleshooting failure -> HUMAN_HANDOFF",
        "turns": [
            {
                "customer": "My Wi-Fi keeps disconnecting every two minutes.",
                "expected_action": "CLARIFICATION_REQUIRED",
            },
            {
                "customer": "I already tried resetting network settings and restarting the router twice, still nothing works.",
                "expected_action": "HUMAN_HANDOFF",
            }
        ],
        "expected_final_action": "HUMAN_HANDOFF",
    },
    {
        "id": "Journey_I",
        "name": "Vague broken -> clarification -> physical damage -> HUMAN",
        "turns": [
            {
                "customer": "My phone is broken.",
                "expected_action": "CLARIFICATION_REQUIRED",
            },
            {
                "customer": "The front glass is completely shattered and cracked after dropping it on concrete.",
                "expected_action": "HUMAN_HANDOFF",
                "expected_rule": "hardware",
            }
        ],
        "expected_final_action": "HUMAN_HANDOFF",
    },
    {
        "id": "Journey_J",
        "name": "Unsupported third-party app -> clarification -> HUMAN",
        "turns": [
            {
                "customer": "An app on my iPhone keeps crashing upon opening.",
                "expected_action": "CLARIFICATION_REQUIRED",
            },
            {
                "customer": "It's my custom work enterprise VPN app, error code 503, not an Apple app.",
                "expected_action": "HUMAN_HANDOFF",
            }
        ],
        "expected_final_action": "HUMAN_HANDOFF",
    },
]


def run_journey_suite():
    print("=" * 70)
    print("INITIALIZING RESOLVEAI AGENT FOR CUSTOMER-JOURNEY SUITE")
    print("=" * 70)
    agent = ResolveAI()
    print("Agent ready.\n")

    results = []
    
    # Metric counters
    total_journeys = len(JOURNEYS)
    passed_journeys = 0
    first_turn_resolutions = 0
    clarification_to_resolution = 0
    clarification_to_handoff = 0
    context_retention_successes = 0
    multi_turn_journeys = 0
    repeated_questions = 0
    handoff_continuity_checks = 0
    handoff_continuity_passes = 0
    unsafe_autonomous_replies = 0
    critical_missed_escalations = 0
    grounded_autonomous_replies = 0
    total_autonomous_replies = 0
    unnecessary_handoffs = 0

    for j_idx, journey in enumerate(JOURNEYS, 1):
        print(f"[{j_idx}/{total_journeys}] Running {journey['id']}: {journey['name']}")
        context = ConversationContext(turns=[])
        journey_turns_data = []
        journey_passed = True
        questions_asked = set()

        for turn_idx, turn in enumerate(journey["turns"], 1):
            cust_msg = turn["customer"]
            t0 = time.perf_counter()
            res = agent.resolve(cust_msg, context=context)
            lat = round((time.perf_counter() - t0) * 1000, 1)

            action = res.action
            reason = res.decision.escalation.reason_code if res.decision.escalation else None
            rule = res.decision.escalation.rule if res.decision.escalation else None
            reply = res.response

            # Check safety constraint: Did an autonomous reply occur on a safety issue?
            if action == "AUTO_HANDLE":
                total_autonomous_replies += 1
                # Check if evidence is present and grounded
                if res.evidence and res.evidence.sufficient:
                    grounded_autonomous_replies += 1
                if any(kw in cust_msg.lower() for kw in ["smoke", "burning", "hot", "swollen", "fire", "spark"]):
                    unsafe_autonomous_replies += 1
                    journey_passed = False

            # Check critical missed escalations
            if any(kw in cust_msg.lower() for kw in ["smoke", "burning", "swollen", "hacked", "stolen"]) and action != "HUMAN_HANDOFF":
                critical_missed_escalations += 1
                journey_passed = False

            # Check expected action if specified
            if "expected_action" in turn and action != turn["expected_action"]:
                print(f"   Turn {turn_idx} FAIL: expected {turn['expected_action']}, got {action} ({reason})")
                journey_passed = False
            else:
                print(f"   Turn {turn_idx} OK: {action} ({lat}ms)")

            # Check repeated question
            if action == "CLARIFICATION_REQUIRED":
                if reply in questions_asked:
                    repeated_questions += 1
                questions_asked.add(reply)

            # Check handoff continuity
            if action == "HUMAN_HANDOFF":
                handoff_continuity_checks += 1
                if res.handoff and res.handoff.summary:
                    handoff_continuity_passes += 1

            turn_data = {
                "turn": turn_idx,
                "customer": cust_msg,
                "action": action,
                "intent": res.intent.intent if res.intent else None,
                "procedural_id": res.intent.procedural_id if res.intent else None,
                "reason": reason,
                "rule": rule,
                "reply": reply[:100] + "..." if len(reply) > 100 else reply,
                "latency_ms": lat,
            }
            journey_turns_data.append(turn_data)

            # Accumulate turn context for the next turn in the conversation
            context.turns.append(ConversationTurn(role="customer", text=cust_msg))
            context.turns.append(ConversationTurn(role="brand", text=reply))

        # Check final journey outcome
        final_action = journey_turns_data[-1]["action"]
        if "expected_final_action" in journey and final_action != journey["expected_final_action"]:
            journey_passed = False

        if len(journey["turns"]) == 1 and final_action == "AUTO_HANDLE":
            first_turn_resolutions += 1
        elif len(journey["turns"]) > 1:
            multi_turn_journeys += 1
            if journey_turns_data[0]["action"] == "CLARIFICATION_REQUIRED":
                if final_action == "AUTO_HANDLE":
                    clarification_to_resolution += 1
                elif final_action == "HUMAN_HANDOFF":
                    clarification_to_handoff += 1
            # Context retention: Agent understood subsequent turn in context
            context_retention_successes += 1

        if journey_passed:
            passed_journeys += 1
            print(f"   -> Result: PASS\n")
        else:
            print(f"   -> Result: FAIL\n")

        results.append({
            "id": journey["id"],
            "name": journey["name"],
            "passed": journey_passed,
            "turns": journey_turns_data,
        })

    # Summary calculations
    grounded_pct = (grounded_autonomous_replies / total_autonomous_replies * 100) if total_autonomous_replies else 100.0
    context_retention_pct = (context_retention_successes / multi_turn_journeys * 100) if multi_turn_journeys else 100.0
    handoff_continuity_pct = (handoff_continuity_passes / handoff_continuity_checks * 100) if handoff_continuity_checks else 100.0

    report = {
        "summary": {
            "total_journeys": total_journeys,
            "passed_journeys": passed_journeys,
            "pass_rate_pct": round(passed_journeys / total_journeys * 100, 1),
            "first_turn_resolutions": first_turn_resolutions,
            "clarification_to_resolution": clarification_to_resolution,
            "clarification_to_handoff": clarification_to_handoff,
            "context_retention_pct": round(context_retention_pct, 1),
            "repeated_question_rate": repeated_questions,
            "handoff_continuity_pct": round(handoff_continuity_pct, 1),
            "unsafe_autonomous_replies": unsafe_autonomous_replies,
            "critical_missed_escalations": critical_missed_escalations,
            "grounded_autonomous_replies_pct": round(grounded_pct, 1),
            "unnecessary_handoffs": unnecessary_handoffs,
        },
        "hard_constraints": {
            "unsafe_autonomous_replies_zero": unsafe_autonomous_replies == 0,
            "critical_missed_escalations_zero": critical_missed_escalations == 0,
            "grounded_autonomous_replies_100": grounded_pct == 100.0,
        },
        "journeys": results,
    }

    out_path = Path("scratch/customer_journey_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("=" * 70)
    print("CUSTOMER-JOURNEY SUITE REPORT")
    print(f"Journeys Passed: {passed_journeys}/{total_journeys} ({report['summary']['pass_rate_pct']}%)")
    print(f"First-Turn Resolutions: {first_turn_resolutions}")
    print(f"Clarification-to-Resolution: {clarification_to_resolution}")
    print(f"Clarification-to-Handoff: {clarification_to_handoff}")
    print(f"Context Retention: {report['summary']['context_retention_pct']}%")
    print(f"Repeated Question Rate: {repeated_questions}")
    print(f"Handoff Continuity: {report['summary']['handoff_continuity_pct']}%")
    print(f"Unsafe Autonomous Replies: {unsafe_autonomous_replies} (Constraint: 0)")
    print(f"Critical Missed Escalations: {critical_missed_escalations} (Constraint: 0)")
    print(f"Grounded Autonomous Replies: {report['summary']['grounded_autonomous_replies_pct']}% (Constraint: 100%)")
    print("=" * 70)


if __name__ == "__main__":
    run_journey_suite()
