# Task 1 — Data Collection

## What we built

A reproducible, public-API-only pipeline that pulls the full pop-culture
Polymarket trading dataset for the Nov 1 2025 – May 1 2026 challenge window.
No API keys, no scraping, no private data.

Four scripts in `src/`:

| Script | Output | Purpose |
|---|---|---|
| `discover_markets.py` | `markets.csv` + summary | Raw event/market discovery via Gamma `/events` across 16 in-scope tag IDs |
| `filter_markets.py` | `markets_filtered.csv` + summary | Apply window, volume floor, topic exclusions, bucket reclassification |
| `backfill_trades.py` | `trades.csv.gz` + summary | Per-market trade pull via data-api `/trades` with offset pagination |
| `enrich_wallets.py` | `wallets.csv` + summary | Per-wallet enrichment via lb-api profit/volume + data-api value endpoints |

The raw discovery file is preserved separately from the filtered analysis set,
so the next engineer can re-derive the filter with different criteria without
re-hitting the Gamma API.

## Key numbers

| Metric | Value |
|---|---|
| Tag IDs queried | 16 |
| Raw events returned | 6,521 |
| Markets after window + closed + $50K vol + topic filter | **222** |
| Distinct events in filtered set | 63 |
| Total volume in filtered universe | **$228M** |
| Trades pulled | **322,899** |
| Unique wallets in trades | **60,916** |
| Wallets eligible for enrichment (≥3 trades OR ≥$1K vol) | 19,257 |
| Wallets actually enriched (top-by-volume; full run would take ~3h) | **2,994** |
| Enriched wallets with public name/pseudonym | 2,861 (96%) |

Bucket split (filtered markets):

| Bucket | Markets | Notes |
|---|---|---|
| `release_performance` | 193 | Heavily weighted by multi-outcome year-end events (Top Spotify Artist 2025 alone is 30+ child markets) |
| `reality_tv` | 20 | Stranger Things release dates, Beast Games winner, Bachelor/Bachelorette finalists |
| `awards` | 9 | Smaller than ideal — Gamma's awards tagging is sparse; some awards markets land in `release_performance` via the music tag |

## Design decisions and trade-offs

### 1. Why keep the raw discovery file (`markets.csv`)?

The investigation will need to defend its filtering choices to a reviewer. By
shipping the raw output alongside the filtered set, the next engineer (or an
Inca reviewer) can:
- Re-derive the filter with different criteria (e.g., looser volume floor, broader topic keywords)
- Spot-check whether the filter is too aggressive (false negatives)
- Verify the discovery step didn't miss obvious markets

Cost is 3MB of disk and a couple seconds longer git clone. Worth it.

### 2. Why a $50K volume floor?

Below $50K lifetime volume, markets typically have <500 trades and a handful
of distinct wallets — not enough degrees of freedom for the timing-based
heuristics (A1, A2, A3) to produce meaningful signal. A 2026 wallet making a
$200 conviction bet on a $5K market is interesting anthropologically but not
statistically separable from random noise. The floor is documented and
configurable via `--min-volume`.

### 3. Why is `release_performance` so dominant?

Polymarket's year-end "Top X" markets are multi-outcome events that expand into
one binary market per candidate. The "Top Spotify Artist 2025" event has 30+
child markets (Bad Bunny YES/NO, Drake YES/NO, etc.), each tagged separately.
This bloats the count but is a *feature*, not a bug, for our analysis: each
child market resolves at the same instant (year-end), creating a clean
multi-arm dataset for the heuristics — especially A1 (pre-resolution edge),
A2 (pre-announcement cluster), and D8 (Brier accuracy).

### 4. Why offset pagination capped at 10K trades per market?

The data-api `/trades` endpoint paginates with `limit=500, offset=N`. Empirical
testing showed an undocumented server-side cap around 3,500 trades for some
high-volume markets (Bruno Mars Spotify, Bad Bunny Spotify) — `offset > 3500`
returns empty even when the market has more trades. We page until empty and
cap at 10K per market as a safety bound. Markets hitting either cap are
flagged in `trades_backfill_summary.json:per_market[].capped`.

For markets where coverage is partial, the right fix is to switch to the CLOB
`/markets/{conditionId}/trades?cursor=…` endpoint, which uses cursor-based
pagination without the depth cap. Documented as future work; not blocking for
heuristic scoring on the median market.

### 5. Why an activity floor on wallet enrichment?

60,916 unique wallets × 4 API calls each = 244K API requests at ~200ms
sequential = ~14 hours. Even with 10 concurrent workers the public lb-api
throttles us to ~100 wallets/min. The activity floor (≥3 trades OR ≥$1K
in-window volume) reduces the wallet set to 19,257 — the wallets that could
possibly score on multi-trade heuristics. Wallets below the floor cannot
register on B5 (side purity requires ≥5 positions), D8 (Brier requires ≥5
resolved positions), or C6 (size-vs-wallet anomaly is meaningless with
<3 trades).

The script processes wallets in volume-descending order, so the top-N most
insider-relevant accounts are enriched first regardless of how long the full
run takes.

## What's left (for Task 3)

- **Hand-attach `reveal_window_start` to the top 20–30 markets by volume.**
  Heuristic A2 (pre-announcement timing cluster) needs an explicit
  "reveal moment" timestamp per market — e.g., year-end midnight for Spotify
  markets, Oscars broadcast start, episode air time for reality TV. A manual
  pass on ~25 markets covers >80% of the filtered dataset's volume.
- **Resolve the empirical 3,500-trade cap on the largest markets** by switching
  to the CLOB cursor-based endpoint. Only matters for the top ~5 markets by
  trade count; the rest are fully covered.
- **Run `enrich_wallets.py` to completion** — currently checkpointed at the
  top-N most-active wallets, which is sufficient for top-20 ranking. The
  remaining wallets can be enriched lazily during Task 3 if any unenriched
  wallet's heuristic score makes it a candidate.

## Reproducibility

```bash
cd polymarket-insider-detection
pip install -r requirements.txt
python src/discover_markets.py
python src/filter_markets.py
python src/backfill_trades.py
python src/enrich_wallets.py --min-trades 3 --min-volume-usd 1000
```

All scripts deterministic given the same Gamma + data-api response state.
Polymarket data evolves continuously, so re-runs will differ slightly as new
trades are added to existing markets, but the in-window resolved markets are
frozen.
