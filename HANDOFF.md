# HANDOFF — Project Brainstorm & Context for Next Engineer

This doc captures the initial brainstorm and the working context behind the heuristics design, so anyone picking this project up has the "why" and not just the "what."

## The challenge in one paragraph

Inca Digital Investigations Analyst take-home. Investigate potential insider/informed trading on Polymarket between Nov 1, 2025 and May 1, 2026. Deliver a written report, the code that collected and analyzed the data, and CSV artifacts. Email to Courtney.fisher@inca.digital. We are picking a niche (pop culture) rather than trying to boil the ocean across politics + sports, both because the universe is tractable and because the analytical angle is differentiated.

## Why pop culture (and not the obvious picks)

We considered four niches: esports (LoL), pop culture, finance, and the obvious politics/sports. Rationale for picking pop culture:

- **Genuine info asymmetry exists.** Reality TV production staff, awards voters, PR firms, studio/label staff all have non-public access to outcomes. The Kalshi YouTube-editor enforcement case (April 2026) is the cleanest publicly adjudicated precedent in this category.
- **Tractable universe.** Estimated 30–80 resolved Polymarket markets in window across reality TV / awards / release performance. Big enough for signal, small enough to spot-check.
- **Differentiated angle.** Every other candidate will submit politics or sports. Pop culture demonstrates judgment about *where* insider risk concentrates.
- **Avoids regulatory third rail.** Framing "finance insider trading" in a job submission is sensitive; pop culture sidesteps that without losing rigor.

Esports (LoL) was the runner-up — a local project (predmonitor) already has LoL market tagging wired up, which would have been a faster start. We chose pop culture anyway because the analytical narrative is stronger.

## Sub-niches in scope

1. **Reality TV eliminations** — Survivor, Love Island, Bachelor/Bachelorette, Big Brother, dance/cooking competitions. Pre-recorded shows are the highest-risk subset (results exist before air).
2. **Awards ceremonies** — Oscars, Grammys, Emmys, Tonys, Met Gala, MTV awards.
3. **Release performance** — opening-weekend box office, first-week album sales, streaming chart position, Rotten Tomatoes score.

Out of scope: celebrity life events, sports, politics, crypto, macro/finance.

## Regulatory landscape (as of May 2026)

- **House Oversight probe (Comer, 2026-05-22)** — letters to Polymarket and Kalshi CEOs requesting documentation on ID verification, geographic enforcement, and anomalous-trade detection. Triggers: 80+ Polymarket wallets making precisely timed wagers before undisclosed US/Israeli strikes on Iran with reported ~98% hit rate, and the unsealed indictment of US Army MSgt Gannon Ken Van Dyke for ~$409K of profits on classified Op. Absolute Resolve.
- **Kalshi enforcement** — three congressional candidates suspended in April 2026 for betting on their own races. YouTube channel editor sanctioned for trading contracts on the same channel's content using pre-release knowledge.
- **CFTC posture** — insider trading on these platforms is illegal and a top enforcement priority.

The investigative bar that emerges: **role-conflict access + precisely timed conviction + abnormal hit rate**. The heuristics are designed to surface that combination.

## Initial heuristic brainstorm (long-list — before pruning)

This was the full set considered before we narrowed to the eight in `report/heuristics.md`:

**Timing**
- Pre-resolution edge (kept as A1, tightened to 4h/≥20pp)
- Pre-announcement reveal-window clustering (kept as A2)
- Dormant-wallet activation (kept as A3)

**Selectivity**
- Single-niche specialist (kept as B4)
- Side purity / directional purity (kept as B5)

**Sizing & conviction**
- Size-vs-wallet anomaly + slippage tolerance (kept as C6)
- Role-conflict adjacency to resolver/production entity (kept as C7, **soft manual-review flag** rather than full automation)

**Outcome accuracy**
- Brier excess accuracy vs. implied (kept as D8)
- Closing-direction precision (kept as D9)

**Network/cluster** (deferred to Task 4 ranking layer, not individual-wallet heuristics)
- Common-funder Sybil cluster
- Counterparty asymmetry (consistently trading against the same retail wallets)

**Anti-signals**
- Doxxed sharps / leaderboard names (soft −0.30)
- Generalist market-makers (soft −0.20)

## Key design decisions and why

- **A1 set tight at 4h/≥20pp** (not 24h/15pp). Pop-culture markets resolve fast — episodes within minutes of air, awards within minutes of envelope-open. A 24h window leaks too many last-day flippers who aren't insiders.
- **C7 is a flag, not a score.** Automating role-conflict adjacency cleanly across all markets is brittle. Better architecture: use it as a high-value enrichment on the top-scoring shortlist from A1/A2/D8, where one true positive (a Van Dyke / YouTube-editor analog) is worth more than 10 generalists. Manual lookup of resolver/production entities per market, 1–3 entries each.
- **Anti-signals are soft, not hard.** A doxxed sharp can still surface if all other signals scream. Hard-exclude risks missing an insider who is also a known sharp.
- **Timing weighted highest in composite (45%).** Timing is the most specific and least gameable signal. Accuracy (30%) is second. Sizing and selectivity are corroborating, not load-bearing. To be sensitivity-tested in Task 4.
- **Threat-model archetypes deferred.** A formal principal/tippee/cluster taxonomy was drafted but pulled — we'll let the data tell us what patterns actually exist before classifying them.

## Reuse note

A separate project at `~/Documents/New project/predmonitor` has Polymarket data infrastructure (LoL-scoped market discovery, RTDS + data-api ingest, wallet P&L scoring, smart-money anomaly detection, resolution polling, semantic clustering). **It was used as pattern reference only.** Per project owner instruction, we do not import, fork, or modify predmonitor. Any logic we want from there is re-implemented clean in this repo.

## Next-engineer playbook

If you're picking this up cold:

1. **Read `report/heuristics.md`** — that's the Task 2 deliverable and the spec for everything downstream.
2. **Task 1 — data collection.**
   - `src/discover_markets.py` — hit Polymarket Gamma `/events` and `/markets` endpoints with a curated keyword set for the three sub-niches. Filter by `endDate` in window. Persist `data/markets.csv` with columns: `market_id, slug, question, category, end_date, resolved_outcome, resolution_price, total_volume_usd, reveal_window_start (hand-attached for A2)`.
   - `src/backfill_trades.py` — hit `data-api.polymarket.com/trades` per market (paginated). Persist `data/trades.csv` with: `trade_id, timestamp, market_id, wallet_address, side (BUY/SELL), outcome (YES/NO), price, size_usd, tx_hash`.
   - `src/enrich_wallets.py` — for each unique wallet that appears in `trades.csv`, fetch Polymarket public profile (lifetime P&L, 30d P&L, total volume, total markets) and persist `data/wallets.csv`.
3. **Task 3 — apply heuristics.**
   - `src/heuristics.py` — one function per heuristic (`score_a1_pre_resolution_edge(wallet_trades, market_metadata) -> float`, etc.). Pure functions, easy to unit-test.
   - Produce `data/wallet_scores.csv` with one row per wallet, columns for each A1–D9 raw score + composite.
4. **Task 4 — composite ranking.**
   - `src/rank.py` — apply weights from `heuristics.md` §6, apply anti-signal penalties, layer cluster-detection (group wallets by common funder address from on-chain trace).
   - Sensitivity test: re-rank with each heuristic dropped one at a time. Top-20 must be stable to ±3 ranks.
   - Produce `data/top20_flagged.csv` and feed the narrative in `report/report.md`.

## Open judgment calls left for the next engineer

- **Sample size floors.** D8 and D9 require resolved positions; B5 requires ≥5 positions. These minimums are first guesses — tune after seeing the wallet distribution.
- **Reveal-window curation for A2.** Box-office windows are softer than awards. The hand-curated table in `markets.csv` should mark uncertain windows and exclude them from A2 scoring per the heuristics doc.
- **Cluster-detection thresholds.** Funder-overlap clustering needs a similarity threshold (shared funder + overlapping market + same side within X minutes). Set after eyeballing the funder graph.
- **Doxxed-sharp list.** Maintain in `src/anti_signals.py` as a manually curated list (Domer, Theo, named leaderboard accounts). Grows as you find more.

## Project owner's stated priorities

- Strong investigative-analyst signal — the deliverable has to land a return interview.
- Tight, defensible top-20 over a broader screen.
- Workshopped iteratively before each task transition (don't barrel ahead).
