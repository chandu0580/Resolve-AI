import pandas as pd

from resolveai.data.ingest import build_pairs, split, subsample

BRAND = "AppleSupport"


def frame():
    rows = [
        # id, author, inbound, parent, ts, text
        (1, "111", True, None, "2017-11-01 10:00", "@AppleSupport battery drains fast, call me 415-555-0134"),
        (2, BRAND, False, 1, "2017-11-01 10:05", "@111 Which iPhone do you have? Try a restart."),
        (3, "111", True, 2, "2017-11-01 10:10", "@AppleSupport iPhone 7, restarted, still dying"),
        (4, BRAND, False, 3, "2017-11-01 10:15", "@111 DM us and we'll dig in."),
        (5, "111", True, 4, "2017-11-01 10:20", "@AppleSupport thanks!"),
        (6, "222", True, 99, "2017-11-30 09:00", "@AppleSupport keyboard types A? instead of I"),   # parent missing
        (7, BRAND, False, 6, "2017-11-30 09:03", "@222 iOS 11.1.1 fixes this."),
        (8, "333", True, None, "2017-12-03 12:00", "@AppleSupport gracias"),
        (9, BRAND, False, 8, "2017-12-03 12:01", "@333 We offer support in English."),
    ]
    df = pd.DataFrame(rows, columns=["tweet_id", "author_id", "inbound", "parent", "ts", "text"]).set_index("tweet_id")
    df["parent"] = df.parent.astype("Int64")
    df["ts"] = pd.to_datetime(df.ts, utc=True)
    return df


def test_pairs_context_outcome_and_redaction():
    p = build_pairs(frame(), BRAND).set_index("brand_tweet_id")
    assert set(p.index) == {2, 4, 7, 9}
    assert p.loc[2, "is_first_turn"] and p.loc[2, "customer_message"] == "battery drains fast, call me <PHONE>"
    assert p.loc[2, "pii_redacted"] == '{"PHONE": 1}'
    # reply 4 answers tweet 3, whose context is [1, 2]
    assert p.loc[4, "context"] == "customer: battery drains fast, call me <PHONE>\nbrand: Which iPhone do you have? Try a restart."
    assert p.loc[4, "n_context_turns"] == 2 and p.loc[4, "dm_handoff"]
    # outcome from the customer's next message
    assert p.loc[2, "outcome"] == "negative" and p.loc[4, "outcome"] == "positive" and p.loc[7, "outcome"] == "none"
    # missing parent is flagged, not crashed
    assert p.loc[7, "context_truncated"] and p.loc[7, "n_context_turns"] == 0


def test_temporal_split_and_customer_flag():
    p = split(build_pairs(frame(), BRAND), holdout_days=5)
    by = p.set_index("brand_tweet_id")
    assert by.loc[2, "split"] == "kb" and by.loc[9, "split"] == "holdout" and by.loc[7, "split"] == "holdout"
    assert not by.loc[9, "customer_seen_in_kb"]      # customer 333 only appears in holdout
    assert p.created_at[p.split == "kb"].max() < p.created_at[p.split == "holdout"].min()


def test_subsample_is_deterministic():
    p = split(build_pairs(frame(), BRAND))
    a, b = subsample(p, n_total=3, n_holdout=1, seed=1), subsample(p, n_total=3, n_holdout=1, seed=1)
    assert list(a.brand_tweet_id) == list(b.brand_tweet_id) and len(a) == 3
