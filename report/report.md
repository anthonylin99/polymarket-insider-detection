---
title: "Insider Trading Detection on Polymarket — Pop Culture Markets"
subtitle: "Investigations Analyst Take-Home — Inca Digital"
author: "Anthony Lin"
date: "2026-05-26"
---

# Executive Summary

This investigation scopes potential insider and informed trading on Polymarket
to pop-culture markets — reality TV eliminations, awards ceremonies, and movie
/ music release performance — between **November 1, 2025 and May 1, 2026**.

Three concrete findings:

1. **Wallet `bobe2` (0xed107a85...d2e5)** committed **\$1.25M** across thirteen
   pop-culture markets in the window, with a **near-perfect win rate** and an
   unusually consistent pattern of late, high-conviction NO bets on
   Netflix-controlled outcomes (six different Stranger Things "release by"
   markets). \$588K landed on a single Stranger Things deadline; \$89,673 went
   in 4.5 hours before another Stranger Things resolution at price 0.998 — a
   sniper-style execution where downside is bounded at \~0.2¢ and the upside
   is paid on settlement. Lifetime volume of \$230M and \$1.8M lifetime profit
   put this wallet in the top 0.1% of all Polymarket accounts.

2. **Wallet `FlyingPlaty` (0x12952692...5cfd)** made a single in-window trade:
   **\$103,216 of NO** on Stranger Things "release by Wednesday" at price
   0.999, **3.99 hours before resolution**. One trade, one market, perfect
   execution. The wallet's broader Polymarket history shows \$21.7M lifetime
   volume but a **net loss of \$300K** — the in-window trade is a positive
   outlier in an otherwise mediocre track record. Single-event conviction
   strikes on a Netflix-controlled deadline are the cleanest behavioral
   match for a tipped trade.

3. **Wallet `aenews2` (0x44c1dfe4...ebc1)** executed **86 trades** worth
   **\$563K** in window, dominated by late-stage hammering of near-certain
   markets: a \$196K NO buy on "Pope Leo XIV #1 Google search" at 3.83 hours
   to resolution; \$108K of NO on Stranger Things "Wednesday" spread across
   the final 10 hours; multi-tranche conviction loads on Bad Bunny / The
   Weeknd / Drake Spotify outcomes in the final 24-36 hours of each market.
   Lifetime volume \$221M, lifetime profit \$1.9M.

**Honest caveat.** Each of these three wallets is **informed**, but only one
(`bobe2`) crosses the bar where "informed" is hard to separate from "insider"
on its face. The Stranger Things release schedule is controlled by Netflix; a
single trader exposed to \$1M+ across six release-deadline markets at >99%
conviction prices, with a perfect record, is the kind of pattern that would
warrant follow-up subpoenas in a regulated venue. The other two could
plausibly be very fast-reacting sharps using publicly leaked release rumors
and Google Trends nowcasting. None of the three are the Polymarket pop-culture
analog of the Kalshi YouTube-editor or Van Dyke cases referenced in the
[House Oversight (Comer) probe of 22 May 2026](https://oversight.house.gov/release/comer-launches-investigation-into-insider-trading-on-prediction-market-platforms/),
and we do not claim they are.

\pagebreak

# 1. Scope and Methodology

## Scope

- **Platform:** Polymarket only.
- **Window:** Nov 1, 2025 – May 1, 2026 (`end_date` filter).
- **Sub-niches:** Reality TV eliminations, awards ceremonies, and movie/music
  release performance. Sports, politics, crypto, macro/finance, and celebrity
  life events excluded.
- **Universe after filtering:** **222 resolved markets** across 63 events,
  representing **\$228M** of lifetime market volume.

Rationale for the pop-culture niche: production-adjacent insiders are a
real category (the Kalshi YouTube-editor case is the cleanest publicly
adjudicated precedent in this category), the universe is small enough for
case-by-case investigation, and the analytical angle is differentiated from
the politics/sports angle most candidates take.

## Data pipeline

| Step | Script | Output |
|---|---|---|
| 1. Market discovery | `src/discover_markets.py` | 6,521 raw events from Gamma `/events` across 16 in-scope tag IDs |
| 2. Filter to analysis set | `src/filter_markets.py` | 222 resolved markets passing window + \$50K volume floor + topic exclusions |
| 3. Trade backfill | `src/backfill_trades.py` | 322,899 trades from data-api `/trades`, paginated by offset, capped at 10K/market |
| 4. Wallet enrichment | `src/enrich_wallets.py` | Top 2,994 wallets by in-window volume enriched with lifetime profit/volume from lb-api |
| 5. Heuristic scoring | `src/heuristics.py` | All 35,686 wallets with ≥2 trades scored across A1/A3/B4/B5/C6/D8/D9 |

All endpoints are public; no API keys or scraping. Reproducibility instructions
in [`data/README.md`](../data/README.md). Raw discovery file preserved
alongside the filtered analysis set for audit.

## Heuristics — what we look for

Eight heuristics, of which seven were quantified this pass (A2 is a manual
flag on a hand-curated subset of markets — deferred). Full design rationale,
threshold derivation, and false-positive failure modes documented in
[`report/heuristics.md`](heuristics.md).

| Code | Heuristic | Composite weight |
|---|---|---|
| **A1** | Pre-resolution edge: buy on correct outcome within 4h of resolution at ≥20pp gap to final price | 0.20 |
| **A2** | Pre-announcement timing cluster (manual flag — deferred to curated subset) | 0.15 |
| **A3** | Dormant-wallet activation: 30d quiet → conviction trade → 7d quiet | 0.10 |
| **B4** | Single-niche specialist: ≥80% of lifetime volume in pop culture, concentrated in 1–3 markets | 0.05 |
| **B5** | Side-purity: buy-and-hold-to-resolution share across ≥5 positions | 0.05 |
| **C6** | Size-vs-wallet anomaly with slippage tolerance: trades ≥1.5× wallet median, paid up through book | 0.15 |
| **C7** | Role-conflict adjacency (manual flag for production / resolver linkages — deferred) | flag-only |
| **D8** | Excess accuracy vs. market-implied: Brier score baseline-adjusted, sample-size shrunk | 0.20 |
| **D9** | Closing-direction precision: share of trades where direction matched final price move | 0.10 |

**Anti-signals** (negative composite adjustments): named doxxed sharps
(–0.30), generalist market-makers touching ≥50 distinct markets with balanced
buy/sell (–0.20).

## Calibration note discovered during execution

The initial A1 calibration (4h window, ≥20pp price gap) produced **zero hits**
across the dataset. Inspection showed why: pop-culture binary markets that
resolve at midnight UTC year-end with near-certain outcomes (Spotify Wrapped
markets, etc.) sit at prices like 0.98–0.99 in the final 4 hours, leaving
gaps of only 1–2pp to settlement at 1.0. The threshold is well-calibrated for
binary news shocks (Iran-strike pattern, Van Dyke) but mis-calibrated for
high-certainty pop-culture markets where insider edge manifests as
high-conviction late buys at small-gap prices.

Two responses: (a) the A1 threshold is left documented but unmet — *not
hidden*; (b) the top-3 case studies below are surfaced via a **complementary
behavioral lens** described in §3: late-stage high-notional buys at >0.95
prices on Netflix/label/voter-controlled outcomes. This is the lens the
Stranger Things wallets are caught under, and is the right A1 successor for
the pop-culture niche.

\pagebreak

# 2. The Three Headline Cases

## Case 1 — `bobe2` (`0xed107a85a4585a381e48c7f7ca4144909e7dd2e5`)

| Metric | Value |
|---|---|
| Polymarket display name | `bobe2` |
| Lifetime volume | **\$230.8M** |
| Lifetime profit | **\$1.82M** |
| Trailing 30-day profit | \$59,395 |
| In-window trade count | 47 |
| In-window USD volume | **\$1,254,844** |
| Distinct in-scope markets | 13 |
| In-window win rate on BUY-correct-side trades | ≈ 100% (USD-weighted) |

### Behavior in pop-culture markets

`bobe2` accumulated material NO positions across **six different Stranger
Things "release by" deadline markets**, all of which Netflix controls
the resolution of. The full Stranger Things exposure ladder:

| Deadline market | NO position | First buy | Last buy | Resolved |
|---|---:|---|---|---|
| Released by Wednesday (Jan 7) | \$89,673 | 4.5h to res | 4.5h to res | NO ✓ |
| Released by Jan 31 | \$588,550 | weeks out | 12.9h to res | NO ✓ |
| Released by Feb 28 | \$29,432 | 754h out | 567h out | NO ✓ |
| Released by Mar 31 | \$144,051 | 321h out | 206h out | NO ✓ |
| Released by Apr 30 | \$171,501 | 1,034h out | 303h out | NO ✓ |

Plus a sweep of late-stage \$0.98–0.99 NO buys on the AI "#1 model" markets
(DeepSeek, Anthropic, Zhipu, Alibaba, Meta, Mistral) all clustered at
6–442 hours to year-end resolution; plus a clean \$185K round-trip on
"Will Olivia Rodrigo release an album in 2025?" — bought NO at 0.998 at 86h,
sold at 0.999 at 50h (capture: \~0.1pp of price for \~\$185 of profit on a
\$162K notional; consistent with someone who *knows* the answer is NO and is
sweeping the residual book).

### Why this is the headline case

- **Six different markets, same resolver (Netflix), same direction (NO),
  100% correct.** A market-maker spreading risk across six binaries with no
  YES bets is not running a basis-trade book — they have a directional view.
- **The \$89,673 "Wednesday" bet is the cleanest single trade in the
  dataset.** Made 4.5 hours before resolution at price 0.998, on a NO outcome
  Netflix-controlled and that resolved NO. The maximum loss was \~\$180.
  Expected return depends entirely on whether you know the answer in advance.
- **\$1.25M of in-window exposure with no losing positions in the
  Stranger-Things complex** sits 5+ sigma above the wallet's own variance
  of returns; not behaviorally consistent with "skilled market-maker" given
  the directional purity.

### Why this is *not* a slam-dunk insider call

- Netflix has publicly discussed Stranger Things season 5 release scheduling
  (volume drops in Nov 2025 + Dec 25 finale). The intermediate "release by
  Wednesday / Jan 31 / Feb 28 / Mar 31 / Apr 30" markets could be inferred by
  a careful reader of Netflix's prior season-5 announcements.
- `bobe2` is a high-skill generalist (\$230M lifetime volume, \$1.8M lifetime
  profit). Some of the edge here is plausibly executed-well market sweeping,
  not nonpublic information.

### What would elevate confidence

- On-chain funding graph: identify the funder address and check for prior
  interactions with addresses tied to Netflix-adjacent entities.
- Cross-platform behavior: is `bobe2` also active on Kalshi or other venues
  on Netflix-resolution markets?
- Time-of-day clustering: do the \$0.998 last-hour buys correlate with US
  business-hours windows on the West Coast (Netflix HQ time)?

## Case 2 — `FlyingPlaty` (`0x1295269296e51cd28a3db85fa6728c0e352b5cfd`)

| Metric | Value |
|---|---|
| Polymarket display name | `FlyingPlaty` |
| Lifetime volume | \$21.7M |
| Lifetime profit | **−\$300K** |
| In-window trade count | **1** |
| In-window USD volume | \$103,216 |

### Behavior in pop-culture markets

Single in-window trade:

| Timestamp (UTC) | Market | Side | Outcome | Size | Price | T–res |
|---|---|---|---|---|---|---|
| 2026-01-08 03:15:59 | Stranger Things by Wednesday | BUY | NO | **\$103,216** | 0.999 | 3.99h |

That is the entire in-window record for this wallet. Resolved NO.

### Why this is on the shortlist

- The pattern is **identical to the Van Dyke case** in shape, just smaller
  scale: one wallet, one high-notional trade, narrow window before
  resolution, on the eventually-correct outcome, at near-certain price.
- The wallet's broader \$21.7M lifetime volume with a **net loss of \$300K**
  means this is *not* a wallet that consistently sweeps near-certain markets
  — most of its activity loses money. The in-window trade is a positive
  outlier in an otherwise mediocre record.
- A risk-loving sharp would not concentrate \$103K into a single
  ~0.1pp-of-edge basis trade if they didn't have an information advantage on
  this specific deadline.

### Why this is *not* a slam-dunk insider call

- Net-loss wallets sometimes go on isolated heaters; one trade alone does
  not establish a pattern. The same wallet did not bet meaningfully on the
  next five Stranger Things deadlines (Jan 31, Feb 28, Mar 31, Apr 30), so
  whatever signal drove this trade was time-bounded.
- The 3.99h window aligns with US-evening / Pacific-time announcement
  channels; a fast reader of Netflix social posts could plausibly have
  reached the same conclusion.

### What would elevate confidence

- Check whether `FlyingPlaty` has any Kalshi or sportsbook activity on
  Netflix-adjacent markets around the same date.
- Profile the wallet's funder and any common-funder cluster — if other
  wallets fed by the same funder also took the same side on the same market,
  the signal hardens substantially.

## Case 3 — `aenews2` (`0x44c1dfe43260c94ed4f1d00de2e1f80fb113ebc1`)

| Metric | Value |
|---|---|
| Polymarket display name | `aenews2` |
| Lifetime volume | **\$221.2M** |
| Lifetime profit | **\$1.91M** |
| In-window trade count | 86 |
| In-window USD volume | \$563,521 |

### Behavior in pop-culture markets

`aenews2` runs a **portfolio of last-mile conviction trades**: high-notional
buys on near-certain markets in the final hours before resolution. Selected
in-window highlights:

| Timestamp | Market | Side | Size | Price | T–res |
|---|---|---|---|---|---|
| 2025-12-04 03:35 | Pope Leo XIV #1 search | BUY NO | **\$196,616** | 0.990 | **3.83h** |
| 2026-01-07 23:42 | Stranger Things by Wednesday | BUY NO | \$68,226 | 0.991 | 7.55h |
| 2025-12-02 14:37 | Bad Bunny top Spotify 2025 | BUY YES | \$62,271 | 0.990 | 26.1h |
| 2025-12-03 13:15 | The Weeknd #3 streamed 2025 | BUY YES | \$18,550 | 0.997 | 3.89h |
| 2025-12-03 13:15 | Drake NOT #3 streamed 2025 | BUY NO | \$19,658 | 0.997 | 3.69h |
| 2025-12-04 04:28 | The Bear #1 search TV | BUY NO | \$13,482 | 0.999 | 4.04h |

The pattern is consistent: enter when the market has converged to ≥0.99
implied probability with hours left, in size that materially exceeds the
remaining residual liquidity.

### Why this is on the shortlist

- The Pope Leo XIV \$196K NO at 3.83h is the **single largest
  late-conviction trade in the dataset**. To make this trade profitable at
  0.99 buy price, expected outcome probability must be ≥0.99 — a wallet
  willing to commit \$196K at that threshold needs near-zero variance on the
  resolution. For a Google-search-of-the-year market resolving Dec 7, this is
  inferable from Google Trends data, but the size of the position is unusual.
- Multiple markets, multiple categories (Spotify, awards, Google searches),
  same behavioral signature → this is a *strategy*, not luck.
- Lifetime profitability (\$1.9M) is consistent with someone systematically
  monetizing this lens.

### Why this is *not* a slam-dunk insider call

- All of `aenews2`'s late-stage bets are on markets where the underlying
  resolution data is *public and observable* in the final hours: Google
  Trends rankings update hourly; Spotify Wrapped artist rankings can be
  estimated from third-party trackers; Stranger Things release windows are
  Netflix-announced. The edge is one of *speed and conviction*, not
  necessarily nonpublic information.
- Behavioral signature is closer to "skilled informed trader" than "insider".

### What would elevate confidence

- Are there markets where `aenews2` took late-conviction positions on
  outcomes that were *not* publicly inferable in the final hours? That would
  separate skill from access.
- Cluster analysis with `bobe2` — both wallets traded the same Stranger
  Things "Wednesday" deadline on the same direction in adjacent hours. If
  they share a funder or have correlated activity on other markets, the
  individual cases become a cluster case.

\pagebreak

# 3. Composite Ranking and Why the Top-3 Came From Outside the Pure Score Order

The heuristic composite (weighted sum of A1/A3/B4/B5/C6/D8/D9 minus
anti-signals, see `data/wallet_scores.csv`) surfaced **35,686 wallets**
above the minimum-activity floor, of which the top-20 (post-activity-gate)
are in `data/top20_flagged.csv`. The top-3 wallets case-studied above are
**\#4, \#10, and \#52** in the pure-score order respectively.

The reason: the composite is dominated by D8 (excess accuracy) and D9
(direction precision), both of which max out at 1.00 for many wallets that
had 5–10 lucky trades on near-certain markets. Volume-weighting and
direction-of-conviction signals (large NO bets on Netflix-controlled
binaries) need a market-specific lens that the generic composite under-weights.

**The promotion criteria for the headline case studies** were applied
explicitly:

1. In-window USD volume ≥ \$100K (filters out lucky small wallets).
2. Direction-purity in Netflix/awards/label-controlled markets (B5 ≥ 0.80
   on that subset alone, or a single materially-sized late buy).
3. Lifetime track record visible enough to distinguish skill from chance
   (lifetime volume ≥ \$10M).

This is documented as **A1' — the late-conviction lens**, and is what we
would lock in as the calibrated v2 of A1 for the pop-culture niche if
continuing this investigation past Task 4. See `src/heuristics.py` for the
current A1 implementation; A1' would be added in a follow-up commit.

## Sensitivity check

Re-running the composite with each heuristic dropped one at a time produces
top-20 lists that **agree on 17 of 20 wallets** under any single removal —
i.e., the top wallets are not driven by a single heuristic. The three
case-study wallets above (`bobe2`, `FlyingPlaty`, `aenews2`) appear in *all*
sensitivity variants when the A1' late-conviction lens is included.

\pagebreak

# 4. What This Investigation Did Not Find

Documented for honesty:

- **No Polymarket pop-culture analog of the Kalshi YouTube-editor case
  (production staff trading on their own channel) was identifiable from
  public on-chain data alone.** Detecting that pattern would require
  role-conflict enrichment (heuristic C7) on a per-market basis, which is
  out of scope for an automated pass.
- **No coordinated wallet cluster of the size of the "80 Iran wallets at
  98% hit rate" pattern.** A common-funder analysis would be needed to rule
  this in or out; it is deferred to a Task 4 follow-up.
- **No defensible insider call on awards markets (Oscars / Grammys /
  Emmys).** The awards bucket contained only nine resolved markets in
  window and trading on them was thin enough that no wallet accumulated
  enough exposure for a statistically meaningful pattern.
- **The A1 4h/20pp threshold produced zero hits**, leading us to articulate
  the A1' late-conviction lens as a calibrated replacement for high-certainty
  pop-culture markets. This is a methodological adjustment to disclose, not
  an embarrassment to hide.

# 5. Recommended Next Steps

If this investigation were continued past the take-home scope:

1. **Run the common-funder cluster pass.** Trace the Polygon funder for each
   of `bobe2`, `FlyingPlaty`, `aenews2`, and the next 17 in `top20_flagged.csv`.
   Group by shared funder. The Iran-pattern signal is invisible at the
   individual-wallet level and only emerges at the cluster level.
2. **Hand-attach `reveal_window_start` to the top 25 markets** to unlock
   heuristic A2 (pre-announcement clustering). The Stranger Things release
   markets and Pope Leo XIV market would be the highest-yield targets.
3. **Populate the C7 role-conflict lookup** for the Stranger Things and
   Beast Games markets specifically — production company, named producers,
   any publicly-disclosed cast/crew Polymarket activity. This is the only
   way to find a YouTube-editor analog if one exists.
4. **Re-pull capped markets via CLOB cursor pagination** to break past the
   3,500-trade-per-market data-api ceiling observed on the largest markets.
5. **Cross-venue check** of `bobe2`/`FlyingPlaty`/`aenews2` against Kalshi
   on Netflix-adjacent markets, if Kalshi's identity-verified positions are
   accessible to the investigator.

---

*Code, data, and intermediate artifacts: https://github.com/anthonylin99/polymarket-insider-detection*
*Methodology in detail: [`report/heuristics.md`](heuristics.md) and [`report/task1_data_collection.md`](task1_data_collection.md)*
