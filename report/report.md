---
title: "Insider Trading Detection on Polymarket"
subtitle: "Pop Culture Markets, Nov 2025 to May 2026 | Investigations Analyst Take-Home, Inca Digital"
author: "Anthony Lin"
date: "2026-05-26"
---

# Executive Summary

This investigation scopes potential insider and informed trading on Polymarket
to pop-culture markets between November 1, 2025 and May 1, 2026. The
underlying dataset is 222 resolved markets across 63 events, $228M of
lifetime market volume, and 322,899 trades from 60,916 wallets, all
collected from public Polymarket APIs.

The headline finding is not a single insider wallet. It is that a population
of wallets that initially looked like high-conviction insider candidates are
in fact volume farmers chasing the POLY token airdrop that Polymarket
confirmed on October 24, 2025. After detecting and removing this wash-trade
activity, the universe of credible insider candidates is small.

Three concrete findings:

1. **26.4% of the volume run through the wallets in our analysis universe is
   wash trading.** This matches independent academic measurement: a Columbia
   University study published November 7, 2025 found roughly 25% of
   Polymarket volume is wash trading driven by airdrop farming.
   ([Decrypt summary](https://decrypt.co/347842/columbia-study-25-polymarket-volume-wash-trading))
   We detect this with a position-net filter that flags wallets whose net
   directional position is less than 10% of their gross volume on a given
   market.

2. **`0xafEe` (`0xee50a31c...7ed6`) is the one wallet in the cleaned dataset
   with a defensible insider-shaped signature.** Lifetime $7.9M traded,
   $929K profit, 0.8% wash share. Took 14 separate buy positions on the NO
   side of "Will Pope Leo XIV be the #1 searched person on Google this year?"
   at weighted-average price $0.599 across late November and early December
   2025, totaling $257K notional with $181K of implied profit at resolution.
   The bets landed 50 to 324 hours before the market closed, at prices well
   inside the 0.20 to 0.70 middling band where market consensus is genuinely
   uncertain. The wallet's lifetime win-rate on resolved positions in our
   scope is 6/6.

3. **Two patterns commonly mistaken for insider trading are actually
   risk-managed sweeping.** `bobe2` ($230M lifetime volume) committed $1.02M
   to a six-market Stranger Things release ladder and netted $5,068 of
   profit, a 0.495% blended return. `no1yet` ($9.95M lifetime volume) ran
   the same pattern on a smaller scale. Both wallets buy near-certain
   markets at $0.97 to $0.999 and capture the residual basis points; neither
   is insider activity.

**What this report does not claim.** It does not claim Polymarket pop-culture
markets are clean. It does claim that, within the public on-chain dataset
available and the scope window we analyzed, only one wallet survives the
combined wash-trade filter and middling-price conviction test. The natural
next step is funder-graph confirmation against `0xafEe`'s owner EOA and the
top 5 partial-washer candidates, which requires an Etherscan API key.

\pagebreak

# 1. Scope and Methodology

## Scope

- **Platform:** Polymarket only.
- **Window:** Nov 1, 2025 to May 1, 2026.
- **Sub-niches:** reality TV eliminations, awards ceremonies, movie and
  music release performance, and celebrity outcomes such as awards
  ranking, Google search rankings, Spotify charts, and reality TV
  resolution. Sports, politics, crypto, macro, and personal life events
  are excluded.

## Why pop culture

Production-adjacent insiders are a real category. The Kalshi enforcement
case against a YouTube channel editor (April 2026) is the cleanest publicly
adjudicated precedent for trading on nonpublic media-industry information.
Pop-culture markets have a small enough universe of resolved markets in the
analysis window (222) to support case-by-case investigation rather than
purely statistical sweeping, which differentiates this analysis from the
politics and sports angles most take-home submissions take.

## Dataset

| Source | Output | Count |
|---|---|---|
| Gamma `/events` | `markets.csv` | 6,521 events |
| Filter applied (window, $50K volume floor, topic excludes) | `markets_filtered.csv` | 222 markets / 63 events |
| Data-api `/trades` paginated by offset | `trades.csv.gz` | 322,899 trades |
| Lb-api profit/volume | `wallets.csv` | 2,994 enriched |
| Data-api `/activity?type=TRADE` (per wallet) | `activity.csv` | 743,871 records, top 500 wallets by volume |
| Wash-pair detection (this report) | `activity_clean.csv`, `wallet_wash_stats.csv` | 577,371 clean records, 26.4% wash share |
| Heuristic scoring on clean data | `wallet_scores_clean.csv`, `top20_clean.csv` | 348 eligible wallets, 20 ranked |
| Wallet dossiers | `data/profiles/*.json` | 55 individual profiles |

All endpoints are public. No scraping, no API keys, no private data. Code
in `src/`, dataset in `data/`, reproducibility instructions in
[`data/README.md`](../data/README.md).

## Heuristics

Four heuristics, each scored 0 to 1, combined into a weighted composite.

| Code | Heuristic | Definition | Weight |
|---|---|---|---|
| H1 | Middling-price conviction | BUY on the eventually-correct outcome at price 0.20 to 0.70, size at least $5,000, at least 48 hours before resolution. Score scales with total implied profit across qualifying trades, capped at $25,000. | 0.40 |
| H2 | Anomalous size or fresh-wallet bet | Trade at least 50x the wallet's prior-trade median size (requires at least 5 prior trades), or wallet has been active 90 days or less and made an in-scope trade of at least $10,000. | 0.20 |
| H3 | Specialist concentration | At least 80% of the wallet's clean in-window volume in 1 to 3 in-scope markets, with the wallet's directional position correct on the top market by USD. | 0.15 |
| H4 | Sample-shrunk excess accuracy | Brier excess vs. market-implied probability, multiplied by `min(1, n_trades / 15)` so a 5-trade lucky wallet is discounted relative to a 50-trade consistently right wallet. | 0.25 |

Anti-signal: wallets with `wash_vol_share >= 0.50` are excluded from the
ranked output regardless of composite score, because their trade behavior
is dominated by airdrop farming rather than directional position-taking.

Why these four. An earlier draft used eight heuristics. After running them on
the data, four of them produced redundant or mis-calibrated signal. The four
above are the ones that did the analytical work. Buying at price 0.99 is
not insider trading at any size, because the residual edge is bounded at
1/0.99 - 1 = 1% of notional. The insider signature is conviction at
middling prices, which is what H1 measures. The other three serve as
corroborating tests.

\pagebreak

# 2. Wash Trading on Polymarket

## Context

Polymarket announced on October 24, 2025 that it will launch a POLY token
and distribute it through an airdrop to users. The CMO Matthew Modabber
confirmed the announcement in public commentary. The community expectation
is that allocation will be weighted by trading volume, with additional
factors for market diversity, consistency over time, and reinvestment of
winnings. ([CryptoNinjas reporting](https://www.cryptoninjas.net/news/polymarket-confirms-poly-token-airdrop-trading-volume-rumors-trigger-user-sprint/),
[Polymarket FAQ](https://docs.polymarket.com/polymarket-learn/FAQ/wen-token))

Polymarket has no KYC requirement and charges no trading fees on the CLOB,
which makes wash trading structurally cheap. The cost of a round-trip is
the bid-ask spread plus minor Polygon gas, not a percentage commission.

A Columbia University study published November 7, 2025 estimated that
approximately 25% of all Polymarket volume is wash trading, peaking near
60% of weekly volume in December 2024, dropping below 5% in May 2025, and
resurging to roughly 20% by October 2025 as airdrop anticipation built.
([Decrypt](https://decrypt.co/347842/columbia-study-25-polymarket-volume-wash-trading),
[CoinDesk](https://www.coindesk.com/markets/2025/11/07/polymarket-s-trading-volume-may-be-25-fake-columbia-study-finds))

## Why this matters for insider detection

The wash-trade pattern is mechanically identical to the surface signature
of an insider:

- BUY of meaningful size on a market that is not at extreme prices
- Short holding period
- Wallet may have minimal other in-scope activity

If unfiltered, a naive screen for "wallets with a single $20K trade and
no other activity in this market" returns mostly volume farmers, not
insiders. The first analytical task before naming any candidate is
removing the wash population.

## Wash filter design

Per (wallet, market, outcome) tuple, we run two detectors:

1. **Pairwise matcher.** A BUY and a SELL within 48 hours, at prices
   within 300 basis points, with notional sizes within 10%, are flagged
   as a matched wash pair.
2. **Position-net detector.** If gross USD volume on the tuple is at least
   $1,000 but the net directional position (`|BUYs - SELLs|`) is less
   than 10% of gross, the entire tuple is flagged as wash. This catches
   multi-leg round trips that the pairwise matcher misses.

Both passes run on `activity.csv`, the per-wallet trade history pulled
directly from `data-api.polymarket.com/activity`. This endpoint, unlike
the per-market `/trades` endpoint, returns both legs of round-trip
positions reliably.

## Results

| Metric | Value |
|---|---|
| Activity records analyzed | 743,871 |
| Records flagged as wash | 166,500 (22.4%) |
| Wash volume | $161,006,073 |
| Total volume | $609,806,989 |
| Wash share by USD | **26.4%** |
| Wallets classified `volume_farmer` (>=50% wash) | 152 of 500 |
| Wallets classified `partial_washer` (10-50% wash) | 198 of 500 |
| Wallets classified `clean` (<10% wash) | 150 of 500 |

The 26.4% USD figure matches the Columbia study's 25% estimate, validating
both the methodology and the operational impact of the airdrop on data
quality.

Notable wallets confirmed as volume farmers under this filter include
`Shalvon` (91% wash), `Niora` (91%), `Uvron` (91%), `Wyntheris` (92%),
`Xalveth` (73%), `Jaxorian` (77%), and 15 other wallets that any
single-trade-screen-without-wash-filter would surface as suspicious. They
are not. Their bets are matched by near-immediate counter-trades that
return the wallet to a flat position.

\pagebreak

# 3. The One Insider Candidate

## `0xafEe` Profile

| Field | Value |
|---|---|
| Wallet address | `0xee50a31c3f5a7c77824b12a941a54388a2827ed6` |
| Display name | `0xafEe` |
| Lifetime volume (lb-api) | **$7,914,116** |
| Lifetime profit (lb-api) | **$929,251** |
| Wash share (this study) | **0.8%** |
| Activity window pulled | Nov 17 to Dec 4, 2025 (16.4 days, 1,986 trades) |
| Clean in-window volume | $2,083,004 |
| In-scope (pop-culture) volume | $1,322,166 |
| Distinct in-scope markets | 6 |
| In-scope resolved positions | 6 of 6 won |
| Median trade size | $24.78 |
| Maximum trade size | $189,128 |

## What `0xafEe` did

The wallet ran a directional book against the "Will [Person X] be the #1
searched person on Google this year?" market complex throughout late November
and early December 2025. The market complex consisted of separate binary
markets for each candidate (Donald Trump, Pope Leo XIV, Bianca Censori,
Diddy, and others), all resolving simultaneously based on Google's published
end-of-year rankings.

The wallet's exposure was structured as follows:

| Candidate | Side | Trades | Total Notional | Wavg Price | Outcome |
|---|---|---:|---:|---:|---|
| Donald Trump | NO | 6 | $498K | 0.913 | NO won |
| Bianca Censori | NO | 7 | $397K | 0.862 | NO won |
| **Pope Leo XIV** | **NO** | **14** | **$257K** | **0.599** | **NO won** |
| Other candidates | NO | small | $170K | sweep | NO won |

The Trump and Censori positions are sweep trades at high prices. The
**Pope Leo XIV book is the one with insider-shaped characteristics**.

## The Pope Leo XIV trades, in detail

These are the 14 H1-qualifying buys, all on the NO side, all eventually
correct, all placed at middling prices (0.48 to 0.65) with 48 to 324
hours of remaining time to market resolution.

| Date (UTC) | Size USD | Price | Hours to resolution | Implied profit if NO wins |
|---|---:|---:|---:|---:|
| 2025-12-01 21:02 | $39,052 | 0.482 | 58 | $41,930 |
| 2025-12-01 22:08 | $13,514 | 0.600 | 194 | $9,009 |
| 2025-11-25 19:35 | $68,584 | 0.610 | 204 | $43,849 |
| 2025-11-25 19:36 | $31,500 | 0.630 | 248 | $18,500 |
| 2025-11-22 14:06 | $20,904 | 0.600 | 213 | $13,936 |
| 2025-11-20 17:26 | $19,208 | 0.648 | 286 | $10,416 |
| 2025-11-25 12:14 | $14,507 | 0.650 | 279 | $7,812 |
| 2025-11-26 21:23 | $11,953 | 0.600 | 315 | $7,969 |
| 2025-12-01 22:21 | $9,816 | 0.500 | 48 | $9,820 |
| 2025-11-22 17:42 | $6,182 | 0.600 | 166 | $4,122 |
| 2025-11-25 19:30 | $5,837 | 0.630 | 248 | $3,428 |
| 2025-11-26 22:01 | $5,739 | 0.600 | 324 | $3,826 |
| 2025-11-22 17:46 | $5,602 | 0.600 | 166 | $3,735 |
| 2025-11-26 13:39 | $5,025 | 0.630 | 301 | $2,951 |
| **Total** | **$257,423** | **0.599** | | **$181,303** |

The bets converted directly into the wallet's lifetime $929K profit figure
on the lb-api. This is the cleanest single-market insider-shaped position
in the entire analysis universe.

## Why this is insider-shaped

- **Real conviction at middling prices.** The wallet did not sweep at
  $0.99. Across 14 separate trades it averaged $0.599 entry price on the
  eventually-correct NO side. At entry, the market was assigning Pope
  Leo XIV a 40% chance of being the #1 Google search of 2025.
- **Concentrated across many trades on one specific outcome.** The trades
  are not a single conviction bet that could be explained by one
  read-through. They are 14 separate adds over 12 days, all leaning the
  same direction with increasing size as resolution approaches.
- **Pre-resolution timing.** The earliest qualifying trade is 324 hours
  (13.5 days) before market close. The Google Trends data that determines
  this kind of market is only released by Google itself at year-end.
  Building a $257K position at $0.50 to $0.65 a week or more before that
  publication requires either (a) systematic real-time Google Trends
  analysis with a defensible model, or (b) nonpublic information about
  how the ranking is constructed or what the leading candidates will be.
- **6 of 6 in-scope resolved positions won.** Across the full Google
  search market complex, every position the wallet took was on the
  eventually-correct side.

## Why this is not yet a slam-dunk case

- **Public alternative explanation.** Google Trends data is technically
  public, updated daily. A sophisticated analyst with real-time scraping
  and a calibrated model could in principle have correctly read that
  d4vd (the actual #1) was outperforming Pope Leo XIV in the weeks
  before resolution. The conviction shown here is consistent with that
  alternative.
- **Lifetime profit is not extreme.** $929K on $7.9M lifetime volume is
  a 12% lifetime return, which is high but not impossible for a skilled
  sharp.
- **No identity attached.** The wallet uses a generic pseudonym
  (`0xafEe`, an abbreviation of its own address). No X handle, no bio,
  no profile image on the LB. This is consistent with both an anonymous
  sharp and an anonymous insider.

## What would elevate confidence

1. **Funder-graph trace.** Identify the EOA owner of the Polymarket safe
   at `0xee50a31c...7ed6` and the address that originally funded it.
   Requires an Etherscan API key. If the funder is associated with any
   entity in the search-ranking-adjacent space (Google, an SEO firm, a
   data analytics provider with privileged access), the case sharpens
   substantially.
2. **Cross-venue check.** Did the same EOA wallet take correlated
   positions on Kalshi or another prediction market in the same window?
3. **Real-time Google Trends comparison.** Pull actual hourly Google
   Trends ranking data for the relevant candidates from November 1 to
   December 4, 2025. If the publicly visible data already showed d4vd
   pulling away by November 17 (the wallet's first qualifying trade),
   then `0xafEe`'s edge could be explained by public-data analytics. If
   Pope Leo XIV was still ahead of d4vd in the publicly visible data
   for most of November, the wallet was either right ahead of public
   information or had a private model that beat the public data
   significantly.

\pagebreak

# 4. Two Patterns That Look Insider But Are Not

These wallets surfaced in earlier heuristic passes and are presented here
to show the failure modes the analytical framework has to avoid.

## `bobe2` (`0xed107a85...d2e5`)

| Field | Value |
|---|---|
| Lifetime volume | $230,813,138 |
| Lifetime profit | $1,819,722 |
| Wash share | 1.0% (clean) |
| Distinct markets touched in recent activity sample | 62 |

`bobe2` is a real, high-skill, high-volume Polymarket sharp who is not
running an insider playbook. Their Stranger Things "release by X date"
positions are the standout pop-culture exposure in our dataset:

| Stranger Things deadline | NO position | Profit | Return |
|---|---:|---:|---:|
| Released by Wednesday (Jan 7) | $89,673 | $179.71 | 0.20% |
| Released by January 31 | $588,550 | $1,860.04 | 0.32% |
| Released by February 28 | $29,432 | $312.41 | 1.06% |
| Released by March 31 | $144,051 | $685.52 | 0.48% |
| Released by April 30 | $171,501 | $1,030.95 | 0.60% |
| **Stranger Things ladder total** | **$1,023,208** | **$5,068** | **0.495%** |

The wallet is committing a million dollars to extract five thousand
dollars of profit on near-certain NO outcomes priced at $0.985 to $0.999.
This is what professional sweep trading looks like, not what insider
trading looks like. The wallet's broader activity confirms the
characterization: their top markets by USD in the most recent 500 trades
are Iran ceasefire markets ($766K) and not Netflix-related markets at
all. Stranger Things is a side project, not a specialty.

## `no1yet` (`0x4d49acb0...7450`)

| Field | Value |
|---|---|
| Lifetime volume | $9,952,639 |
| Wash share | 19.3% (partial washer) |
| In-scope volume | $1,019,275 |

The same pattern at smaller scale. `no1yet` bought $222,289 of NO on
"Stranger Things by January 14" at $0.998 with 16 hours to resolution,
plus 14 other near-certain late-stage NO bets on Stranger Things and
other release-deadline markets. All correct, all paying single-digit
basis points per trade.

The 19.3% wash share also indicates that even a real, profitable
high-volume sharp is mixing some airdrop-farming behavior into their
book. This is a useful corroboration of the wash-trade thesis.

\pagebreak

# 5. What We Considered and Rejected

Several earlier candidates were promoted in interim drafts and excluded
on closer inspection.

| Wallet | Why excluded |
|---|---|
| `Shalvon` | 91% wash share. The "$20,798 BUY NO on Diddy" trade was paired with a $20,797 SELL NO at the same price 64 minutes later. Net P&L on the position was -$1.24. The wallet is an airdrop farmer. |
| `Niora` | 91% wash share. The $13,714 "Rihanna Baby Girl" bet was a wash pair. |
| `Uvron` | 91% wash share. The Taylor Swift / Travis Kelce engagement bet was a wash pair. |
| `Wyntheris` | 92% wash share. Most "single big bet" patterns are matched immediate-reversal trades. |
| Six fantasy-named wallets (Xalveth, Jaxorian, etc.) | 60% to 77% wash. The vintage clustering pattern was real but the underlying trades were wash, not directional. |

## What the wash-trade pivot revealed about the original heuristic set

The original H1 (4-hour, 20-percentage-point gap) produced zero hits. The
revised H1 (middling-price 0.20 to 0.70, 48-hour pre-resolution, $5K size)
produced 12 hits in the wash-filtered universe, of which 14 trades from
the single wallet `0xafEe` account for the entire population of substantive
H1 evidence. After wash filtering, the H1 signal collapses to one wallet.
That is the actual investigative finding.

# 6. What This Investigation Did Not Find

- **No Polymarket pop-culture analog of the Kalshi YouTube-editor case.**
  Detecting a "production staff trading on their own employer's outcomes"
  pattern requires role-conflict enrichment per market, which is out of
  scope for an automated pass.
- **No confirmed Sybil cluster.** Polygon RPC reads confirm each of the
  flagged volume-farmer wallets has a distinct safe-owner EOA. Without
  funder-graph analysis we cannot say whether multiple wallets share a
  single human operator.
- **No insider candidate at the bobe2 scale.** No wallet with comparable
  lifetime volume to `bobe2` shows H1-qualifying middling-price conviction
  on a Netflix-controlled, label-controlled, or production-controlled
  outcome.

# 7. Recommended Next Steps

Ranked by analytical leverage:

1. **Funder-graph trace on `0xafEe` and the 15 partial-washer candidates
   with non-trivial H1 evidence.** Etherscan v2 API key required.
   Approximately 30 minutes of work. Confirms or refutes whether
   `0xafEe`'s owner EOA is associated with any search-ranking-adjacent
   entity.
2. **Cross-venue check on Kalshi.** Identify whether any of the wash
   wallets or `0xafEe` show on Kalshi against correlated outcomes. Kalshi
   identity-verified data, if accessible, would close several open
   questions.
3. **Real-time Google Trends back-test for the Pope Leo XIV market.**
   Confirm whether the publicly available Trends signal in late November
   already showed d4vd pulling ahead of Pope Leo XIV. If yes, `0xafEe`'s
   edge is plausibly skill rather than asymmetric information. If no,
   the case strengthens.
4. **CLOB cursor-pagination repull of the largest markets** to break past
   the empirical 3,500-trade per-market cap on the original `/trades`
   endpoint. Currently the top 5 markets by trade count are
   under-sampled.

---

*Code, data, and intermediate artifacts:
[github.com/anthonylin99/polymarket-insider-detection](https://github.com/anthonylin99/polymarket-insider-detection)*

*Methodology in detail:
[`report/heuristics.md`](heuristics.md) and
[`report/task1_data_collection.md`](task1_data_collection.md). Data
dictionary: [`data/README.md`](../data/README.md). Per-wallet profiles:
[`data/profiles/`](../data/profiles/).*
