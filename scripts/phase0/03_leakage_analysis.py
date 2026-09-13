"""Phase 0 — leakage risks that would inflate evaluation numbers. Writes artifacts/dataset_recon/leakage.json"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

df = pd.read_parquet("artifacts/dataset_recon/threads.parquet")
df["parent"] = df.parent.astype("Int64")
by_id = df.set_index("tweet_id")
L = {}

# 1. customer identity across time: if we split by time, how many holdout customers also appear in train?
cust = df[df.inbound]
first_seen = cust.groupby("author_id").ts.min()
cut = df.ts.quantile(0.9)
late = cust[cust.ts > cut]
L["time_split_holdout_customers_seen_before_cut"] = float(late.author_id.map(first_seen).lt(cut).mean())

# 2. duplicated customer texts (same complaint copy-pasted / retweeted / spam)
norm = cust.text.str.replace(r"@\w+|https?://\S+", " ", regex=True).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
vc = norm.value_counts()
L["customer_exact_dup_share"] = float((vc[vc > 1].sum()) / len(norm))
L["top_duplicated_customer_texts"] = vc.head(8).to_dict()

# 3. brand replies that quote the customer's text (grounding could leak the answer into the query)
br = df[~df.inbound & df.parent.notna()]
sample = br.sample(20000, random_state=0)
par = by_id.reindex(sample.parent.astype("int64"))
def overlap(a, b):
    A = set(re.findall(r"[a-z]{4,}", str(a).lower())); B = set(re.findall(r"[a-z]{4,}", str(b).lower()))
    return len(A & B) / max(1, len(A))
ov = np.array([overlap(c, r) for c, r in zip(par.text.values, sample.text.values, strict=False)])
L["brand_reply_token_overlap_with_customer"] = {"mean": float(ov.mean()), "share_gt_0.5": float((ov > 0.5).mean())}

# 4. template replies: same brand reply text reused verbatim (retrieval would trivially 'hit')
bnorm = br.text.str.replace(r"@\w+|https?://\S+", " ", regex=True).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
bvc = bnorm.value_counts()
L["brand_reply_exact_dup_share"] = float(bvc[bvc > 1].sum() / len(bnorm))

# 5. tweet_id is NOT time-ordered -> id-based splits mix time (from profile spearman=0.33); quantify
L["tweet_id_vs_time_note"] = "spearman(tweet_id, created_at)=0.33: ids were assigned by the dataset author in crawl order, not chronologically; any split by id or row order is a random split, not a temporal one."

# 6. burst events: share of all inbound volume in the top-3 days (an intent spike like the iOS11 'I' bug dominates)
daily = cust.ts.dt.date.value_counts()
L["top3_days_share_of_inbound"] = float(daily.head(3).sum() / len(cust))

# 7. threads where the customer's later messages reveal the resolution (multi-turn leakage if we take non-first turns)
L["non_first_turn_share_inbound"] = float(cust.parent.notna().mean())

Path("artifacts/dataset_recon/leakage.json").write_text(json.dumps(L, indent=2, default=str))
print(json.dumps(L, indent=2, default=str))
