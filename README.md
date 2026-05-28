# Polymarket Informed Trading Detection

Interview submission for the **Inca Digital Investigations Analyst** take-home.

## Objective

Investigate potential insider or informed trading behavior on Polymarket
between November 1, 2025 and May 1, 2026 using public data, reproducible code,
and comma-separated value files.

## Scope

The project focuses on **media and attention markets**: Google Year in Search,
Spotify and music charts, YouTube and creator metrics, awards, and
entertainment-release markets. This scope is narrow enough to review manually
and broad enough to test for information advantages.

## Deliverables

| Deliverable | Path |
|---|---|
| Short written report | `report/report.md` and `report/report.pdf` |
| Market universe | `data/markets_reviewed.csv` |
| Excluded market audit file | `data/markets_excluded.csv` |
| Wallet scores | `data/wallet_scores_reviewed.csv` |
| Ranked review queue | `data/top20_reviewed.csv` |
| Reviewed candidate leads | `data/candidate_wallet_leads.csv` |
| Candidate contract movement | `data/candidate_market_movements.csv` |
| Contract movement chart | `report/candidate_market_movements.png` |
| Verification output | `data/verification_summary.json` |

## Headline Numbers

- **154 reviewed markets** across 42 events.
- **$211.9 million** of market lifetime volume.
- **205,362 pulled trades** from **44,607 wallets**.
- **78.9%** of pulled reviewed-market trade volume covered by the top-500 wallet activity sample.
- **38.6%** of sampled in-scope activity volume flagged as wash-like round-tripping.
- **38 candidate wallet-market rows** from the reviewed lead screen.
- **3 wallets selected** for follow-up in the final report.
- **4 selected wallet-market positions** checked against free Polymarket trade API contract movements.

## Main Finding

The strongest finding is a short follow-up queue of wallets whose trades map to
specific information-access hypotheses:

- `0xcd71fd5370880f3d92bb941e628c05840fe0d127` / `Kevindoto`
- `0x8564848285e54c65f6cc2e3930b49362fbd84b2e` / `AllYourMoniesAreBelongToMe`
- `0x614ef98a8be021de3a974942b2fb98794ff34f1b` / `cookiejar`

The selected wallets map to streaming-rank data, album-sales tracking, and
production outcome knowledge. Google-search trades are treated as controls
because public trend data can explain too much of that edge.

## Reproduce

```bash
pip install -r requirements.txt
python3 src/review_markets.py
python3 src/owner_trace.py
python3 src/score_wallets.py
python3 src/identify_candidate_leads.py
python3 src/analyze_candidate_markets.py
python3 src/plot_candidate_market_movements.py
python3 src/verify_submission.py
```
