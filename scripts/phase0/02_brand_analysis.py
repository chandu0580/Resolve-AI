"""Phase 0 — enumerate every brand and compute suitability statistics. Writes artifacts/brand_analysis/brand_stats.csv"""
import os
import re

os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("artifacts/brand_analysis"); OUT.mkdir(parents=True, exist_ok=True)
df = pd.read_parquet("artifacts/dataset_recon/threads.parquet")
df["parent"] = df.parent.astype("Int64")
by_id = df.set_index("tweet_id")
thread_size = df.groupby("thread_root").size()

DM = re.compile(r"\bdm\b|direct message|private message|send us a (private )?message", re.I)
URL = re.compile(r"https?://")
TEMPLATE_STRIP = re.compile(r"@\w+|https?://\S+|\d+")

brands = df.loc[~df.inbound, "author_id"].value_counts()
rows = []
for b, n_replies in brands.items():
    br = df[(df.author_id == b) & (~df.inbound)]
    pr = br[br.parent.notna()].copy()
    pr["parent"] = pr.parent.astype("int64")
    pr = pr[pr.parent.isin(by_id.index)]
    par = by_id.loc[pr.parent]
    mask = par.inbound.values
    pr, par = pr[mask], par[mask]
    if len(pr) < 50:
        continue
    gp = par.parent.astype("float").values
    gp_auth = np.array([by_id.author_id.get(int(g), "") if not np.isnan(g) else "" for g in gp])
    first_turn = (np.isnan(gp)) | (gp_auth != b)
    tsize = thread_size.reindex(pr.thread_root).values
    reply_norm = pr.text.str.replace(TEMPLATE_STRIP, "", regex=True).str.strip().str.lower()
    top10 = reply_norm.value_counts().head(10).sum() / len(pr)
    lat = (pr.ts.values - par.ts.values) / np.timedelta64(1, "m")
    cust_text = par.text
    non_ascii = (cust_text.str.count(r"[^\x00-\x7F]") / cust_text.str.len().clip(lower=1) > 0.3)
    dm = pr.text.str.contains(DM)
    substantive = (~dm) & (pr.text.str.len() > 60)
    rows.append(dict(
        brand=b, replies=int(n_replies), pairs=len(pr), unique_customers=int(par.author_id.nunique()),
        days_active=int(pr.ts.dt.date.nunique()), span_days=int((pr.ts.max() - pr.ts.min()).days) + 1,
        first_turn_share=float(first_turn.mean()), thread_size_p50=float(np.median(tsize)), thread_size_mean=float(tsize.mean()),
        dm_rate=float(dm.mean()), reply_url_share=float(pr.text.str.contains(URL).mean()),
        substantive_public_share=float(substantive.mean()), reply_uniqueness=float(reply_norm.nunique() / len(pr)),
        top10_template_share=float(top10), reply_len_p50=float(pr.text.str.len().median()),
        cust_len_p50=float(cust_text.str.len().median()), cust_short_share=float((cust_text.str.len() < 25).mean()),
        cust_non_english_share=float(non_ascii.mean()), latency_p50_min=float(np.nanmedian(lat)),
    ))
stats = pd.DataFrame(rows).sort_values("pairs", ascending=False).reset_index(drop=True)

# intent diversity for the top 30 brands: cluster a sample of first-turn customer messages
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
div = {}
for b in stats.brand.head(30):
    br = df[(df.author_id == b) & (~df.inbound) & df.parent.notna()]
    pids = br.parent.astype("int64")
    pids = pids[pids.isin(by_id.index)]
    cust = by_id.loc[pids]
    cust = cust[cust.inbound]
    texts = cust.text.str.replace(r"@\w+|https?://\S+", " ", regex=True).str.strip()
    texts = texts[texts.str.len() > 15].drop_duplicates()
    s = texts.sample(min(1500, len(texts)), random_state=0).tolist()
    X = model.encode(s, batch_size=256, normalize_embeddings=True, show_progress_bar=False)
    km = KMeans(n_clusters=12, random_state=0, n_init=3).fit(X)
    p = np.bincount(km.labels_, minlength=12) / len(s)
    ent = float(-(p * np.log(p + 1e-12)).sum() / np.log(12))
    sil = float(silhouette_score(X, km.labels_, sample_size=min(1000, len(s)), random_state=0))
    spread = float(np.mean(np.linalg.norm(X - X.mean(0), axis=1)))  # how spread out the topics are
    div[b] = dict(cluster_entropy=ent, silhouette=sil, embedding_spread=spread)
stats = stats.merge(pd.DataFrame(div).T.rename_axis("brand").reset_index(), on="brand", how="left")
stats.to_csv(OUT / "brand_stats.csv", index=False)
print(stats.head(30).to_string())
