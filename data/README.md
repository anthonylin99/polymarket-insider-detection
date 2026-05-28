# Dataset and Artifacts

All artifacts in this directory are generated from public Polymarket data
sources and a public Polygon node. No private data is used.

## Submission Files

| File | Purpose |
|---|---|
| `markets_reviewed.csv` | Reviewed media and attention market universe |
| `markets_excluded.csv` | Excluded markets with explicit `exclusion_reason` values |
| `markets_reviewed_summary.json` | Market counts, volume, topic labels, and removal summary |
| `wallet_scores_reviewed.csv` | Conservative wallet scoring and confidence labels |
| `top20_reviewed.csv` | Ranked review queue after excluding obvious volume farmers |
| `candidate_wallet_leads.csv` | Reviewed wallet-market lead queue used in the final report |
| `candidate_wallet_leads_summary.json` | Screen thresholds and selected follow-up wallets |
| `candidate_market_movements.csv` | Free Polymarket trade API summary of post-entry contract movement |
| `candidate_market_price_points.csv` | Price points used to render the contract movement chart |
| `candidate_market_movements_summary.json` | API fetch summary for selected candidate markets |
| `primary_signal_evidence.csv` | Older single-wallet scoring evidence retained for audit trail |
| `rank_sensitivity.csv` | Rank impact after removing each scoring component |
| `owner_trace.json` | Public Polygon node owner-wallet trace for the Google-search control wallet |
| `verification_summary.json` | Verification results for market scope, candidate leads, and report hygiene |

## Reviewed Universe

The reviewed universe contains **154 markets across 42 events** and
**$211.9 million** of market lifetime volume.

Included categories:

- Google Year in Search attention markets
- Spotify, music chart, and streaming markets
- YouTube and creator attention metrics
- awards markets
- entertainment-release and performance markets

Excluded categories:

- artificial-intelligence model benchmark markets
- celebrity legal or personal-life markets
- sports-framed halftime markets
- generic non-media markets without a clear information-asymmetry thesis

Each retained row has `topic_label` and `include_reason`. Each excluded row has
`exclusion_reason`.

## Data Sources

| Source | Artifact | Notes |
|---|---|---|
| Polymarket public market endpoints | `markets.csv`, `markets_reviewed.csv` | market discovery, lifecycle metadata, volume, and outcomes |
| Polymarket public trade endpoint | `trades.csv.gz` | reviewed subset has 205,362 trades from 44,607 wallets |
| Polymarket public trade endpoint | `candidate_market_movements.csv`, `candidate_market_price_points.csv` | direct free-API refresh for selected candidate markets |
| Polymarket public wallet activity endpoint | `activity.csv.gz` | top-500 wallet activity histories used for wash filtering |
| Polymarket public leaderboard endpoints | `wallets.csv`, `profiles/*.json` | profile, lifetime volume, and profit metadata |
| Public Polygon node | `owner_trace.json` | proxy-wallet owner lookup for the Google-search control wallet |

## Caveats

The wallet activity pull is a **top-500 wallet sample**, not every wallet. That
sample covers **78.9%** of pulled reviewed-market trade volume.

The public activity endpoint is capped at **2,000 records per wallet**. **332
of 500 wallets hit that cap**. The cap does not invalidate the selected trade
evidence, but it limits claims about complete wallet history, complete wash
share, and funding behavior.

The wash filter is operational, not definitive. It flags same-wallet round
trips by matched buy and sell pairs and near-flat net positions. The in-scope
sampled activity wash share is **38.6%** by dollar volume.

`candidate_wallet_leads.csv` is built from pulled market trades rather than
only the top-500 wallet activity sample. That makes the lead queue broader, but
some candidate wallets do not have wash-share estimates or complete wallet
activity histories in this repository.

## Reproduce

```bash
python3 src/review_markets.py
python3 src/owner_trace.py
python3 src/score_wallets.py
python3 src/identify_candidate_leads.py
python3 src/analyze_candidate_markets.py
python3 src/plot_candidate_market_movements.py
python3 src/verify_submission.py
```
