"""Phase 0 — what kind of reply does each brand give? troubleshooting instruction vs data-gathering vs handoff vs social.
This is the criterion the numeric ranking lacked: a brand is only a good fit if a meaningful share of issues can be
resolved publicly (auto-handle) AND a meaningful share genuinely needs a human (escalate)."""
import re

import numpy as np
import pandas as pd

df = pd.read_parquet("artifacts/dataset_recon/threads.parquet"); df["parent"] = df.parent.astype("Int64"); by = df.set_index("tweet_id")
CAT = {
 "troubleshoot": r"\b(restart|reboot|power (off|cycle)|force close|reinstall|re-install|update to|latest version|settings ?>|go to settings|log ?out|sign ?out|log back|clear (the )?cache|reset|toggle|turn (off|on)|try (this|these|the following|again)|check (that|if|whether|your)|make sure|steps? (here|below)|support\.apple|help article|this article|troubleshoot)\b",
 "data_gather": r"\b(full name|address|post ?code|zip|order (number|#|no)|booking (ref|reference)|confirmation (number|code)|receipt|account (email|number)|email address|phone number|serial|imei|username|which (device|model|version|store)|what (device|model|version|ios)|ios version|when did|where did|what happens when|can you (tell|confirm|let us know)|could you (tell|confirm|let us know)|let us know (which|what|if|when))\b",
 "handoff": r"\b(dm|direct message|private message|send us a message|call us|contact us|reach out|chat with us|our team|specialist|1-?800|phone (line|support))\b",
 "social": r"\b(glad|happy to hear|thank(s| you) for|love (to|hearing)|appreciate|welcome|congrat|enjoy|awesome|great day|have a (good|great|nice))\b",
}
rx = {k: re.compile(v, re.I) for k, v in CAT.items()}
cands = ["AppleSupport","SpotifyCares","Tesco","British_Airways","AmazonHelp","hulu_support","AmericanAir","O2","SouthwestAir","XboxSupport","Uber_Support","Delta","sprintcare","AskPlayStation","VirginTrains","GWRHelp","MicrosoftHelps","AdobeCare","comcastcares","TMobileHelp"]
out = {}
for b in cands:
    br = df[(df.author_id == b) & df.parent.notna()]; br = br[br.parent.astype("int64").isin(by.index)]
    par = by.loc[br.parent.astype("int64")]; m = par.inbound.values
    t = br.text[m]
    flags = {k: t.str.contains(r).values for k, r in rx.items()}
    n = len(t)
    troubleshoot_only = flags["troubleshoot"] & ~flags["handoff"]
    out[b] = dict(pairs=n, troubleshoot=float(flags["troubleshoot"].mean()), troubleshoot_no_handoff=float(troubleshoot_only.mean()),
                  data_gather=float(flags["data_gather"].mean()), handoff=float(flags["handoff"].mean()), social=float(flags["social"].mean()),
                  none_of_above=float((~(flags["troubleshoot"]|flags["data_gather"]|flags["handoff"]|flags["social"])).mean()))
R = pd.DataFrame(out).T
# balance score: both automation and escalation must be real. geometric mean of the two, penalised if either < 10%
R["auto_esc_balance"] = np.sqrt(R.troubleshoot_no_handoff.clip(lower=0.01) * R.handoff.clip(lower=0.01))
R = R.sort_values("auto_esc_balance", ascending=False)
print(R.round(3).to_string())
R.to_csv("artifacts/brand_analysis/auto_resolvability.csv")
