# Polymarket Insider Trading Detection — Pop Culture Markets

Investigation submission for the **Inca Digital — Investigations Analyst** take-home challenge.

**Objective.** Investigate potential informed or insider trading behavior on Polymarket within Nov 1, 2025 – May 1, 2026, scoped to pop-culture markets (reality TV eliminations, awards ceremonies, movie/music release performance).

**Picking this up?** Start with [`HANDOFF.md`](HANDOFF.md) for the initial brainstorm, design decisions, and the next-engineer playbook.

## Status

| Task | Deliverable | Status |
|---|---|---|
| 1. Data collection | [`data/`](data/README.md) + [`report/task1_data_collection.md`](report/task1_data_collection.md) | **complete** |
| 2. Heuristics design | [`report/heuristics.md`](report/heuristics.md) | **complete** |
| 3. Apply heuristics + write findings | `report/report.md`, `data/wallet_scores.csv` | pending |
| 4. Composite ranking system | `data/top20_flagged.csv` | pending |

## Headline numbers (Task 1)

- **222 resolved pop-culture markets** across 63 events, Nov 1 2025 – May 1 2026
- **$228M total volume** in the filtered universe
- **322,899 trades** pulled from 60,916 unique wallets

## Repo layout

```
report/        # written deliverables (heuristics doc, final report, PDFs)
data/          # CSV artifacts: markets, trades, wallet scores, top-20 flagged
src/           # collection + scoring code
notebooks/     # exploratory analysis and case-study writeups
```

## Why pop culture

Politics and sports are the obvious choices for this challenge. The Kalshi YouTube-editor enforcement case (April 2026) and the structural information asymmetry around reality-TV production, awards voting, and release-day numbers make pop-culture markets a high-yield niche with a defensible analytical justification. See [`report/heuristics.md`](report/heuristics.md) §2.

## Regulatory context

This investigation is scoped against the active House Oversight (Comer) probe of Polymarket and Kalshi opened May 22, 2026, and Kalshi's existing insider-trading enforcement actions. Methodology and citations in the heuristics doc.

## Submission

Email to Courtney.fisher@inca.digital with the contents of `report/` and `data/` once Tasks 1, 3, 4 are complete.
