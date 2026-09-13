# Intent classifier results (Phase 3)

Train: 10795 silver-v2 rows (HIGH+MEDIUM band(s), 60% of KB; band-set choice on DEV: {'HIGH': {'rows': 8403, 'macro_f1': 0.5231, 'accuracy': 0.4088}, 'HIGH+MEDIUM': {'rows': 10795, 'macro_f1': 0.5516, 'accuracy': 0.4662}}). Dev: 800 silver-labelled holdout rows (selection + calibration). Golden: 197 human-labelled, evaluated once.

## DEV (silver labels; noisy, used for selection only)

| model | accuracy | macro-F1 | weighted-F1 | ECE | Brier |
|---|---|---|---|---|---|
| majority | 0.0512 | 0.0089 | 0.005 | 0.9487 | 1.8975 |
| keyword | 1.0 | 1.0 | 1.0 | 0.2744 | 0.0936 |
| tfidf_lr | 0.5975 | 0.641 | 0.5705 | 0.0663 | 0.5282 |
| embed_lr_uncalibrated | 0.4838 | 0.5745 | 0.422 | 0.1617 | 0.6914 |
| embed_lr_calibrated | 0.4838 | 0.5745 | 0.422 | 0.0355 | 0.6577 |

Selected: `{'model': 'embed_lr', 'C': 4.0, 'class_weight': None, 'train_band_set': 'HIGH+MEDIUM', 'temperature': 1.5, 'band_high': 0.75, 'band_medium': 0.4}`. Smoke-dev (30 hand-labelled) accuracy: embed_lr 0.6, keyword 0.5333.

## GOLDEN (197, once)

| model | accuracy | macro-F1 | weighted-F1 | ECE | Brier | 95% CI acc | 95% CI macro-F1 |
|---|---|---|---|---|---|---|---|
| majority | 0.0812 | 0.0137 | 0.0122 | 0.9188 | 1.8375 |  |  |
| keyword | 0.4975 | 0.5598 | 0.5292 | 0.2431 | 0.7402 |  |  |
| tfidf_lr | 0.5431 | 0.5498 | 0.5376 | 0.1269 | 0.5903 |  |  |
| embed_lr_message_only | 0.6142 | 0.6182 | 0.6135 | 0.0774 | 0.5199 | [0.553, 0.68] | [0.551, 0.677] |
| embed_lr_with_context | 0.6091 | 0.6098 | 0.6018 | 0.0979 | 0.5134 | [0.535, 0.68] | [0.528, 0.676] |

### Per-intent (embed_lr with context)

| intent | P | R | F1 | support |
|---|---|---|---|---|
| battery_power | 0.6 | 0.75 | 0.667 | 16 |
| performance_crash | 0.739 | 0.654 | 0.694 | 26 |
| keyboard_text_bug | 0.5 | 0.75 | 0.6 | 16 |
| connectivity | 0.625 | 0.714 | 0.667 | 14 |
| data_loss_sync | 0.615 | 0.471 | 0.533 | 17 |
| apps_services | 0.538 | 0.553 | 0.545 | 38 |
| account_store_repair | 0.571 | 0.75 | 0.649 | 16 |
| hardware_damage | 0.571 | 0.571 | 0.571 | 7 |
| general_complaint | 0.357 | 0.357 | 0.357 | 14 |
| non_english | 0.929 | 1.0 | 0.963 | 13 |
| other | 1.0 | 0.3 | 0.462 | 20 |

### Slices (accuracy)

| slice | n | message only | with context |
|---|---|---|---|
| short | 45 | 0.4 | 0.378 |
| first_turn | 149 | 0.658 | 0.658 |
| multi_turn | 48 | 0.479 | 0.458 |
| multi_intent | 10 | 0.6 | 0.6 |
| insufficient_context | 18 | 0.444 | 0.444 |
| taxonomy_gap | 7 | 0.286 | 0.286 |
| evidence_unavailable | 31 | 0.581 | 0.645 |
| customer_seen_in_kb | 25 | 0.64 | 0.6 |
| low_confidence | 74 | 0.405 | 0.378 |

Bands on golden (with context): {'MEDIUM': 75, 'LOW': 74, 'HIGH': 48}; accuracy by band: {'HIGH': 0.958, 'MEDIUM': 0.613, 'LOW': 0.378}

Flag detection: {'multi_intent': {'gold_n': 10, 'pred_n': 44, 'tp': 3}, 'insufficient_context': {'gold_n': 18, 'pred_n': 10, 'tp': 6}, 'taxonomy_gap': {'gold_n': 7, 'pred_n': 1, 'tp': 0}}

### DEV reliability (calibrated)

| bin | n | mean confidence | accuracy |
|---|---|---|---|
| 0.1-0.2 | 23 | 0.185 | 0.13 |
| 0.2-0.3 | 132 | 0.252 | 0.212 |
| 0.3-0.4 | 161 | 0.348 | 0.261 |
| 0.4-0.5 | 140 | 0.45 | 0.45 |
| 0.5-0.6 | 93 | 0.545 | 0.527 |
| 0.6-0.7 | 72 | 0.649 | 0.708 |
| 0.7-0.8 | 69 | 0.748 | 0.739 |
| 0.8-0.9 | 55 | 0.852 | 0.855 |
| 0.9-1.0 | 55 | 0.943 | 0.964 |

Timings (s): {'majority': 0.023, 'keyword': 0.534, 'tfidf_lr_fit': 8.212, 'embed_lr_fit': 3.136, 'golden_embed_lr_197_predict': 0.004, 'total': 39.3}