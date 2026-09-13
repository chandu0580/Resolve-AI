"""Phase 0 — raw dataset profile. Writes artifacts/dataset_recon/dataset_profile.json + threads.parquet"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/twcs.csv")
OUT = Path("artifacts/dataset_recon"); OUT.mkdir(parents=True, exist_ok=True)
P = {}

df = pd.read_csv(RAW, dtype={"response_tweet_id": "string", "author_id": "string", "text": "string"})
P["rows"] = len(df)
P["columns"] = {c: str(t) for c, t in df.dtypes.items()}
P["null_counts"] = df.isna().sum().to_dict()
P["duplicate_tweet_ids"] = int(df.tweet_id.duplicated().sum())
P["duplicate_texts"] = int(df.text.duplicated().sum())
P["inbound_share"] = float(df.inbound.mean())
P["unique_authors"] = int(df.author_id.nunique())
brands = df.loc[~df.inbound, "author_id"]
P["n_brands"] = int(brands.nunique())
# customers are anonymised numeric ids; brands keep real handles
P["customer_ids_numeric_share"] = float(df.loc[df.inbound, "author_id"].str.fullmatch(r"\d+").mean())
P["brand_ids_numeric_share"] = float(brands.str.fullmatch(r"\d+").mean())

# time
ts = pd.to_datetime(df.created_at, format="%a %b %d %H:%M:%S %z %Y", errors="coerce")
P["unparseable_dates"] = int(ts.isna().sum())
P["date_min"], P["date_max"] = str(ts.min()), str(ts.max())
monthly = ts.dt.to_period("M").astype(str).value_counts().sort_index()
P["rows_by_month"] = monthly.to_dict()
# is tweet_id order == time order? (matters for leakage via id-based splits)
P["tweet_id_time_spearman"] = float(pd.Series(df.tweet_id.values).corr(pd.Series(ts.astype("int64").values), method="spearman"))

# text
txt = df.text.fillna("")
L = txt.str.len()
P["text_len"] = {"mean": float(L.mean()), "p50": float(L.quantile(.5)), "p90": float(L.quantile(.9)), "max": int(L.max()), "min": int(L.min())}
P["share_with_url"] = float(txt.str.contains(r"https?://", regex=True).mean())
P["share_with_mention"] = float(txt.str.contains(r"@\w+", regex=True).mean())
P["share_with_emoji"] = float(txt.str.contains(r"[\U0001F300-\U0001FAFF☀-➿]", regex=True).mean())
P["share_html_entities"] = float(txt.str.contains(r"&(amp|lt|gt|quot);", regex=True).mean())
P["share_truncated_ellipsis"] = float(txt.str.endswith("…").mean())
# crude language check: share of inbound texts that are mostly ASCII letters
inb = txt[df.inbound]
P["inbound_non_ascii_heavy_share"] = float((inb.str.count(r"[^\x00-\x7F]") / inb.str.len().clip(lower=1) > 0.3).mean())

# graph structure
df["parent"] = df.in_response_to_tweet_id.astype("Int64")
ids = set(df.tweet_id.values)
has_parent = df.parent.notna()
P["share_with_parent"] = float(has_parent.mean())
P["orphan_parent_refs"] = int((~df.loc[has_parent, "parent"].astype("int64").isin(ids)).sum())
resp = df.response_tweet_id.fillna("")
n_children = resp.str.count(r"\d+")
P["share_with_children"] = float((n_children > 0).mean())
P["branching_children_gt1_share"] = float((n_children > 1).mean())
P["max_children"] = int(n_children.max())
# self-consistency: does parent's response list include the child?
child_of = df.loc[has_parent, ["tweet_id", "parent"]].astype("int64")
resp_map = dict(zip(df.tweet_id, resp, strict=False))
consistent = np.fromiter((str(t) in resp_map.get(p, "").split(",") for t, p in zip(child_of.tweet_id, child_of.parent, strict=False)), dtype=bool)
P["parent_child_consistency"] = float(consistent.mean())

# roots -> thread ids by walking up parents (iterative, vectorised)
parent_map = dict(zip(df.tweet_id.values, df.parent.astype("float").values, strict=False))
# Walk every tweet up to its root. Max thread depth is well under 60 hops.
root = df.tweet_id.values.astype("int64")
cur = root.copy()
for _ in range(60):
    nxt = np.array([parent_map.get(int(c), np.nan) for c in cur])
    valid = np.array([(not np.isnan(n)) and (int(n) in ids) for n in nxt])
    if not valid.any():
        break
    cur = np.where(valid, nxt, cur).astype("int64")
    root = np.where(valid, nxt, root).astype("int64")
df["thread_root"] = root
depth = df.groupby("thread_root").size()
P["n_threads"] = int(len(depth))
P["thread_size"] = {"mean": float(depth.mean()), "p50": float(depth.quantile(.5)), "p90": float(depth.quantile(.9)), "p99": float(depth.quantile(.99)), "max": int(depth.max())}
P["threads_single_tweet_share"] = float((depth == 1).mean())
# threads that start with a brand tweet (proactive outreach / missing root)
root_rows = df[df.tweet_id == df.thread_root]
P["threads_starting_with_brand_share"] = float((~root_rows.inbound).mean())
# multi-brand threads
tb = df[~df.inbound].groupby("thread_root").author_id.nunique()
P["threads_with_multiple_brands_share"] = float((tb > 1).mean())
# customers appearing in >1 thread (identity leakage across splits)
ct = df[df.inbound].groupby("author_id").thread_root.nunique()
P["customers_multi_thread_share"] = float((ct > 1).mean())
P["customers_ge5_threads"] = int((ct >= 5).sum())

# reply latency brand->customer
df["ts"] = ts
m = df[~df.inbound & has_parent].merge(df[["tweet_id", "ts"]].rename(columns={"tweet_id": "parent", "ts": "pts"}), on="parent", how="left")
lat = (m.ts - m.pts).dt.total_seconds() / 60
P["brand_reply_latency_min"] = {"p50": float(lat.quantile(.5)), "p90": float(lat.quantile(.9)), "negative_share": float((lat < 0).mean())}

df[["tweet_id", "author_id", "inbound", "ts", "text", "parent", "thread_root"]].to_parquet(OUT / "threads.parquet", index=False)
(OUT / "dataset_profile.json").write_text(json.dumps(P, indent=2, default=str))
print(json.dumps(P, indent=2, default=str))
