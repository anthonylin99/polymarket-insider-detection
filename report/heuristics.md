# Insider & Informed Trading on Polymarket — Heuristics Design

**Author:** Anthony Lin
**Submitted to:** Inca Digital — Investigations Analyst take-home challenge
**Window of analysis:** Nov 1, 2025 – May 1, 2026
**Scope:** Polymarket only; pop-culture sub-markets (reality TV eliminations, awards ceremonies, movie/music release performance)
**This document covers Task 2 only** — heuristics design and rationale. Tasks 1 (data collection), 3 (application + report), and 4 (composite ranking) follow in subsequent commits to this repo.

---

## 1. Regulatory and case context

This investigation is scoped against the live regulatory landscape as of May 2026:

- **House Oversight probe (Comer, 2026-05-22).** Letters sent to Polymarket and Kalshi CEOs requesting documentation on identity verification, geographic enforcement, and anomalous-trade detection. Triggering events: 80+ Polymarket wallets placed precisely timed wagers ahead of undisclosed US/Israeli military strikes on Iran with a reported ~98% hit rate, and the unsealed indictment of US Army Master Sergeant Gannon Ken Van Dyke, who allegedly used classified Operation Absolute Resolve information to net ~$409K on Polymarket. ([Oversight release](https://oversight.house.gov/release/comer-launches-investigation-into-insider-trading-on-prediction-market-platforms/), [CNBC](https://www.cnbc.com/2026/05/22/kalshi-polymarket-comer-insider-trading-probe-congress.html))
- **Kalshi enforcement precedents.** Three congressional candidates suspended in April 2026 for betting on their own races. A YouTube channel editor sanctioned for placing contracts on the same channel's content using pre-release knowledge.
- **CFTC posture.** Insider trading on Polymarket/Kalshi is illegal and a stated top federal enforcement priority.

The investigative bar that emerges from these cases is consistent: **role-conflict access + precisely timed conviction + abnormal hit rate**. The heuristics below are designed to surface that combination directly, in a niche (pop culture) where principal-access insiders are plausible and where the smaller market universe lets us avoid the noise that dominates politics and sports.

## 2. Why pop culture

Three reasons:

1. **Genuine information asymmetry.** Production staff on reality competitions know elimination outcomes before air. Awards-body voters and PR firms have early reads on winners. Studio/label staff know box-office tracking and chart numbers before release. The YouTube-editor Kalshi case is the cleanest publicly adjudicated precedent in this category.
2. **Tractable universe.** The Nov 1 2025 – May 1 2026 window contains an estimated 30–80 resolved Polymarket markets across the three sub-niches in scope. That is large enough for statistical signal, small enough to spot-check by hand.
3. **Differentiated angle.** Politics and sports are the obvious choices and will dominate every other take-home submission. Pop-culture markets show analytical judgment about *where* insider risk concentrates, not just *how* to detect it.

Sub-niches in scope:
- **Reality TV eliminations** — Survivor, Love Island, Bachelor/Bachelorette, Big Brother, dance/cooking competitions. Pre-recorded shows are the highest-risk subset (results exist before air).
- **Awards ceremonies** — Oscars, Grammys, Emmys, Tonys, Met Gala, MTV awards. Voter and PR-firm leak surface.
- **Release performance** — opening-weekend box office, first-week album sales, streaming chart position, Rotten Tomatoes score.

Out of scope: celebrity life events (engagements, breakups, deaths), sports, politics, crypto, macro/finance.

## 3. Threat model

Deferred until we see the data. A formal actor taxonomy before observing real trade patterns risks anchoring the analysis on archetypes that don't exist in the dataset. The heuristics below are individual-wallet scorers; we'll revisit grouping (principal vs. tippee vs. coordinated cluster) in Task 3 once the top-flagged wallets are in hand and we can characterize the patterns that actually show up.

## 4. The eight heuristics

Each heuristic produces a `0.0–1.0` score per wallet. Composite ranking in Task 4 is a weighted sum minus anti-signal penalties.

### A. Timing-based — the strongest insider signal

#### A1. Pre-resolution edge

**Plain English.** The wallet repeatedly buys the eventually-correct outcome in the final hours before the market resolves, at a price far from the resolved price.

**Computation.** For each resolved market the wallet entered:

1. Find the wallet's last buy on the eventually-correct outcome.
2. Compute `time_to_resolution = resolution_ts − trade_ts`.
3. Compute `price_gap = |resolution_price − trade_price|` (in probability points, 0–1).
4. Qualify if `time_to_resolution ≤ 4h` AND `price_gap ≥ 0.20`.
5. Per-trade score: `min(1.0, price_gap / 0.40) × exp(−time_to_resolution_minutes / 120)`.
6. Wallet score: mean of qualifying trade scores, scaled by `min(1.0, num_qualifying / 3)` so a single lucky entry can't max the score.

**Why these thresholds.** A 4-hour window is calibrated to the pop-culture cadence: reality TV episodes typically resolve within minutes of broadcast, awards within minutes of envelope-open, box-office within hours of weekend close. Anything bought >4h before is more plausibly skill or rumor. A 20pp gap is large enough to exceed normal pre-resolution drift driven by sharp money clearing residual books.

**False-positive modes.**
- A skilled trader who consistently reads obvious last-minute information (e.g., leaked exit polls posted publicly). Addressed by requiring ≥3 qualifying trades — a one-off doesn't max the score.
- Markets that resolve fast and have natural last-minute price moves (Sundays for box-office). Addressed by anchoring the price-gap measure to *resolved* price rather than to subsequent intra-day prints.

#### A2. Pre-announcement timing cluster

**Plain English.** Wallet's entries concentrate in the final 60 minutes before a known public reveal (episode air time, awards ceremony start, release moment).

**Computation.**
1. For each in-scope market, hand-attach a `reveal_window_start` (taken from show air time / ceremony broadcast / release-date public schedule).
2. For each wallet, compute fraction of total USD volume in market traded in `[reveal_window_start − 60min, reveal_window_start]`.
3. Score = `min(1.0, last_hour_share / 0.5)` — capped at 100% when half or more of the wallet's volume sits in the last hour.

**Why.** This is the single behavior most consistently called out in the Comer-probe reporting on Iran wallets and Van Dyke. The signal is concentration in a specific narrow pre-event window, not just lateness.

**False-positive modes.**
- Pure scalpers riding the closing book. Addressed by cross-checking with B5 (side-purity): scalpers flip sides; insiders don't.

#### A3. Dormant-wallet activation

**Plain English.** Wallet sits idle for ≥30 days, wakes up with one conviction trade on a single pop-culture market, then goes dormant again within 7 days.

**Computation.** For each wallet:
1. Identify trade events that satisfy: prior gap ≥ 30d, single market touched in the awake-window, next trade ≥7d later (or wallet still dormant at extract time).
2. Score = `min(1.0, num_dormant_wakeups / 3)` weighted by USD size of the wake trade relative to wallet's lifetime median.

**Why.** This is the cluster signature from the Comer-probe Iran wallets. Real bettors trade continuously. Single-purpose wallets — fund, bet, vanish — are the operational pattern of someone monetizing a specific tip.

**False-positive modes.**
- Casual users who only bet during one show season. Mitigated by requiring at least 2 separate dormant-wakeup events in window, and by Task 4 cluster-detection which boosts the signal further if multiple dormant wallets share a funder.

### B. Selectivity

#### B4. Single-niche specialist

**Plain English.** Wallet's lifetime trading is heavily concentrated in 1–3 pop-culture markets and avoids the obvious high-volume categories (politics, sports, crypto).

**Computation.**
1. Pull wallet's full lifetime Polymarket trade set (public profile + data-api).
2. Compute `pop_culture_share = USD_in_scope / USD_total`.
3. Compute `concentration = max market share of total USD` (single-market dominance).
4. Score = `pop_culture_share × concentration`, with a 0.8 floor on `pop_culture_share` to qualify at all.

**Why.** Insiders bet where they have information. Generalists do not. A wallet with 95% of volume on one Survivor season finale and nothing on US elections is structurally different from a sharp generalist.

**False-positive modes.**
- A genuine pop-culture fan who happens to only bet on what they watch. Acknowledged — this heuristic alone is weak; it earns weight in Task 4 only when paired with timing or accuracy signals.

#### B5. Side purity (directional, non-market-making)

**Plain English.** Across multiple resolved positions, the wallet only ever takes one side, never hedges, never partially exits.

**Computation.**
1. For each wallet × market, classify entry pattern: `buy-and-hold-to-resolution`, `round-trip`, `partial-exit`, `hedged`.
2. `side_purity = share of positions classified buy-and-hold-to-resolution`.
3. Score = `side_purity` if num_positions ≥ 5, else 0.

**Why.** Market-makers and scalpers flip and hedge — their P&L comes from spread, not direction. Pure directional buy-and-hold across many positions is the footprint of someone who knows the answer.

**False-positive modes.**
- Long-term thesis bettors. Mitigated by requiring resolution-side correctness in conjunction with D8.

### C. Sizing and conviction

#### C6. Size-vs-wallet anomaly with slippage tolerance

**Plain English.** The flagged trades are far larger than the wallet's normal trade and the wallet was willing to eat the book — paying through several levels of asks — to fill at scale.

**Computation.**
1. For each wallet, compute trailing-30-day median trade size (USD).
2. Flag any in-scope trade with size ≥ 1.5× median.
3. For each flagged trade, compute `slippage_bps = (fill_price − pre-trade mid) × 10000`.
4. Score = mean over flagged trades of `min(1.0, size_multiple / 5) × min(1.0, slippage_bps / 200)`.

**Why.** Conviction has two dimensions: relative size and willingness to pay up. An insider who knows the outcome is indifferent to slippage; a careful sharp manages it. The interaction term is the signal.

**False-positive modes.**
- Whales whose normal size dwarfs the book regardless of conviction. Partially addressed by normalizing against the wallet's own median, not absolute USD.

#### C7. Role-conflict adjacency (soft, manual-review tag)

**Plain English.** A wallet's on-chain or off-chain identity has a plausible link to the market's resolution authority — e.g., the funder address has prior interactions with addresses tied to the production company, awards body, or label/studio.

**Computation.** This heuristic is intentionally *not* fully automated in v1. It runs as a flag:

1. For each in-scope market, populate a small lookup of resolver / production / sponsor entities (manually curated — typically 1–3 entries per market).
2. For each top-scoring wallet from A1/A2, pull:
   - Funder address (the address that originally funded this wallet on Polygon)
   - Polymarket public profile (name, X handle, ENS, description)
   - On-chain interaction history of the funder (first-hop counterparties only — keep cheap)
3. Set `role_conflict_flag = True` if any string/address match surfaces.

**Score contribution.** This heuristic does not produce a 0–1 score. In the Task 4 composite, a `True` flag adds a flat `+0.25` and triggers inclusion of the wallet in the report's case-study section regardless of composite rank.

**Why this is soft.** The Kalshi YouTube-editor case is the ideal target for this heuristic, but generating it requires per-market subject-matter research. Automating it brittle-ly across all markets will produce noise. The right architecture is a high-value enrichment on the top of the timing-flagged shortlist, where one true positive is worth more than ten cleanly scored generalists.

### D. Outcome accuracy

#### D8. Excess accuracy vs. market-implied probability (Brier-style)

**Plain English.** The wallet is dramatically more right than the prices it bought at would predict.

**Computation.**
1. For each wallet × resolved market, log `(implied_prob_at_trade, resolved_outcome ∈ {0,1})`.
2. Compute wallet Brier score: `mean((implied_prob - outcome)^2)` — lower is better.
3. Compute the *expected* Brier under perfect calibration (which is the variance of the implied probs themselves).
4. `excess_accuracy = max(0, expected_brier - actual_brier)`.
5. Score = `min(1.0, excess_accuracy / 0.15)`.

**Why.** This is the quantitative version of the "98% hit rate" pattern in the Comer reporting. Buying YES at 30¢ that resolves at $1 has the same accuracy signature as buying YES at 95¢ that resolves at $1; the heuristic captures that an insider knows the answer before the price reflects it.

**False-positive modes.**
- Very small sample size. Mitigated by requiring n ≥ 5 resolved positions to compute a score.

#### D9. Closing-direction precision

**Plain English.** The wallet's direction matches the final price move from trade time to resolution at an abnormally high rate.

**Computation.**
1. For each wallet × trade, label `direction_correct = sign(resolution_price − trade_price) == sign(buy=+1, sell=−1)`.
2. Compute `direction_precision = mean(direction_correct)`.
3. Score = `max(0, (direction_precision − 0.55) / 0.30)`, capped at 1.0.

**Why.** D8 captures the outcome; D9 captures the information *quality* — whether the wallet moved before the market did, not just whether the wallet was eventually right. Together D8 and D9 differentiate informed trading from lucky outcome-betting.

## 5. Anti-signals (down-weight in composite)

Two categories of wallet behavior actively reduce the composite score in Task 4:

- **Doxxed sharps and named leaderboard accounts** (Domer, Theo, Polymarket-published leaderboard names, X-handled wallets that publicly post calls). **Down-weight `−0.30`** on composite score. Soft, not hard exclude, so a doxxed name still surfaces if other signals overwhelm the penalty.
- **Generalist market-makers** — wallets with ≥50 markets touched and trade-direction balance across both YES and NO at similar rates. **Down-weight `−0.20`**. These are spread-capturers, not directional information traders.

Both anti-signals are computed at the wallet level once, applied as a flat composite-score adjustment in Task 4.

## 6. Composite scoring (preview of Task 4)

Tentative weighting, to be sensitivity-tested in Task 4:

| Heuristic | Weight |
|---|---|
| A1 Pre-resolution edge | 0.20 |
| A2 Pre-announcement cluster | 0.15 |
| A3 Dormant-wallet activation | 0.10 |
| B4 Single-niche specialist | 0.05 |
| B5 Side purity | 0.05 |
| C6 Size + slippage anomaly | 0.15 |
| C7 Role-conflict adjacency | flag-only, `+0.25` flat |
| D8 Excess accuracy (Brier) | 0.20 |
| D9 Closing-direction precision | 0.10 |
| **Anti-signals** | `−0.30` doxxed, `−0.20` market-maker |

Timing carries the largest aggregate weight (45% across A1/A2/A3) because timing is the most specific and least gameable signal. Accuracy is second (30% across D8/D9). Sizing and selectivity are corroborating, not load-bearing.

Sensitivity protocol: re-rank the top-50 with each heuristic dropped one-at-a-time. The final top-20 should be stable to ±3 ranks under any single heuristic removal. If a wallet only appears because of one heuristic, it is demoted to the report's "watchlist" section rather than the "flagged" section.

## 7. Known blind spots (brief)

Documented for honesty; revisited after Task 3 data review:

- Small-size insiders (sub-threshold for C6/A1).
- Wallets funded from centralized exchanges (degrades C7 enrichment only).
- Order-splitting to defeat C6.
- Markets without a clean `reveal_window_start` (softens A2).

## 8. Next steps (Tasks 1, 3, 4)

- **Task 1 — Data collection.** Polymarket Gamma API + data-api: discover pop-culture markets in window using a curated keyword set, persist `markets.csv` with hand-attached `reveal_window_start`. Pull trades for those markets into `trades.csv`. Enrich wallet metadata (`enrich_wallets.py`).
- **Task 3 — Apply heuristics + report.** Run `heuristics.py` over the dataset, produce `wallet_scores.csv`, write `report.md` with per-wallet case studies for the top 20.
- **Task 4 — Composite ranking.** Apply weights from §6, sensitivity test, layer the cluster-detection pass (common-funder graph), produce `top20_flagged.csv` and the ranked summary table.

---

*Repository: https://github.com/anthonylin99/polymarket-insider-detection (public). All code, data, and report artifacts will land here as Tasks 1, 3, and 4 complete.*
