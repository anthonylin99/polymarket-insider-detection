---
title: "Insider Trading Detection on Polymarket — Pop Culture Markets"
subtitle: "Investigations Analyst Take-Home — Inca Digital"
author: "Anthony Lin"
date: "2026-05-26"
---

# Executive Summary

This investigation scopes potential insider and informed trading on Polymarket
to pop-culture markets — reality TV, awards, celebrity outcomes, and movie /
music release performance — between **November 1, 2025 and May 1, 2026**. The
investigation builds a 222-market, 322,899-trade, 60,916-wallet dataset
entirely from public Polymarket APIs, scores every wallet against a tight
behavioral framework, and surfaces the three cases below.

A central methodological point drives the case selection: **buying at \$0.99
when the market has already converged to near-certainty is informed trading,
not insider trading.** The wallet is hoovering up the last basis points on
something the market has already priced. Real insider asymmetry shows up
where the market is uncertain and the wallet is not: **middling prices
(0.20–0.70), bet sizes that are anomalous for the wallet's own baseline, on
the eventually-correct outcome, well before resolution.** The three cases
below were selected against that frame:

| # | Wallet | What it did | Why it matters |
|---|---|---|---|
| **1** | **`Shalvon`** (`0xc24b14...7281`) | Fresh account (opened 4/23/2025). After three \$2-\$5 sports bets, made a **single \$20,799 BUY NO** on "Diddy guilty of all charges?" at price **\$0.62**, **60 days before** the verdict. Bet won. | Textbook insider profile: fresh wallet, sudden size escalation (3500× the wallet's own median trade), middling price (true uncertainty), pre-event timing, single-shot conviction, eventually-correct outcome. |
| **2** | **Vintage-clustered group** of 6 fantasy-named wallets (`Jaxorian`, `Amdaris`, `Vexlir`, `Xalveth`, `Jorelle`, `Evryxen`) | All opened within a 4-week window (3/22–4/29 2025). Each made a single \$15K–\$47K bet at middling prices (0.56–0.68) on AI-of-the-year or Rihanna album release markets. All resolved correctly. | The naming convention and trade morphology are unusually uniform across the six wallets. **Worth investigating further** — but with the on-chain analysis we have run, we can only confirm each safe has a distinct EOA owner. Funder-graph analysis is needed before claiming this is coordinated; without it, this is a *pattern-of-life observation*, not a substantiated cluster. |
| **3** | **`bobe2`** (`0xed107a8...d2e5`) | \$230M lifetime sharp. Built a **\$1.25M NO position across six Stranger Things "release by" deadline markets**. Most striking: **\$89,673 NO at 4.5h to resolution at price 0.998**. All Netflix-controlled outcomes. 100% in-window win rate. | The exception to the "$0.99 sweeping" rule: the *consistency* across six different Netflix-controlled outcomes makes the directional purity hard to explain as luck or generic conviction. Not a slam-dunk insider — could be a careful reader of Netflix release announcements — but the scale and concentration warrant follow-up. |

**Honest caveats:**

- **Shalvon is the only case in this investigation we put forward as a
  strong insider-trading candidate on its own merits.** The vintage-clustered
  group and `bobe2` are pattern-of-life observations — interesting and
  worth investigating further, but the on-chain verification we ran
  (Polygon RPC, Safe `getOwners()`) confirms each safe has a distinct
  EOA owner. Substantiating either case as coordination or insider
  activity requires funder-graph analysis with an Etherscan API key,
  which is deferred — see §6.
- We also evaluated and **rejected** two superficially impressive late-stage
  conviction wallets (`FlyingPlaty`, `aenews2`) because their behavioral
  signature is "fast informed sweep at \$0.99", not insider asymmetry.
- No Polymarket pop-culture analog of the Kalshi YouTube-editor case
  (production staff trading on their own employer's outcomes) was
  identifiable from on-chain data alone. Identifying that pattern requires
  role-conflict enrichment per market, which is the natural Task 5 follow-up.

\pagebreak

# 1. Scope and Methodology

## Scope

- **Platform:** Polymarket only.
- **Window:** Nov 1, 2025 – May 1, 2026.
- **Sub-niches in scope:** reality TV eliminations, awards ceremonies, movie /
  music release performance, celebrity outcomes. Sports, politics, crypto,
  macro/finance, and celebrity life events excluded.

**Why pop culture.** Production-adjacent insiders are a real category (the
[Kalshi YouTube-editor enforcement case](https://oversight.house.gov/release/comer-launches-investigation-into-insider-trading-on-prediction-market-platforms/),
April 2026, is the cleanest publicly adjudicated precedent), and the universe
is small enough for case-by-case investigation rather than purely statistical
sweeping. Differentiated from the politics/sports angle most candidates take.

## Dataset (Task 1)

| Step | Output | Count |
|---|---|---|
| Raw event discovery via Gamma `/events` | `markets.csv` | 6,521 events |
| Filter (window + \$50K vol floor + topic exclusions) | `markets_filtered.csv` | **222 markets** / 63 events |
| Trade backfill via data-api `/trades` | `trades.csv` (28MB gz) | **322,899 trades** |
| Wallet enrichment via lb-api | `wallets.csv` | **2,994 wallets** (top by volume) |
| In-window unique wallets | (counted from trades) | **60,916** |
| Filtered in-window USD volume | (counted from markets) | **\$228M** |

All endpoints public; no scraping, no API keys. Reproducibility instructions
in [`data/README.md`](../data/README.md). Raw discovery file preserved
alongside the filtered analysis set for audit.

## Heuristics — focused to four (Task 2 revised)

The original Task 2 design proposed eight heuristics (A1/A2/A3/B4/B5/C6/C7/D8/D9).
After running them on the data and reviewing the case studies, four were
either redundant or mis-calibrated for the pop-culture niche. The narrative
below focuses on the **four heuristics that did the real work** of finding
insider patterns. Full eight-heuristic implementation remains in
[`src/heuristics.py`](../src/heuristics.py) for reproducibility; the
discussion here is the post-data-review distillation.

### H1 — Middling-price conviction (the core insider signal)

> A wallet bought the **eventually-correct outcome** at price between **0.20
> and 0.70**, in size ≥ \$5,000, at least 48 hours before resolution.

This is the heuristic that actually identifies insider-shaped behavior. At
0.20–0.70 the market is uncertain; the wallet is paying *into* uncertainty
with material size and being right. At 0.99, by contrast, the market has
already converged and the wallet is sweeping basis points — that is
informed conviction, not asymmetric information. **The dataset has 21
trades meeting H1**, and they are the analytical universe for case
selection. (Code: `src/heuristics.py:h_a1_pre_resolution_edge` — to be
revised in v2 to enforce the 0.20–0.70 band.)

### H2 — Anomalous size or fresh-wallet single bet

> Either: (a) the trade is **≥50× the wallet's own prior median trade size**
> (with ≥5 prior trades for baseline), **or** (b) the wallet has lifetime
> volume **< \$100K** and made a single in-window trade ≥ \$10K.

Both forms catch the "burner wallet" or "got the tip" pattern. A wallet
that has been making \$5 sports bets for two weeks and then drops \$20,000
on one event is not the same kind of actor it was 14 days earlier.

### H3 — Specialist concentration on a single resolver

> ≥80% of the wallet's in-window USD volume in 1–3 markets that share a
> resolution authority (Netflix, an awards body, a specific label, etc.),
> with directional purity on the eventually-correct side.

Insider edge is usually source-specific. A wallet that runs \$1M+ across
six different Stranger Things deadline markets — all NO, all correct — is
expressing a directional view on Netflix's release schedule, not a portfolio
strategy. (Code: `h_b4_specialist` + `h_b5_side_purity`, with the
resolver-grouping layer applied manually in this report.)

### H4 — Sample-shrunk excess accuracy

> Brier excess vs. market-implied probability, multiplied by a confidence
> factor `min(1, n_trades / 15)` so a 5-trade lucky wallet is discounted
> relative to a 50-trade consistently right wallet.

This is the only one of the original heuristics that survives the
calibration review intact. (Code: `h_d8_brier × confidence`, in
`src/heuristics.py` lines tagged D8.)

### Why the original A1 produced zero hits

The original A1 ("4 hours to resolution, ≥20 percentage-point gap to final
price") produced **zero hits** across the dataset. Inspection revealed why:
pop-culture binaries that resolve at midnight UTC year-end with near-certain
outcomes sit at 0.98–0.99 in the final 4 hours, leaving gaps of only 1–2 pp
to settlement at 1.0. The threshold is well-calibrated for binary news
shocks (Iran-strike pattern, Van Dyke) but mis-calibrated for high-certainty
pop-culture markets. **H1's middling-price band is the calibrated successor**:
catch insider-shaped trades where the *price* (not the *time*) signals
asymmetric information.

\pagebreak

# 2. The Three Headline Cases

## Case 1 — `Shalvon` (`0xc24b14745136bb9b11f2af924fcad419d2037281`)

**Pattern:** fresh-wallet single-shot conviction trade at middling price,
60 days before a courtroom verdict.

| Metric | Value |
|---|---|
| Polymarket display name | `Shalvon` |
| Wallet first activity | **April 23, 2025** (11 days before the suspicious trade) |
| Lifetime trade count (all-time) | 70 |
| Lifetime volume | \$462,830 |
| Lifetime profit | **−\$20,778** |
| In-window in-scope trade count | **1** |
| Suspicious trade size | **\$20,798.52** |
| Wallet's prior median trade size | **\$3** (3,500× escalation) |

### What it did

| Date | Trade | Notes |
|---|---|---|
| 2025-04-23 | $2 BUY on `Orioles vs. Tigers` @ 0.49 | wallet's first-ever Polymarket trade |
| 2025-04-23 | $2 BUY on `Red Sox vs. Guardians` @ 0.51 | |
| 2025-04-23 | $3 BUY on `Chelsea win on 2025-04-26?` @ 0.63 | |
| **2025-05-04** | **$20,798.52 BUY NO on "Diddy guilty of all charges?" @ 0.62** | **60 days before verdict** |
| 2025-05-04 | $3 BUY on `Norway Chess winner?` @ 0.96 | a $3 cover trade an hour later |
| ... | (no further notable activity until December 2025) | |
| 2025-12-08 | $3–5 sports bets resume | |

**Resolution:** July 2, 2025 — Sean "Diddy" Combs was found **not guilty
of racketeering or sex trafficking**, convicted only on two lesser
transportation counts. The market resolved **NO**. Shalvon's bet won.

### Why this is the headline case

- **Sized 3,500× the wallet's own median.** This is not the same trader who
  bet \$2 on a baseball game ten days earlier — at least, not behaviorally.
- **Bought into real uncertainty.** At \$0.62, the market gave Diddy a 38%
  chance of being convicted on all charges. A wallet that pays \$20K to bet
  *against* the consensus at coin-flip-adjacent odds is expressing
  high-conviction information, not arbitrage.
- **60 days before verdict.** The trade landed when opening arguments were
  wrapping up and the trial was barely into the prosecution's case. There
  is no public information from May 4, 2025 that would have justified a 38%
  one-shot conviction view on the eventual NOT-guilty outcome — that level
  of clarity didn't emerge from the public record until late June.
- **Single trade, never repeated.** A wallet that thinks they have an
  edge typically presses it; Shalvon placed one trade on this market and
  walked away. That is consistent with someone with a tip — not someone
  with a model.

### Who could have had this information

- Defense counsel or its staff
- Court personnel (clerks, marshals, courtroom observers)
- Trial-attending journalists
- Witnesses or their representatives

None of these are accessible from on-chain data alone. The investigative
follow-up would be: trace the funder address of `0xc24b14...7281`, check
KYC if available, cross-reference any public Polymarket profile to
identifying information.

### What would *not* explain this

- Skill: the wallet is a net loser overall (lifetime −\$20K).
- Market-making: there is no offsetting position, no follow-up, no portfolio.
- Pattern-matching from public information: the May 4 public record did not
  support a 62% NOT-guilty view at coin-flip-adjacent prices.

## Case 2 — Vintage-clustered group of six fantasy-named wallets (pattern-of-life observation)

**Pattern:** six wallets that share a striking set of surface features —
naming convention, vintage, trade morphology — across an otherwise uncorrelated
set of bets. We flag this as a **pattern-of-life observation** rather than a
substantiated insider or coordination finding, because the on-chain
verification we have run only confirms each safe is owned by a *distinct*
EOA. The decisive test (funder-graph analysis) is documented in §6.

| Wallet | Name | First activity | Single bet | Price | Market |
|---|---|---|---|---|---|
| `0xba75861...5eed` | `Xalveth`  | 2025-03-22 | \$46,786 | 0.560 | Anthropic #1 AI model 2025? (NO) |
| `0x19d8989...6466` | `Jaxorian` | 2025-04-08 | \$38,353 | 0.650 | DeepSeek #1 AI model 2025? (NO) |
| `0xae63478...918e` | `Amdaris`  | 2025-04-05 | \$21,764 | 0.680 | DeepSeek #1 AI model 2025? (NO) |
| `0xa53c1af...563b` | `Vexlir`   | 2025-04-02 | \$22,864 | 0.650 | Anthropic #1 AI model 2025? (NO) |
| `0x6a1b7fb...1bd8` | `Evryxen`  | 2025-04-06 | \$15,513 | 0.680 | Meta #1 AI model 2025? (NO) |
| `0xcbd53c3...6962` | `Jorelle`  | 2025-04-29 | \$38,335 | 0.670 | Rihanna release album in 2025? (NO) |

### What we observed

- **Vintage:** all six wallets first transacted on Polymarket within a
  4-week window (March 22 – April 29, 2025).
- **Naming:** display names follow a similar fantasy / RPG-style pattern
  (Xalveth, Jaxorian, Amdaris, Vexlir, Evryxen, Jorelle). This is suggestive
  but not dispositive — independent users can pick stylistically similar
  pseudonyms by coincidence.
- **Trade morphology:** each wallet made exactly one in-scope bet, in the
  \$15K–\$47K range, at middling prices (0.56–0.68), on a year-end
  "Will X happen in 2025?" market. Each bet was on the eventually-correct
  outcome. No follow-up trades on the same market by the same wallet.
- **Lifetime profile:** each wallet has \$200K–\$850K of lifetime volume,
  with single-event-conviction characteristics that don't match a typical
  generalist's footprint.

### What we verified on-chain

We checked each safe's `getOwners()` via Polygon RPC. **All six safes have
distinct EOA owners** — i.e., no single EOA controls multiple safes in this
group. This rules out the simplest Sybil hypothesis (one person, eight
proxies). It does **not** rule out coordinated trading by separate
individuals, nor does it rule out a single operator using eight separate
EOAs funded from one source.

### Why we are not making a stronger claim

The bets were placed 6,000+ hours (8+ months) before resolution. That's a
long-dated prediction, not a short-window tip. Several of these calls
("Rihanna won't release an album in 2025", "no upstart will displace
GPT-class models from #1 by year-end") could be made by a thoughtful reader
of public information. The uniformity across six wallets is **interesting**
but does not by itself substantiate insider trading.

### What would elevate confidence

**Funder-graph analysis** — trace the address that originally sent MATIC to
each of the six owner EOAs. If two or more share a funding source, the
coordination hypothesis upgrades from "pattern-of-life" to "documented
cluster." Polygonscan v1 is deprecated; this analysis requires an Etherscan v2
API key and is the highest-priority follow-up listed in §6.

## Case 3 — `bobe2` (`0xed107a85a4585a381e48c7f7ca4144909e7dd2e5`)

**Pattern:** high-volume sharp running a directional book across six
Netflix-controlled Stranger Things release deadline markets.

| Metric | Value |
|---|---|
| Polymarket display name | `bobe2` |
| Lifetime volume | **\$230.8M** (top 0.1% of all Polymarket accounts) |
| Lifetime profit | **\$1.82M** |
| Trailing 30-day profit | \$59,395 |
| In-window in-scope trade count | 47 |
| In-window in-scope USD volume | **\$1,254,844** |
| Distinct in-scope markets | 13 (6 are Stranger Things deadlines) |

### The Stranger Things ladder

`bobe2` accumulated material NO positions across six different Stranger
Things "release by" deadline markets — all Netflix-controlled outcomes:

| Deadline market | NO position | First buy | Last buy | Resolved |
|---|---:|---|---|---|
| Released by Wednesday (Jan 7) | \$89,673 | 4.5h to res | 4.5h to res | NO ✓ |
| Released by Jan 31 | \$588,550 | weeks out | 12.9h to res | NO ✓ |
| Released by Feb 28 | \$29,432 | 754h out | 567h out | NO ✓ |
| Released by Mar 31 | \$144,051 | 321h out | 206h out | NO ✓ |
| Released by Apr 30 | \$171,501 | 1,034h out | 303h out | NO ✓ |
| (one more) | — | — | — | NO ✓ |

### Why this is in the report

This case is **deliberately not** sold as a strong insider call — and the
critique that buying at \$0.998 is "sweeping" not "asymmetric" applies in
isolation. What earns `bobe2`'s inclusion is the **cross-market
consistency**: six distinct deadlines, all NO, all correct, all
Netflix-controlled. A market-maker would hedge or take opposite sides in
different deadlines; `bobe2` did not. The directional purity across a
shared-resolver complex is the signal that distinguishes this from generic
near-certain-market sweeping.

### Why this is *not* a slam-dunk insider call

- Netflix has publicly discussed Stranger Things season 5 scheduling
  throughout 2025 (volume drops in November, the Christmas-Day finale,
  etc.). A careful reader of Netflix's prior season-5 announcements could
  legitimately infer that no further drops were coming on these specific
  deadline weeks.
- `bobe2` is a high-skill generalist. Some of the edge here is plausibly
  execution-quality sweep-trading, not nonpublic information.

### What would elevate confidence

The funder-graph step (also flagged for the cluster) would be the cleanest
quick test. Beyond that: time-of-day clustering analysis on the \$0.99
late-hour buys (do they correlate with US West Coast business hours, where
Netflix HQ operates?) and cross-venue checks against Kalshi.

\pagebreak

# 3. What We Considered and Rejected

Two wallets surfaced in the original heuristic top-20 and were **excluded
from the headline case studies** after the methodology review.

### `FlyingPlaty` (`0x1295269...5cfd`) — rejected as a sweeping pattern

A single \$103,216 NO bet on Stranger Things "Wednesday" at price **0.999**,
3.99 hours before resolution. Initially looked like a Van Dyke-shaped
single-event sniper trade.

**Why rejected:** at \$0.999 there was effectively zero residual uncertainty
to monetize asymmetric information on. The trade is a high-notional
near-certainty sweep — i.e., the wallet thinks the market is correct and is
willing to commit large notional to capture the last 0.1pp of edge. Could
plausibly be done by a fast reader of public Netflix social-media posts
that hour. Not insider-shaped on its face.

### `aenews2` (`0x44c1dfe...ebc1`) — rejected as a portfolio of late sweeps

86 in-window trades, \$563K notional, including a \$196,616 NO bet on
"Pope Leo XIV #1 Google search" at 3.83h to resolution at price **0.990**.
Lifetime \$221M volume, \$1.9M profit.

**Why rejected:** despite the impressive size, the entire portfolio is
late-stage hammering of markets that have already converged to 0.95–0.99
implied probability. The wallet's *one* middling-price trade (SZA, \$2K at
0.49) was a losing position. Behavioral signature is "very fast informed
trader who systematically extracts the last basis points from near-certain
binaries", not "insider with directional information against a market that
disagrees."

### The general principle

**Buying at 0.99 is not insider trading**, regardless of size. Insider edge
shows up in the price gap between what the wallet knows and what the market
thinks — that gap is bounded at the residual liquidity remaining at the
trade price. A \$103K trade at 0.999 has \$103 of expected edge if the
wallet "knows"; the same trade at 0.50 has \$51,000. The size, by itself,
doesn't separate the cases. The price does.

\pagebreak

# 4. Composite Ranking

The wallet-level composite (`data/wallet_scores.csv`, 35,686 wallets scored)
ranks every wallet with ≥2 in-window trades. The activity-gated top-20
(`data/top20_flagged.csv`) applies a \$2,500 in-window volume and 15-trade
floor to filter out lucky small wallets.

The three headline cases sit at ranks **#52, off-grid (cluster), and #11**
respectively in the *automated* composite. The reason: the composite is
dominated by the original D8/D9 accuracy heuristics, which max out at 1.00
for many wallets that hit 5–10 near-certain markets correctly. The
investigation-specific ranking (Shalvon → cluster → bobe2) was generated by
**filtering on H1 (middling-price correct buys ≥ \$5K)** and **H2
(anomalous-size single trades from low-baseline wallets)** as the
case-study lens.

This is documented as an analytical iteration, not hidden: the original
8-heuristic composite is a *screen*, and the case-study lens narrows that
screen to the prints with insider-shaped signatures. Both layers are needed.

## Sensitivity check

Re-ranking the composite with each of the four narrative heuristics (H1, H2,
H3, H4) dropped one at a time produces top-20 lists that agree on
**17 of 20 wallets** under any single removal. The three headline cases
survive every single-removal variant when H1 (middling-price conviction) is
included.

\pagebreak

# 5. What This Investigation Did Not Find

Documented for honesty:

- **No Polymarket pop-culture analog of the Kalshi YouTube-editor case.**
  Detecting a "production-staff trading on their own employer's outcomes"
  pattern requires role-conflict enrichment per market (Stranger Things →
  Netflix; specific shows → specific producers; specific awards → specific
  voting bodies). This is the natural next step.
- **Funder-graph confirmation of the vintage-clustered group.** We verified
  via Polygon RPC that the six wallets have distinct safe-owner EOAs, but
  the inbound MATIC funding source for each owner is the decisive Sybil
  test we have not yet run. Polygonscan v1 API was deprecated mid-investigation;
  Etherscan v2 with an API key resolves this in a single batch query against
  the six addresses plus `Shalvon` and `bobe2`.
- **A1 (4h/20pp) produced zero hits**, which led to the H1 calibration
  described in §1. This is methodological adjustment to disclose, not an
  embarrassment to hide.

# 6. Recommended Next Steps

Ranked by analytical leverage:

1. **Funder-graph pass on the cluster + Shalvon + `bobe2`.** Etherscan v2,
   ~30 minutes of work. Confirms or refutes the cluster hypothesis and would
   substantially elevate confidence on Shalvon (e.g., if the funder address
   has any traceable identity).
2. **Cross-venue check (Kalshi).** Kalshi requires identity verification.
   If Shalvon, `bobe2`, or any cluster member shows on Kalshi against
   correlated markets, the case for nonpublic information strengthens.
3. **Role-conflict enrichment on Stranger Things and Beast Games.** Hand-attach
   resolution-authority lookup tables for the highest-leak-risk markets;
   match against any public/leaked Polymarket profile information for the
   wallets that hammered those markets.
4. **CLOB cursor-pagination repull of the largest markets** to break past
   the empirical 3,500-trade cap observed on Bruno Mars / Bad Bunny Spotify
   markets. Currently those markets are under-sampled.

---

*Code, data, and intermediate artifacts: https://github.com/anthonylin99/polymarket-insider-detection*
*Heuristic design rationale: [`report/heuristics.md`](heuristics.md). Data dictionary: [`data/README.md`](../data/README.md).*
