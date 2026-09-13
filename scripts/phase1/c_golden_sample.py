"""Phase 1-C: sample the golden set from the temporal holdout, stratified as specified in
data/golden/ANNOTATION_GUIDE.md. Weak keyword labels are used for stratification ONLY and are not written
to the annotation file. Writes data/golden/golden_unlabelled.csv and golden_sampling_report.json.
"""
from __future__ import annotations

import json

import pandas as pd

from resolveai import config
from resolveai.models.taxonomy import KEYWORDS

SEED = config.SEED
N_INTENT, N_MULTI, N_SHORT, N_EDGE = 120, 40, 20, 20
INTENT_MIN, KEYBOARD_CAP = 8, 20

EDGE = {
    "safety": r"\b(kill myself|suicid|self.?harm|end it all|hurt myself|burn(ed|t) me|caught fire|explod|smoke)\b",
    "legal": r"\b(lawyer|lawsuit|sue|legal action|attorney|consumer (rights|protection)|trading standards|bbb|ftc|press|journalist)\b",
    "non_english": r"\b(que|por|para|não|está|con|pero|gracias|hola|merci|bonjour|ich|nicht|bitte)\b",
    "closure": r"^(thank(s| you)!?|thanks!?|done|sent|ok|okay|yes|no)[.! ]*$",
    "abuse_no_symptom": r"\b(fuck|shit|crap|suck|garbage|trash|useless)\b",
    "pii": None,  # rows where redaction fired
}


def weak_label(text: str) -> str:
    t = text.lower()
    best, best_n = "general_complaint", 0
    for intent, kws in KEYWORDS.items():
        n = sum(1 for k in kws if k in t)
        if n > best_n:
            best, best_n = intent, n
    return best


def main() -> None:
    df = pd.read_csv(config.PROCESSED_DIR / "full_apple_pairs.csv")
    ho = df[df.split == "holdout"].copy()
    ho["weak"] = ho.customer_message.map(weak_label)
    ho["len"] = ho.customer_message.str.len()
    taken: set[int] = set()
    parts = []

    def take(frame: pd.DataFrame, n: int, stratum: str) -> None:
        frame = frame[~frame.customer_tweet_id.isin(taken)]
        pick = frame.sample(n=min(n, len(frame)), random_state=SEED)
        taken.update(pick.customer_tweet_id)
        parts.append(pick.assign(stratum=stratum))

    # 1. edge cases first (rarest)
    per_edge = N_EDGE // len(EDGE)
    for name, pat in EDGE.items():
        m = ho.pii_redacted.notna() & (ho.pii_redacted != "") if pat is None else ho.customer_message.str.contains(pat, case=False, regex=True)
        take(ho[m], per_edge + (1 if name == "safety" else 0), f"edge:{name}")
    # 2. short / ambiguous first-turn
    take(ho[(ho.len < 40) & ho.is_first_turn], N_SHORT, "short")
    # 3. multi-turn
    take(ho[ho.n_context_turns >= 1], N_MULTI, "multi_turn")
    # 4. by weak-label intent: floor of INTENT_MIN each, keyboard capped, rest proportional
    first = ho[ho.is_first_turn]
    counts = first.weak.value_counts()
    alloc = {k: INTENT_MIN for k in counts.index}
    remaining = N_INTENT - sum(alloc.values())
    prop = (counts / counts.sum() * remaining).round().astype(int)
    for k in counts.index:
        alloc[k] += int(prop[k])
    alloc["keyboard_text_bug"] = min(alloc.get("keyboard_text_bug", 0), KEYBOARD_CAP)
    for k, n in alloc.items():
        take(first[first.weak == k], n, f"intent:{k}")

    g = pd.concat(parts).sample(frac=1, random_state=SEED).reset_index(drop=True)  # shuffle so strata aren't visible in order
    g.insert(0, "gid", [f"g{i:03d}" for i in range(len(g))])
    cols = ["gid", "customer_tweet_id", "brand_tweet_id", "created_at", "context", "customer_message", "brand_reply", "n_context_turns", "customer_seen_in_kb"]
    out = g[cols].copy()
    for c in ("intent", "should_escalate", "escalation_reason", "note"):
        out[c] = ""
    out.to_csv(config.GOLDEN_DIR / "golden_unlabelled.csv", index=False)
    # stratum map kept separately so annotators never see it
    g[["gid", "stratum", "weak"]].to_csv(config.GOLDEN_DIR / "golden_strata_hidden.csv", index=False)
    rep = {
        "holdout_rows": len(ho),
        "sampled": len(g),
        "strata": g.stratum.value_counts().to_dict(),
        "weak_label_distribution_holdout": (ho.weak.value_counts(normalize=True).round(3)).to_dict(),
        "weak_label_distribution_sample": (g.weak.value_counts(normalize=True).round(3)).to_dict(),
        "multi_turn_share": round((g.n_context_turns >= 1).mean(), 3),
        "customer_seen_in_kb_share": round(g.customer_seen_in_kb.mean(), 3),
        "seed": SEED,
    }
    (config.GOLDEN_DIR / "golden_sampling_report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    assert not set(g.customer_tweet_id) & set(df[df.split == "kb"].customer_tweet_id), "golden overlaps kb"


if __name__ == "__main__":
    main()
