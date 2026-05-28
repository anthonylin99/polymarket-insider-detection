# Handoff

This repository is an Inca Digital Investigations Analyst take-home project.
It investigates potential insider or informed trading on Polymarket between
November 1, 2025 and May 1, 2026.

## Current Pipeline

- `src/review_markets.py` builds the reviewed media and attention market
  universe in `data/markets_reviewed.csv`.
- `src/score_wallets.py` scores wallets and writes
  `data/wallet_scores_reviewed.csv`, `data/top20_reviewed.csv`,
  `data/primary_signal_evidence.csv`, and `data/rank_sensitivity.csv`.
- `src/identify_candidate_leads.py` builds the reviewed wallet-market lead
  queue used in the final report: `data/candidate_wallet_leads.csv`.
- `src/analyze_candidate_markets.py` refreshes selected candidate market trades
  from the free Polymarket trade API and writes
  `data/candidate_market_movements.csv` plus price points.
- `src/plot_candidate_market_movements.py` renders
  `report/candidate_market_movements.png`.
- `src/owner_trace.py` writes `data/owner_trace.json` by checking the
  Polymarket proxy wallet owner for the Google-search control case through a
  public Polygon node.
- `src/verify_submission.py` writes `data/verification_summary.json`.

## Core Conclusion

The final report does not treat the Pope Leo XIV Google-search wallet as the
headline lead because public trend data is a plausible explanation. The
selected follow-up wallets are `Kevindoto`, `AllYourMoniesAreBelongToMe`, and
`cookiejar`, where the trade behavior maps more naturally to streaming-rank
data, album-sales tracking, and production-result information.

## Submission Files

- `report/report.md`
- `report/report.pdf`
- `data/markets_reviewed.csv`
- `data/wallet_scores_reviewed.csv`
- `data/candidate_wallet_leads.csv`
- `data/candidate_market_movements.csv`
- `report/candidate_market_movements.png`
- `data/verification_summary.json`

## Reproduce

```bash
python3 src/review_markets.py
python3 src/owner_trace.py
python3 src/score_wallets.py
python3 src/identify_candidate_leads.py
python3 src/analyze_candidate_markets.py
python3 src/plot_candidate_market_movements.py
python3 src/verify_submission.py
npx --yes md-to-pdf "report/report.md"
```
