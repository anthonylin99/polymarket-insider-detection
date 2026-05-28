# Lead Review Methodology

**Scope:** Polymarket media, music, and entertainment markets from November 1,
2025 through May 1, 2026.  
**Purpose:** identify wallets worth investigative follow-up, not prove insider
trading from public data alone.

## Market Scope

The reviewed market universe is stored in `data/markets_reviewed.csv`. It keeps
markets where the outcome can plausibly depend on information known earlier by
a smaller group: music-platform rankings, album or song releases, first-week
sales, awards, creator metrics, and Google Year in Search markets.

The final report does not treat every category equally. Google-search markets
are useful for calibration, but public trend data is a strong alternative
explanation. Release, sales, production-result, and streaming-rank markets are
better places to look for private-information channels.

## Lead Screen

`src/identify_candidate_leads.py` builds the report lead queue from
`data/trades.csv.gz`.

It keeps wallet-market clusters that meet all of these conditions:

- trade timestamp between November 1, 2025 and May 1, 2026
- buy on the side that ultimately resolved as winning
- entry price between 20 and 85 cents
- at least 24 hours before market resolution
- at least $3,000 of notional buying in the same wallet, market, and side

The script then adds wallet metadata, measured wash-like share when available,
activity-cap status, prior median trade size when available, and a plain-English
possible information channel.

`src/analyze_candidate_markets.py` then refreshes the selected markets directly
from the free Polymarket trade API. It measures post-entry contract movement:
entry average, worst price after first buy, worst price after last buy, last
pre-resolution trade, and settlement direction. `src/plot_candidate_market_movements.py`
turns those price points into the chart used in the report.

## Manual Review Rules

I selected follow-up wallets where the trading behavior connected to a specific
information-access hypothesis:

| Pattern | Why it matters |
|---|---|
| Paired positioning inside the same market complex | A wallet expressing both who will and will not win a rank can be more informative than a single lucky trade. |
| Large trade relative to prior wallet behavior | A sudden size jump can matter more than raw dollar size. |
| Long lead time before resolution | Earlier entries are harder to explain as simple endgame cleanup. |
| Topic with a natural private-information owner | Labels, distributors, platforms, production teams, and awards insiders are clearer hypotheses than generic internet attention. |
| Contract movement after entry | A candidate is stronger when the contract later trades against the wallet, recovers, and resolves in the predicted direction. |

The report excludes or downgrades:

- volume farmers with high wash-like share
- near-certain sweep trades priced close to one dollar
- Google-search trades where public trend data is enough to explain the edge
- wallets where the information channel is too vague to investigate

## Known Limits

- The activity endpoint caps many wallets at 2,000 records.
- Wash detection is an operational same-wallet filter, not a shared-funder
  graph.
- Public data cannot establish role conflict or material nonpublic information.
- A strong candidate row means "worth tracing and attributing," not "insider."
