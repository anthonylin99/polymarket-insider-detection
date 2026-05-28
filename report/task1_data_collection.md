# Data Collection

This file documents the public data collection pipeline behind the report.

## Pipeline

| Script | Output | Purpose |
|---|---|---|
| `discover_markets.py` | `data/markets.csv` | Raw Polymarket market discovery |
| `review_markets.py` | `data/markets_reviewed.csv` | Reviewed media and attention market universe |
| `backfill_trades.py` | `data/trades.csv.gz` | Public trade records for reviewed markets |
| `activity_pull.py` | `data/activity.csv.gz` | Top-wallet activity histories for wash filtering |
| `wash_filter.py` | `data/activity_clean.csv.gz`, `data/wallet_wash_stats.csv` | Same-wallet round-trip detection |
| `score_wallets.py` | `data/wallet_scores_reviewed.csv` | Wallet scoring and confidence labels |
| `identify_candidate_leads.py` | `data/candidate_wallet_leads.csv` | Reviewed wallet-market lead queue used in the report |
| `analyze_candidate_markets.py` | `data/candidate_market_movements.csv` | Free Polymarket API check of post-entry contract movement |
| `plot_candidate_market_movements.py` | `report/candidate_market_movements.png` | Contract movement chart for the final report |
| `verify_submission.py` | `data/verification_summary.json` | Consistency checks before submission |

## Key Numbers

| Metric | Value |
|---|---:|
| Reviewed markets | 154 |
| Distinct events | 42 |
| Market lifetime volume | $211.9 million |
| Pulled trades | 205,362 |
| Unique wallets in pulled trades | 44,607 |
| Wallets scored in activity sample | 498 |
| Candidate wallet-market rows | 38 |
| Selected follow-up wallets | 3 |
| Selected wallet-market movement rows | 4 |

## Review Rules

Markets are retained when they fit the media and attention thesis:

- Google Year in Search markets
- Spotify and music chart markets
- YouTube and creator metrics
- awards markets
- entertainment-release and performance markets

Markets are excluded when they introduce topic drift:

- artificial-intelligence model benchmark markets
- celebrity legal or personal-life markets
- sports-framed halftime markets
- politics, macroeconomics, and cryptocurrency markets
- residual non-media markets

## Caveats

The wallet activity pull covers the top 500 wallets by reviewed-market volume,
not every wallet. It covers 78.9% of pulled reviewed-market trade volume.

The activity source is capped at 2,000 records per wallet. Some selected
follow-up wallets hit that cap, so the report avoids claims about complete
lifetime behavior.

The wash filter identifies same-wallet round trips. It is not a complete shared
funder graph.
