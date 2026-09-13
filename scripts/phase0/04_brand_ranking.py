"""Phase 0 — rank brands. Every criterion, transform and weight is explicit and documented in brand_ranking.md."""
import numpy as np
import pandas as pd

s = pd.read_csv("artifacts/brand_analysis/brand_stats.csv")
s = s[s.pairs >= 2000].copy()          # below this a 200-example golden set + KB is not credible

def z(x): return (x - x.mean()) / (x.std() + 1e-9)
def peak(x, ideal, width): return np.exp(-((x - ideal) / width) ** 2)   # 1 at ideal, decays either side

crit = pd.DataFrame(index=s.index)
crit["volume"]          = z(np.log(s.pairs))
crit["reach"]           = z(np.log(s.unique_customers))
crit["intent_diversity"]= z(s.cluster_entropy.fillna(s.cluster_entropy.min())) + z(s.embedding_spread.fillna(s.embedding_spread.min()))
crit["resolution_density"] = z(s.substantive_public_share) + z(s.reply_uniqueness) - z(s.top10_template_share)
crit["conversation_depth"] = z(s.thread_size_mean) - z(s.first_turn_share)   # deeper threads, more follow-ups
crit["temporal_coverage"]  = z(np.log(s.days_active))
crit["escalation_potential"] = z(peak(s.dm_rate, 0.45, 0.25))               # both extremes are degenerate
crit["data_cleanliness"]   = -z(s.cust_non_english_share) - z(s.cust_short_share)
W = {"volume": .10, "reach": .05, "intent_diversity": .20, "resolution_density": .25, "conversation_depth": .10,
     "temporal_coverage": .05, "escalation_potential": .15, "data_cleanliness": .10}
s["score"] = sum(crit[k] * w for k, w in W.items())
cols = ["brand","score","pairs","unique_customers","days_active","cluster_entropy","embedding_spread","substantive_public_share",
        "reply_uniqueness","top10_template_share","thread_size_mean","first_turn_share","dm_rate","cust_non_english_share","cust_short_share","latency_p50_min"]
r = s.sort_values("score", ascending=False)[cols].reset_index(drop=True)
r.index += 1
r.to_csv("artifacts/brand_analysis/brand_ranking.csv")
pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda v: f"{v:.3f}")
print(r.head(20).to_string())
print("\nweights:", W)
