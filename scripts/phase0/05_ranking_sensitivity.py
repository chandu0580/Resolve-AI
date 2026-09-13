"""Phase 0 — (a) where does each brand land under different weightings, (b) eyeball top brands,
(c) can we derive a 'resolved' outcome label from thread continuation?"""
import json
import re

import numpy as np
import pandas as pd

s = pd.read_csv("artifacts/brand_analysis/brand_stats.csv"); s = s[s.pairs >= 2000].copy()
def z(x): return (x - x.mean()) / (x.std() + 1e-9)
def peak(x, ideal, width): return np.exp(-((x - ideal) / width) ** 2)
C = pd.DataFrame(index=s.index)
C["volume"] = z(np.log(s.pairs)); C["reach"] = z(np.log(s.unique_customers))
C["intent_diversity"] = z(s.cluster_entropy.fillna(s.cluster_entropy.min())) + z(s.embedding_spread.fillna(s.embedding_spread.min()))
C["resolution_density"] = z(s.substantive_public_share) + z(s.reply_uniqueness) - z(s.top10_template_share)
C["conversation_depth"] = z(np.log(s.thread_size_p50)) - z(s.first_turn_share)
C["temporal_coverage"] = z(np.log(s.days_active))
C["escalation_potential"] = z(peak(s.dm_rate, 0.45, 0.25))
C["data_cleanliness"] = -z(s.cust_non_english_share) - z(s.cust_short_share)
# absolute grounding material: how many substantive (non-DM, >60 char) historical replies exist to ground on
s["substantive_pairs"] = s.pairs * s.substantive_public_share
C["grounding_corpus"] = z(np.log(s.substantive_pairs))
profiles = {
 "balanced":   dict(volume=.10, reach=.05, intent_diversity=.20, resolution_density=.25, conversation_depth=.10, temporal_coverage=.05, escalation_potential=.15, data_cleanliness=.10),
 "escalation-heavy": dict(volume=.10, reach=.05, intent_diversity=.15, resolution_density=.15, conversation_depth=.10, temporal_coverage=.05, escalation_potential=.30, data_cleanliness=.10),
 "grounding-heavy":  dict(volume=.10, reach=.05, intent_diversity=.15, resolution_density=.40, conversation_depth=.05, temporal_coverage=.05, escalation_potential=.10, data_cleanliness=.10),
 "volume-heavy":     dict(volume=.30, reach=.15, intent_diversity=.15, resolution_density=.15, conversation_depth=.05, temporal_coverage=.05, escalation_potential=.10, data_cleanliness=.05),
 "grounding-absolute": dict(volume=.05, reach=.05, intent_diversity=.20, resolution_density=.10, grounding_corpus=.20, conversation_depth=.10, temporal_coverage=.05, escalation_potential=.15, data_cleanliness=.10),
 "equal":            {k: 1/len(C.columns) for k in C.columns},
}
R = pd.DataFrame({p: (sum(C[k]*w for k, w in W.items())).rank(ascending=False).astype(int).values for p, W in profiles.items()}, index=s.brand.values)
R["mean_rank"] = R.mean(1); R = R.sort_values("mean_rank")
print("RANK UNDER EACH WEIGHT PROFILE (top 15 by mean rank, plus AppleSupport):")
print(pd.concat([R.head(15), R.loc[["AppleSupport"]]]).to_string())
R.to_csv("artifacts/brand_analysis/ranking_sensitivity.csv")
print("\nAppleSupport criterion z-scores:"); print(C.loc[s.brand == "AppleSupport"].T.to_string())

# (b) eyeball
df = pd.read_parquet("artifacts/dataset_recon/threads.parquet"); df["parent"] = df.parent.astype("Int64"); by = df.set_index("tweet_id")
def pairs_for(b):
    br = df[(df.author_id == b) & df.parent.notna()]; br = br[br.parent.astype("int64").isin(by.index)]
    par = by.loc[br.parent.astype("int64")]; m = par.inbound.values
    return pd.DataFrame({"cust": par.text.values[m], "reply": br.text.values[m], "reply_id": br.tweet_id.values[m], "brand": b})
pd.set_option("display.max_colwidth", 170); pd.set_option("display.width", 300)
for b in []:
    p = pairs_for(b).sample(4, random_state=3)
    print(f"\n##### {b}"); [print(" C:", c[:160], "\n R:", r[:160]) for c, r in zip(p.cust, p.reply, strict=False)]

# (c) resolution signal: customer's next message after brand reply
THANKS = re.compile(r"thank|thx|worked|fixed|sorted|solved|great|perfect|that did it|resolved|👍|🙏", re.I)
NEG = re.compile(r"still|didn.t work|doesn.t work|not work|no luck|same (issue|problem)|already tried|useless|worse", re.I)
ch = df[df.parent.notna() & df.inbound].copy(); ch["parent"] = ch.parent.astype("int64")
kids = ch.groupby("parent").text.apply(list)
out = {}
for b in ["Tesco", "SouthwestAir", "hulu_support", "SpotifyCares", "AmazonHelp", "AppleSupport", "British_Airways", "XboxSupport"]:
    p = pairs_for(b)
    nxt = p.reply_id.map(kids)
    has = nxt.notna()
    txt = nxt[has].str.join(" ")
    pos = txt.str.contains(THANKS); neg = txt.str.contains(NEG)
    out[b] = dict(pairs=len(p), has_customer_followup=float(has.mean()), followup_positive=float(pos.mean()), followup_negative=float(neg.mean()))
print("\nRESOLUTION SIGNAL FEASIBILITY:"); print(pd.DataFrame(out).T.round(3).to_string())
json.dump(out, open("artifacts/dataset_recon/resolution_signal.json", "w"), indent=2)
