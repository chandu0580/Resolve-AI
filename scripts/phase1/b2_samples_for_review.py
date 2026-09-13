"""Phase 1-B/A support: draw two small review samples from the KB split (never from holdout).
  1. data/dev/smoke_dev_unlabelled.csv  -- 30 examples for the LLM smoke test; hand-labelled before use.
     Each comes with 3 'evidence' replies: historical replies to lexically similar KB messages (cheap TF-IDF
     neighbours; the real retriever is built in step E). Disjoint from the golden set by construction (kb only).
  2. data/dev/outcome_check_unlabelled.csv -- 50 pairs with outcome != none for the hand-check required by
     locked decision 6 (outcome signal precision).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from resolveai import config

DEV = Path("data/dev")
DEV.mkdir(exist_ok=True)
SEED = config.SEED + 1  # different seed from the golden sample on purpose


def main() -> None:
    df = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv")
    kb = df[df.split == "kb"].reset_index(drop=True)

    # --- smoke dev set: 30 first-turn KB rows, mixed lengths, plus 3 evidence replies each
    cand = kb[kb.is_first_turn & (kb.customer_message.str.len() > 25)]
    dev = cand.sample(30, random_state=SEED).reset_index(drop=True)
    substantive = kb[(~kb.dm_handoff) & (kb.brand_reply.str.len() > 60)].reset_index(drop=True)
    vec = TfidfVectorizer(min_df=2, ngram_range=(1, 2), sublinear_tf=True).fit(substantive.customer_message)
    S = linear_kernel(vec.transform(dev.customer_message), vec.transform(substantive.customer_message))
    rows = []
    for i, r in dev.iterrows():
        top = [j for j in S[i].argsort()[::-1] if substantive.customer_tweet_id[j] != r.customer_tweet_id][:3]
        rows.append(
            {
                "id": f"d{i:02d}",
                "customer_message": r.customer_message,
                "context": r.context if isinstance(r.context, str) else "",
                "evidence": json.dumps([substantive.brand_reply[j] for j in top]),
                "historical_reply": r.brand_reply,
                "intent": "",
                "should_escalate": "",
            }
        )
    pd.DataFrame(rows).to_csv(DEV / "smoke_dev_unlabelled.csv", index=False)

    # --- outcome check: 50 pairs where the regex fired, stratified over positive / negative / mixed
    oc = pd.concat(
        [
            kb[kb.outcome == "positive"].sample(25, random_state=SEED),
            kb[kb.outcome == "negative"].sample(20, random_state=SEED),
            kb[kb.outcome == "mixed"].sample(5, random_state=SEED),
        ]
    ).sample(frac=1, random_state=SEED)
    oc = oc[["customer_tweet_id", "customer_message", "brand_reply", "followup", "outcome"]].copy()
    oc["human_outcome"] = ""
    oc["note"] = ""
    oc.to_csv(DEV / "outcome_check_unlabelled.csv", index=False)
    print("wrote", DEV / "smoke_dev_unlabelled.csv", "and", DEV / "outcome_check_unlabelled.csv")


if __name__ == "__main__":
    main()
