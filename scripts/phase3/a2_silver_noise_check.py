"""Phase 3-A2: silver-label noise measured on a hand-inspected sample (60 TRAIN rows, 20 per confidence band, fixed seed).
Hand labels: Claude (an AI annotator, not a human), applying annotation guide v1.1. Re-usable against any silver version:
  python scripts/phase3/a2_silver_noise_check.py
Writes artifacts/intelligence/silver_noise_check.{csv,md}
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from resolveai import config

OUT = Path("artifacts/intelligence")
# customer_tweet_id -> human intent (guide v1.1). Written once against silver-v1; never edited afterwards.
HAND = {
    2261581: "performance_crash", 1526977: "keyboard_text_bug", 1924716: "other", 2774292: "data_loss_sync", 1585322: "keyboard_text_bug",
    1583003: "keyboard_text_bug", 2202159: "performance_crash", 1761120: "hardware_damage", 1979944: "performance_crash", 1217562: "performance_crash",
    430135: "connectivity", 2299868: "apps_services", 2562325: "apps_services", 1834694: "battery_power", 2060155: "account_store_repair",
    387637: "non_english", 1681698: "other", 1657754: "keyboard_text_bug", 2057307: "battery_power", 2303444: "data_loss_sync",
    2060172: "performance_crash", 854596: "general_complaint", 2834443: "apps_services", 2779285: "other", 2040124: "performance_crash",
    2284831: "general_complaint", 957613: "apps_services", 1018324: "general_complaint", 1691697: "keyboard_text_bug", 2366207: "battery_power",
    1451567: "account_store_repair", 2405030: "apps_services", 855413: "other", 1551789: "keyboard_text_bug", 2001541: "data_loss_sync",
    370347: "performance_crash", 1924498: "keyboard_text_bug", 2093810: "general_complaint", 1461640: "keyboard_text_bug", 1713026: "keyboard_text_bug",
    2004971: "account_store_repair", 2668960: "connectivity", 1720750: "general_complaint", 1756423: "other", 1557803: "general_complaint",
    2241253: "keyboard_text_bug", 1821896: "keyboard_text_bug", 1238230: "apps_services", 2524579: "connectivity", 2621260: "general_complaint",
    374798: "apps_services", 1830366: "apps_services", 783466: "non_english", 325894: "general_complaint", 2780669: "general_complaint",
    1395674: "general_complaint", 2852306: "battery_power", 436487: "general_complaint", 2623978: "keyboard_text_bug", 1392464: "general_complaint",
}


def check(version_tag: str) -> dict:
    tr = pd.read_csv(config.PROCESSED_DIR / "silver_train.csv", keep_default_na=False).set_index("customer_tweet_id")
    rows = []
    for tid, human in HAND.items():
        r = tr.loc[tid]
        rows.append({"customer_tweet_id": tid, "message": r.customer_message[:160], "silver": r.silver_intent, "band": r.silver_band, "confidence": r.silver_confidence, "human": human, "correct": r.silver_intent == human})
    df = pd.DataFrame(rows)
    by_band = df.groupby("band").correct.agg(["mean", "count"]).round(3)
    band_share = tr.silver_band.value_counts(normalize=True)
    est = float(sum(by_band.loc[b, "mean"] * band_share.get(b, 0) for b in by_band.index))
    hm = tr.silver_band.isin(["HIGH", "MEDIUM"])
    est_train = float(sum(by_band.loc[b, "mean"] * (tr.silver_band[hm] == b).mean() for b in ("HIGH", "MEDIUM") if b in by_band.index))
    wrong = df[~df.correct][["customer_tweet_id", "band", "silver", "human", "message"]].head(15).to_dict("records")
    rep = {"version": version_tag, "n": len(df), "precision_by_band": {b: {"precision": float(by_band.loc[b, "mean"]), "n": int(by_band.loc[b, "count"])} for b in by_band.index},
           "estimated_precision_all_train": round(est, 3), "estimated_precision_training_rows_high_medium": round(est_train, 3), "examples_wrong": wrong}
    df.to_csv(OUT / f"silver_noise_check_{version_tag}.csv", index=False)
    return rep


def main() -> None:
    stats = json.loads((OUT / "silver_stats.json").read_text(encoding="utf-8"))
    rep = check(stats["version"])
    hist = OUT / "silver_noise_check.json"
    allrep = json.loads(hist.read_text(encoding="utf-8")) if hist.exists() else {}
    allrep[stats["version"]] = rep
    hist.write_text(json.dumps(allrep, indent=1), encoding="utf-8")
    L = ["# Silver-label noise check", "", "60 TRAIN rows (20 per band, seed 42) hand-labelled under guide v1.1 by Claude (AI annotator). Labels fixed before any silver revision.", ""]
    for v, r in allrep.items():
        L += [f"## {v}", "", "| band | precision | n |", "|---|---|---|"] + [f"| {b} | {x['precision']} | {x['n']} |" for b, x in r["precision_by_band"].items()]
        L += ["", f"Estimated precision over all train rows: {r['estimated_precision_all_train']}; over the HIGH+MEDIUM rows used for training: {r['estimated_precision_training_rows_high_medium']}.", "", "Examples of wrong silver labels:", ""]
        L += [f"- `{e['customer_tweet_id']}` [{e['band']}] silver={e['silver']} human={e['human']}: {e['message']}" for e in r["examples_wrong"][:8]]
        L.append("")
    (OUT / "silver_noise_check.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "examples_wrong"}, indent=1))


if __name__ == "__main__":
    main()
