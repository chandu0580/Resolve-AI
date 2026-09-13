"""Phase 1-D2: apply annotation-guide v1.1 rules (R1-R7) to BOTH annotator label sets, deterministically.

Nothing is modified in place. Inputs: golden_annotatorA.csv, golden_annotatorB.csv (v1.0 labels).
Outputs (all in data/golden/):
  golden_annotatorA_v11.csv, golden_annotatorB_v11.csv   both passes after v1.1
  golden_adjudicated.csv                                 candidate gold (NOT frozen)
  golden_v11_diff.csv                                    machine-readable: every (gid, field) whose value changed
  ADJUDICATION_REPORT.md                             per-row: A, B, v1.1, rule, resolved?
Every override is listed in ADJUDICATIONS with the rule that justifies it, so the change set is reviewable.
"""
from __future__ import annotations

import pandas as pd

from resolveai import config

G = config.GOLDEN_DIR
REASON_PRIORITY = ["safety", "legal_media", "private_info", "hardware", "repeat_contact", "vague_hostile"]

# gid -> dict(field=value, ...) plus 'rule' and 'why'. Applied identically to A and B.
ADJUDICATIONS: dict[str, dict] = {
    # ---- escalation (R1 / R7) ----
    "g048": dict(should_escalate=True, escalation_reason="repeat_contact", intent="other", insufficient_context=True, rule="R1,R7",
                 why="'the dm I sent' is an explicit prior contact; no underlying issue inferred"),
    "g102": dict(should_escalate=False, escalation_reason="none", rule="R1",
                 why="'force restart didn't work' was stated by a different customer in the thread ('I have the same problem'); current customer states no attempt"),
    "g126": dict(should_escalate=False, escalation_reason="none", rule="R1",
                 why="'3rd time you've deleted my library' is a recurrence, not an attempt or a contact; symptom present so not vague_hostile"),
    "g131": dict(should_escalate=True, escalation_reason="repeat_contact", rule="R1",
                 why="'I try to place it right for many times' is an explicit prior attempt"),
    "g135": dict(should_escalate=False, escalation_reason="none", rule="R1",
                 why="'no chance with any of the usual tricks' is vague; no explicit attempt"),
    "g153": dict(should_escalate=False, escalation_reason="none", insufficient_context=True, rule="R7",
                 why="policy complaint about reset wait; no account problem stated, none inferred"),
    "g191": dict(should_escalate=True, escalation_reason="repeat_contact", rule="R1",
                 why="explicit completion of the brand's suggested step ('all the apps are on their latest version') then 'what's next?'"),
    # ---- intent ----
    "g011": dict(intent="keyboard_text_bug", rule="R5",
                 why="corrupted I-glyph is present in the customer's own text and message refers to 'this glitch'"),
    "g024": dict(intent="connectivity", rule="R3", why="accessory 'not supported'; no physical fault stated"),
    "g029": dict(intent="apps_services", taxonomy_gap=True, rule="R2,R4", why="Cmd+V clipboard = OS feature failure; no dedicated bucket"),
    "g063": dict(intent="general_complaint", insufficient_context=True, rule="R5", why="pop-up is only in the screenshot"),
    "g077": dict(intent="battery_power", multi_intent=True, rule="R6", why="'warm' (overheating) is the only concrete symptom; 'glitchy' is vague"),
    "g085": dict(intent="general_complaint", insufficient_context=True, rule="R5", why="symptom only in the video"),
    "g087": dict(intent="connectivity", rule="R3", why="Beats audio issue, no physical fault stated -> functional category, clarify"),
    "g113": dict(intent="other", insufficient_context=True, rule="R5,R7", why="'Proofreading <url>' states no support request"),
    "g121": dict(intent="apps_services", rule="R2", why="crash confined to the Phone app"),
    "g134": dict(intent="apps_services", rule="R2", why="crash confined to Safari"),
    "g146": dict(intent="general_complaint", taxonomy_gap=True, rule="R4", why="OS security-vulnerability question; no intent genuinely fits"),
    "g148": dict(intent="apps_services", rule="R6", why="requested resolution is iTunes sync, the Wi-Fi is the transport"),
    "g170": dict(intent="general_complaint", taxonomy_gap=True, rule="R4", why="OS security-vulnerability confirmation; no intent genuinely fits"),
    "g171": dict(intent="account_store_repair", escalation_reason="private_info", multi_intent=True, rule="R6",
                 why="main requested resolution is scheduling a service appointment blocked by 2FA; black screen is secondary; reason by priority"),
    # ---- agreed rows that v1.1 nevertheless changes ----
    "g006": dict(intent="apps_services", rule="R2", why="crash confined to the Settings app (both annotators had performance_crash under v1.0)"),
}

# Metadata-only annotations on rows whose labels do not change.
META: dict[str, dict] = {
    "g015": dict(taxonomy_gap=True), "g056": dict(taxonomy_gap=True), "g128": dict(taxonomy_gap=True), "g166": dict(taxonomy_gap=True),
    "g023": dict(multi_intent=True), "g027": dict(multi_intent=True), "g064": dict(multi_intent=True), "g089": dict(multi_intent=True),
    "g110": dict(multi_intent=True), "g114": dict(multi_intent=True), "g117": dict(multi_intent=True), "g154": dict(multi_intent=True),
    "g033": dict(insufficient_context=True), "g037": dict(insufficient_context=True), "g062": dict(insufficient_context=True),
    "g090": dict(insufficient_context=True), "g101": dict(insufficient_context=True), "g112": dict(insufficient_context=True),
    "g116": dict(insufficient_context=True), "g118": dict(insufficient_context=True), "g142": dict(insufficient_context=True),
    "g145": dict(insufficient_context=True), "g168": dict(insufficient_context=True), "g169": dict(insufficient_context=True),
    "g173": dict(insufficient_context=True),
}
FLAGS = ["taxonomy_gap", "insufficient_context", "multi_intent", "evidence_unavailable"]
LABELS = ["intent", "should_escalate", "escalation_reason"]


def norm_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().map({"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False})


def load(name: str) -> pd.DataFrame:
    df = pd.read_csv(G / name, dtype=str, keep_default_na=False)
    df["should_escalate"] = norm_bool(df.should_escalate)
    for f in FLAGS:
        df[f] = False
    df["evidence_unavailable"] = df.customer_message.str.contains("<url>", regex=False)
    return df.set_index("gid")


def apply(df: pd.DataFrame, who: str) -> tuple[pd.DataFrame, list[dict]]:
    df = df.copy()
    diff = []
    for gid, adj in ADJUDICATIONS.items():
        for field, new in adj.items():
            if field in ("rule", "why"):
                continue
            old = df.at[gid, field]
            if old != new:
                diff.append(dict(gid=gid, annotator=who, field=field, old=old, new=new, rule=adj["rule"]))
                df.at[gid, field] = new
    for gid, meta in META.items():
        for field, new in meta.items():
            if df.at[gid, field] != new:
                df.at[gid, field] = new
                diff.append(dict(gid=gid, annotator=who, field=field, old=False, new=new, rule="meta"))
    return df, diff


def main() -> None:
    a0, b0 = load("golden_annotatorA.csv"), load("golden_annotatorB.csv")
    a1, da = apply(a0, "A")
    b1, db = apply(b0, "B")

    # residual disagreements after v1.1 -> resolve reason mismatches by priority, everything else must be empty
    residual = []
    for gid in a1.index:
        for f in LABELS:
            if a1.at[gid, f] != b1.at[gid, f]:
                residual.append((gid, f, a1.at[gid, f], b1.at[gid, f]))
    resolved_by_priority = []
    for gid, f, va, vb in list(residual):
        if f == "escalation_reason" and a1.at[gid, "should_escalate"] and b1.at[gid, "should_escalate"]:
            best = min((va, vb), key=REASON_PRIORITY.index)
            for df, who, v in ((a1, "A", va), (b1, "B", vb)):
                if v != best:
                    df.at[gid, f] = best
                    (da if who == "A" else db).append(dict(gid=gid, annotator=who, field=f, old=v, new=best, rule="priority"))
            resolved_by_priority.append((gid, va, vb, best))
            residual.remove((gid, f, va, vb))
    assert not residual, f"UNEXPLAINED DISAGREEMENTS REMAIN: {residual}"

    a1.reset_index().to_csv(G / "golden_annotatorA_v11.csv", index=False)
    b1.reset_index().to_csv(G / "golden_annotatorB_v11.csv", index=False)
    gold = a1.reset_index().copy()
    gold["note"] = [ADJUDICATIONS.get(g, {}).get("why", "") or n for g, n in zip(gold.gid, gold.note, strict=False)]
    gold["adjudication_rule"] = [ADJUDICATIONS.get(g, {}).get("rule", "") for g in gold.gid]
    gold.to_csv(G / "golden_adjudicated.csv", index=False)
    diff = pd.DataFrame(da + db)
    diff.to_csv(G / "golden_v11_diff.csv", index=False)

    # ---- report ----
    lines = ["# Guide v1.1 adjudication report", "",
             "Provenance: Annotator B was an isolated AI annotator, not an independent human; the v1.0 kappa (intent 0.920, "
             "escalation 0.885) must never be described as human-human agreement.", "",
             "Status: candidate gold (`golden_adjudicated.csv`) produced. **NOT frozen.**", "",
             "## Rows whose labels changed under v1.1", "",
             "| gid | field | A (v1.0) | B (v1.0) | v1.1 | rule | disagreement | why |", "|---|---|---|---|---|---|---|---|"]
    n_res, n_agreed_changed = 0, 0
    for gid, adj in ADJUDICATIONS.items():
        for f in LABELS:
            if f not in adj:
                continue
            va, vb, v = a0.at[gid, f], b0.at[gid, f], adj[f]
            status = "resolved" if va != vb else "agreed row changed"
            n_res += va != vb
            n_agreed_changed += va == vb
            lines.append(f"| {gid} | {f} | {va} | {vb} | {v} | {adj['rule']} | {status} | {adj['why']} |")
    for gid, va, vb, best in resolved_by_priority:
        lines.append(f"| {gid} | escalation_reason | {va} | {vb} | {best} | priority | resolved | reason priority order |")
        n_res += 1
    lines += ["", f"Label disagreements resolved: {n_res}. Agreed rows changed by a v1.1 rule: {n_agreed_changed}. "
              f"Metadata-only annotations: {len(META)} rows. Residual unexplained disagreements: 0 (asserted).", "",
              "## Rule usage", ""]
    rc = pd.Series([r for adj in ADJUDICATIONS.values() for r in adj["rule"].split(",")]).value_counts()
    lines += [f"- {r}: {n}" for r, n in rc.items()]
    lines += ["", "## Candidate gold summary", "",
              f"- rows: {len(gold)}", f"- intent: {gold.intent.value_counts().to_dict()}",
              f"- should_escalate = true: {int(gold.should_escalate.sum())} ({gold.should_escalate.mean():.1%})",
              f"- escalation_reason: {gold[gold.should_escalate].escalation_reason.value_counts().to_dict()}",
              "- flags: " + ", ".join(f"{f}={int(gold[f].sum())}" for f in FLAGS)]
    (G / "ADJUDICATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[-8:]))
    print(f"\ndiff rows: {len(diff)} (A: {len(da)}, B: {len(db)})  -> golden_v11_diff.csv, ADJUDICATION_REPORT.md")


if __name__ == "__main__":
    main()
