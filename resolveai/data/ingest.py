"""Ingestion v2: build the AppleSupport conversation dataset from the raw Kaggle CSV.

Output row = one (customer message -> brand reply) pair with:
  - thread context (up to MAX_CONTEXT_TURNS prior turns, oldest first)
  - the customer's follow-up after the brand reply and a weak outcome signal derived from it
  - a temporal split (kb / holdout) and, for holdout rows, whether the customer was already seen in kb
All customer-authored text is PII-redacted before it is stored. The raw file is read-only.

Run:  python -m resolveai.data.ingest
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
from tqdm import tqdm

from resolveai import config
from resolveai.data.clean import clean_tweet, is_dm_handoff, outcome_from_followup
from resolveai.trust.pii import redact_pii

MAX_CONTEXT_TURNS = 4
HOLDOUT_DAYS = 5
HOLDOUT_SAMPLE = 2_000
DATE_FMT = "%a %b %d %H:%M:%S %z %Y"


@dataclass(frozen=True)
class Thread:
    """Minimal graph view over the raw frame: parent and children lookups plus text/author/time."""
    author: pd.Series
    text: pd.Series
    inbound: pd.Series
    parent: pd.Series
    ts: pd.Series
    children: dict[int, list[int]]

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "Thread":
        kids: dict[int, list[int]] = {}
        has_parent = df.parent.notna()
        for tid, pid in zip(df.index[has_parent], df.parent[has_parent].astype("int64")):
            kids.setdefault(int(pid), []).append(int(tid))
        return cls(df.author_id, df.text, df.inbound, df.parent, df.ts, kids)

    def has(self, tid: int) -> bool:
        return tid in self.text.index

    def parent_of(self, tid: int) -> int | None:
        p = self.parent.get(tid)
        return None if pd.isna(p) else int(p)

    def context_for(self, cust_id: int, brand: str, max_turns: int = MAX_CONTEXT_TURNS) -> tuple[list[str], bool]:
        """Prior turns above cust_id, oldest first. Second value: True if the chain hit a missing tweet."""
        turns, cur, truncated = [], self.parent_of(cust_id), False
        while cur is not None and len(turns) < max_turns:
            if not self.has(cur):
                truncated = True
                break
            who = "brand" if self.author[cur] == brand else "customer"
            turns.append(f"{who}: {clean_tweet(self.text[cur])}")
            cur = self.parent_of(cur)
        turns.reverse()
        return turns, truncated

    def customer_followup(self, brand_tweet_id: int) -> str | None:
        """Earliest inbound reply to the brand's tweet, if any (what the customer said next)."""
        ids = [c for c in self.children.get(brand_tweet_id, []) if self.inbound[c]]
        if not ids:
            return None
        first = min(ids, key=lambda c: self.ts[c])
        return clean_tweet(self.text[first])


def load_raw(path=config.RAW_CSV) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        usecols=["tweet_id", "author_id", "inbound", "created_at", "text", "in_response_to_tweet_id"],
        dtype={"tweet_id": "int64", "author_id": "string", "text": "string"},
    )
    df = df.rename(columns={"in_response_to_tweet_id": "parent"})
    df["parent"] = df.parent.astype("Int64")
    df["ts"] = pd.to_datetime(df.created_at, format=DATE_FMT, errors="coerce")
    return df.drop(columns="created_at").set_index("tweet_id")


def build_pairs(df: pd.DataFrame, brand: str = config.BRAND) -> pd.DataFrame:
    th = Thread.from_frame(df)
    brand_replies = df[(df.author_id == brand) & df.parent.notna()]
    rows = []
    for reply_id, reply in tqdm(brand_replies.iterrows(), total=len(brand_replies), desc="pairs"):
        cust_id = int(reply.parent)
        if not th.has(cust_id) or not th.inbound[cust_id]:
            continue
        context, truncated = th.context_for(cust_id, brand)
        red = redact_pii(clean_tweet(df.text[cust_id], redact=False))
        followup = th.customer_followup(int(reply_id))
        rows.append(
            {
                "customer_tweet_id": cust_id,
                "brand_tweet_id": int(reply_id),
                "customer_author": df.author_id[cust_id],
                "created_at": df.ts[cust_id],
                "customer_message": red.text,
                "pii_redacted": json.dumps(red.counts) if red.counts else "",
                "brand_reply": clean_tweet(reply.text),
                "context": "\n".join(context),
                "n_context_turns": len(context),
                "context_truncated": truncated,
                "is_first_turn": len(context) == 0,
                "dm_handoff": is_dm_handoff(reply.text),
                "followup": followup or "",
                "outcome": outcome_from_followup(followup),
            }
        )
    out = pd.DataFrame(rows)
    out = out[out.customer_message.str.len() >= 5].drop_duplicates("customer_tweet_id")
    return out.sort_values("created_at").reset_index(drop=True)


def split(pairs: pd.DataFrame, holdout_days: int = HOLDOUT_DAYS) -> pd.DataFrame:
    """Temporal split. tweet_id is not chronological (Spearman 0.33 with time), so only created_at is safe.
    Holdout rows also record whether their customer appears in kb, for the customer-disjoint metric variant."""
    pairs = pairs.copy()
    cutoff = pairs.created_at.max().normalize() - pd.Timedelta(days=holdout_days)
    pairs["split"] = "kb"
    pairs.loc[pairs.created_at >= cutoff, "split"] = "holdout"
    kb_customers = set(pairs.loc[pairs.split == "kb", "customer_author"])
    pairs["customer_seen_in_kb"] = (pairs.split == "holdout") & pairs.customer_author.isin(kb_customers)
    return pairs


def subsample(pairs: pd.DataFrame, n_total: int = config.SUBSAMPLE_SIZE, n_holdout: int = HOLDOUT_SAMPLE, seed: int = config.SEED) -> pd.DataFrame:
    kb, ho = pairs[pairs.split == "kb"], pairs[pairs.split == "holdout"]
    sub = pd.concat(
        [kb.sample(n=min(n_total - n_holdout, len(kb)), random_state=seed), ho.sample(n=min(n_holdout, len(ho)), random_state=seed)]
    )
    return sub.sort_values("created_at").reset_index(drop=True)


def main() -> None:
    print(f"reading {config.RAW_CSV}")
    pairs = split(build_pairs(load_raw()))
    full_path = config.PROCESSED_DIR / "full_apple_pairs.csv"
    pairs.to_csv(full_path, index=False)
    sub = subsample(pairs)
    sub_path = config.PROCESSED_DIR / "apple_pairs.csv"
    sub.to_csv(sub_path, index=False)

    stats = {
        "full_pairs": len(pairs),
        "split": pairs.split.value_counts().to_dict(),
        "holdout_window": [str(pairs[pairs.split == "holdout"].created_at.min()), str(pairs.created_at.max())],
        "first_turn_share": round(pairs.is_first_turn.mean(), 4),
        "dm_handoff_share": round(pairs.dm_handoff.mean(), 4),
        "has_followup_share": round((pairs.followup != "").mean(), 4),
        "outcome": pairs.outcome.value_counts().to_dict(),
        "pii_redacted_rows": int((pairs.pii_redacted != "").sum()),
        "context_truncated_rows": int(pairs.context_truncated.sum()),
        "holdout_customer_seen_in_kb_share": round(pairs.loc[pairs.split == "holdout", "customer_seen_in_kb"].mean(), 4),
        "subsample": {"rows": len(sub), "split": sub.split.value_counts().to_dict(), "path": str(sub_path)},
    }
    (config.PROCESSED_DIR / "ingest_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    main()
