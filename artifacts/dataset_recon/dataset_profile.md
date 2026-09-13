# Dataset profile: Customer Support on Twitter (Kaggle `thoughtvector/customer-support-on-twitter`, version 10)

Produced by `scripts/phase0/01_dataset_profile.py`; raw numbers in `dataset_profile.json`.

## Schema
| column | type | meaning | nulls |
|---|---|---|---|
| tweet_id | int64 | dataset-assigned id (NOT the Twitter id, NOT chronological) | 0 |
| author_id | string | anonymised numeric id for customers, real handle for brands | 0 |
| inbound | bool | True = customer -> brand | 0 |
| created_at | string | `Tue Oct 31 22:10:47 +0000 2017`, all parseable | 0 |
| text | string | tweet body; handles anonymised as @123456 | 0 |
| response_tweet_id | string | comma-separated ids of replies to this tweet | 37% |
| in_response_to_tweet_id | float | parent id | 28% |

## Size and shape
| fact | value |
|---|---|
| rows | 2,811,774 |
| inbound share | 54.7% |
| unique authors | 702,777 (108 brands, 100% of customer ids are numeric) |
| reconstructed threads | 799,903 |
| thread size | mean 3.5, p50 2, p90 6, p99 15, max 1,390 |
| threads starting with a brand tweet | 1.1% (proactive or truncated) |
| threads with > 1 brand | 0.4% |
| customers appearing in > 1 thread | 16.3% (7,952 customers in 5+ threads) |
| brand reply latency | p50 21 min, p90 ~9 h |

## Time coverage
- Effective range: **Oct 2017 - 3 Dec 2017** (99.4% of rows). Rows from 2008-Sep 2017 exist (about 17k) but are threads whose *replies* happened in the crawl window.
- Volume: Oct 1.25M, Nov 1.40M, Dec (3 days) 139k.
- `tweet_id` vs time Spearman = **0.33**. Ids are crawl order, not chronological. A split by id or row order is a random split.

## Text
| fact | value |
|---|---|
| length | mean 114, p50 115, p90 169, max 513 chars |
| contains URL | 22.5% (mostly t.co; images and help links are unrecoverable) |
| contains @mention | 97.9% |
| contains emoji | 6.9% |
| HTML entities (`&amp;` etc.) | 3.5% -> must unescape |
| truncated with ellipsis | 0.04% |
| inbound heavy non-ASCII (non-Latin script) | 0.8% overall; brand-dependent (AmazonHelp 5.7%, NortonSupport 27%) |
| exact-duplicate texts | 29k (1%); after stripping handles/URLs, 5.6% of customer texts are duplicates, dominated by "thank you", "done", "yes", "sent" |

## Conversation graph quality
- `in_response_to_tweet_id` and `response_tweet_id` agree in 99.8% of parent-child links.
- 3,862 parent references point to tweets absent from the dataset (deleted or outside crawl). Those chains are truncated at the missing node.
- 7.9% of tweets have > 1 reply (branching). Max 1,755 replies to one tweet (a brand announcement).
- Mega-threads exist (max 1,390 tweets). They are viral outage threads, not conversations; thread-size means are skewed by them, so medians are used for ranking.
