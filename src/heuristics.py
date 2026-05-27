"""
heuristics.py
-------------
Compute the eight insider-trading heuristics from report/heuristics.md
across every wallet in data/trades.csv, write data/wallet_scores.csv with
raw + normalized scores per heuristic and a weighted composite, write
data/top20_flagged.csv with the ranked top 20.

Implemented in this pass: A1, A3, B4, B5, C6, D8, D9. Deferred:
  - A2 (pre-announcement timing cluster) — needs hand-curated
    reveal_window_start per market; will be applied on the curated
    subset in a follow-up. Set to 0 in the composite for now.
  - C7 (role-conflict adjacency) — implemented as a *flag* after the
    fact, not a quantitative score. Applied during top-20 investigation.

Anti-signals applied as negative composite adjustments:
  - doxxed sharp: -0.30
  - generalist market-maker: -0.20

Output schema (wallet_scores.csv):
  wallet_address, name, pseudonym, lifetime_volume_usd, lifetime_profit_usd,
  in_window_trade_count, in_window_volume_usd,
  a1_pre_resolution_edge, a3_dormant_activation,
  b4_specialist, b5_side_purity,
  c6_size_anomaly,
  d8_brier_excess, d9_direction_precision,
  antisignal_doxxed, antisignal_marketmaker,
  composite_score, composite_rank
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Heuristic thresholds (locked from report/heuristics.md)
A1_WINDOW_HOURS = 4
A1_PRICE_GAP_MIN = 0.20

A3_DORMANT_DAYS = 30
A3_REACTIVATE_DAYS = 7

B5_MIN_POSITIONS = 5

C6_SIZE_MULTIPLIER = 1.5

D8_MIN_RESOLVED_POSITIONS = 5

# Top-20 eligibility — exclude tiny-volume / few-trade noise wallets where 5 lucky
# correct trades give 100% precision by chance alone. With 60K wallets in the
# dataset, ~2000 will hit perfect 5-trade precision randomly. The activity gate
# below is calibrated so that a flagged wallet would need >$2.5K of conviction
# behind its calls — high enough to be meaningful, low enough to keep insider
# wallets that prefer to size small.
TOP20_MIN_VOLUME_USD = 2500.0
TOP20_MIN_TRADES = 15

# Bayesian shrinkage strength for D8/D9 — scores get multiplied by min(1, n/15)
# so a 5-trade wallet's perfect precision is discounted relative to a 50-trade
# wallet's 80% precision.
CONFIDENCE_PIVOT = 15

# Composite weights
WEIGHTS = {
    "a1": 0.20,
    "a2": 0.15,  # deferred: not scored this pass
    "a3": 0.10,
    "b4": 0.05,
    "b5": 0.05,
    "c6": 0.15,
    "d8": 0.20,
    "d9": 0.10,
}
ANTISIG_DOXXED = -0.30
ANTISIG_MM = -0.20

# Anti-signal: market-maker threshold (touches >= X distinct markets AND has balanced sides)
MM_DISTINCT_MARKETS = 50
MM_SIDE_BALANCE = 0.40  # buys/total between [0.40, 0.60]


def parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def load_markets(path: Path) -> dict[str, dict]:
    """Index filtered markets by condition_id with resolution metadata."""
    out: dict[str, dict] = {}
    for r in csv.DictReader(open(path)):
        cid = r["condition_id"]
        end = parse_ts(r.get("end_date") or "")
        closed_time = parse_ts(r.get("closed_time") or "") or end
        try:
            resolved_price = float(r.get("resolved_price") or 0)
        except ValueError:
            resolved_price = 0.0
        out[cid] = {
            "condition_id": cid,
            "event_id": r["event_id"],
            "question": r["market_question"],
            "bucket": r["bucket"],
            "end_date": end,
            "closed_time": closed_time,
            "resolved_outcome": r.get("resolved_outcome") or "",
            "resolved_price": resolved_price,
            "volume_usd": float(r.get("volume_usd") or 0),
        }
    return out


def load_wallets(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in csv.DictReader(open(path)):
        addr = r["wallet_address"].lower()
        for k in ("lifetime_profit_usd", "profit_30d_usd",
                  "lifetime_volume_usd", "current_portfolio_value_usd"):
            try:
                r[k] = float(r.get(k) or 0)
            except ValueError:
                r[k] = 0.0
        out[addr] = r
    return out


def load_trades(path: Path) -> dict[str, list[dict]]:
    """Group trades by wallet address. Returns {wallet -> [trade, ...]} sorted by ts."""
    by_wallet: dict[str, list[dict]] = defaultdict(list)
    for r in csv.DictReader(open(path)):
        addr = r["wallet_address"].lower()
        if not addr:
            continue
        try:
            r["price"] = float(r["price"])
            r["size_usd"] = float(r["size_usd"])
            r["timestamp"] = parse_ts(r["timestamp_utc"])
        except (ValueError, KeyError):
            continue
        if r["timestamp"] is None:
            continue
        by_wallet[addr].append(r)
    for addr in by_wallet:
        by_wallet[addr].sort(key=lambda t: t["timestamp"])
    return by_wallet


# ---------- HEURISTICS ----------

def h_a1_pre_resolution_edge(trades: list[dict], markets: dict[str, dict]) -> float:
    """For each wallet x market position, score last buy on correct side within 4h of resolution
    at >=20pp price gap. Wallet score = mean over qualifying trades, scaled by min(1, n/3)."""
    by_mkt: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        by_mkt[t["market_condition_id"]].append(t)

    qual_scores: list[float] = []
    for cid, ts in by_mkt.items():
        m = markets.get(cid)
        if not m or not m["closed_time"] or m["resolved_price"] <= 0:
            continue
        # find the wallet's last BUY on the eventually-correct outcome
        buys_correct = [t for t in ts if t["side"] == "BUY" and t["outcome"] == m["resolved_outcome"]]
        if not buys_correct:
            continue
        last = max(buys_correct, key=lambda t: t["timestamp"])
        dt_to_res = (m["closed_time"] - last["timestamp"]).total_seconds() / 3600
        if dt_to_res < 0 or dt_to_res > A1_WINDOW_HOURS:
            continue
        price_gap = abs(m["resolved_price"] - last["price"])
        if price_gap < A1_PRICE_GAP_MIN:
            continue
        time_decay = math.exp(-((dt_to_res * 60) / 120))
        s = min(1.0, price_gap / 0.40) * time_decay
        qual_scores.append(s)

    if not qual_scores:
        return 0.0
    base = statistics.mean(qual_scores)
    return base * min(1.0, len(qual_scores) / 3.0)


def h_a3_dormant_activation(trades: list[dict]) -> float:
    """Wallet inactive >=30d, wakes with single conviction trade, dormant >=7d again.
    Count such events; score = min(1, n/3) weighted by size ratio."""
    if len(trades) < 2:
        return 0.0
    median_size = statistics.median(t["size_usd"] for t in trades)
    events = 0
    score_acc = 0.0
    for i in range(1, len(trades) - 1):
        prev_gap = (trades[i]["timestamp"] - trades[i - 1]["timestamp"]).total_seconds() / 86400
        next_gap = (trades[i + 1]["timestamp"] - trades[i]["timestamp"]).total_seconds() / 86400
        if prev_gap >= A3_DORMANT_DAYS and next_gap >= A3_REACTIVATE_DAYS:
            events += 1
            size_ratio = trades[i]["size_usd"] / max(median_size, 1.0)
            score_acc += min(1.0, size_ratio / 3.0)
    # also check trailing event (last trade with long prior gap)
    if len(trades) >= 2:
        last_gap = (trades[-1]["timestamp"] - trades[-2]["timestamp"]).total_seconds() / 86400
        if last_gap >= A3_DORMANT_DAYS:
            events += 1
            size_ratio = trades[-1]["size_usd"] / max(median_size, 1.0)
            score_acc += min(1.0, size_ratio / 3.0)
    if events == 0:
        return 0.0
    return min(1.0, events / 3.0) * (score_acc / events)


def h_b4_specialist(trades: list[dict], wallet_meta: dict | None) -> float:
    """Concentration on pop-culture (already filtered set) × single-market dominance.
    Requires lifetime volume from wallet enrichment."""
    in_window_vol = sum(t["size_usd"] for t in trades)
    lifetime_vol = (wallet_meta or {}).get("lifetime_volume_usd", 0) or 0
    if lifetime_vol <= 0:
        # If we can't see lifetime, assume the in-window volume IS the lifetime (could be a fresh wallet)
        pop_share = 1.0 if in_window_vol > 0 else 0.0
    else:
        pop_share = min(1.0, in_window_vol / lifetime_vol)
    if pop_share < 0.80:
        return 0.0
    by_mkt_vol: dict[str, float] = defaultdict(float)
    for t in trades:
        by_mkt_vol[t["market_condition_id"]] += t["size_usd"]
    if not by_mkt_vol:
        return 0.0
    concentration = max(by_mkt_vol.values()) / sum(by_mkt_vol.values())
    return pop_share * concentration


def classify_position(trades_for_mkt: list[dict], market: dict) -> str:
    """Classify a wallet's behavior in a single market: buy-and-hold, round-trip, partial-exit, hedged."""
    has_buy = any(t["side"] == "BUY" for t in trades_for_mkt)
    has_sell = any(t["side"] == "SELL" for t in trades_for_mkt)
    outcomes_touched = set(t["outcome"] for t in trades_for_mkt)
    if len(outcomes_touched) > 1:
        return "hedged"
    if has_buy and has_sell:
        return "round-trip"
    if has_buy and not has_sell:
        return "buy-and-hold"
    return "other"


def h_b5_side_purity(trades: list[dict], markets: dict[str, dict]) -> float:
    """Share of positions classified buy-and-hold-to-resolution, requires n>=5."""
    by_mkt: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        by_mkt[t["market_condition_id"]].append(t)
    if len(by_mkt) < B5_MIN_POSITIONS:
        return 0.0
    pure = 0
    n = 0
    for cid, ts in by_mkt.items():
        m = markets.get(cid)
        if not m:
            continue
        n += 1
        if classify_position(ts, m) == "buy-and-hold":
            pure += 1
    if n == 0:
        return 0.0
    return pure / n


def h_c6_size_anomaly(trades: list[dict]) -> float:
    """Flag trades >=1.5x wallet trailing median. Score reflects multiple + (proxy for) slippage.
    We don't have order book depth from the trade-only feed, so we use price-vs-rolling-mean
    as a proxy for slippage tolerance."""
    if len(trades) < 5:
        return 0.0
    sizes = [t["size_usd"] for t in trades]
    median = statistics.median(sizes)
    if median <= 0:
        return 0.0
    flagged = [t for t in trades if t["size_usd"] >= C6_SIZE_MULTIPLIER * median]
    if not flagged:
        return 0.0
    by_mkt_prices: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        by_mkt_prices[t["market_condition_id"]].append(t["price"])
    scores = []
    for t in flagged:
        mp = by_mkt_prices[t["market_condition_id"]]
        if len(mp) < 3:
            slip_proxy = 0.5
        else:
            mean_p = statistics.mean(mp)
            slip_proxy = min(1.0, abs(t["price"] - mean_p) / 0.10)
        size_mult = t["size_usd"] / median
        s = min(1.0, size_mult / 5.0) * slip_proxy
        scores.append(s)
    return statistics.mean(scores) if scores else 0.0


def h_d8_brier(trades: list[dict], markets: dict[str, dict]) -> float:
    """Excess accuracy vs market-implied. Brier of implied prob at trade time vs binary
    resolution outcome. Compare against expected Brier under perfect calibration."""
    impl_probs = []
    outcomes = []
    for t in trades:
        m = markets.get(t["market_condition_id"])
        if not m or not m["resolved_outcome"]:
            continue
        if t["side"] != "BUY":
            continue
        # implied probability that the eventually-correct outcome wins, at trade time
        # if wallet bought the correct outcome at price p, market said p; if bought wrong outcome, market said 1-p
        if t["outcome"] == m["resolved_outcome"]:
            impl = t["price"]
            outcome = 1.0
        else:
            impl = 1 - t["price"]
            outcome = 1.0  # the correct outcome did happen; market said impl
        impl_probs.append(impl)
        outcomes.append(outcome)
    if len(impl_probs) < D8_MIN_RESOLVED_POSITIONS:
        return 0.0
    # actual Brier: how wrong was the market at trade time, given we know what happened?
    actual_brier = statistics.mean((p - o) ** 2 for p, o in zip(impl_probs, outcomes))
    # expected Brier under no-info (use base rate of outcome happening, which is 1.0 by construction)
    # So expected = mean((mean(impl_probs) - 1)^2) is a poor baseline.
    # Better: compare to "wallet bought random outcome" baseline = 0.5
    baseline_brier = statistics.mean((0.5 - o) ** 2 for o in outcomes)  # = 0.25
    excess = max(0.0, baseline_brier - actual_brier)
    return min(1.0, excess / 0.15)


def h_d9_direction_precision(trades: list[dict], markets: dict[str, dict]) -> float:
    """Fraction of trades where direction matched final price move."""
    correct = 0
    n = 0
    for t in trades:
        m = markets.get(t["market_condition_id"])
        if not m or m["resolved_price"] <= 0:
            continue
        # For a BUY on outcome X: profitable if outcome resolves YES at price > entry
        if t["outcome"] == m["resolved_outcome"]:
            res_price_for_outcome = m["resolved_price"]
        else:
            res_price_for_outcome = 1 - m["resolved_price"]
        move = res_price_for_outcome - t["price"]
        # BUY profitable when move > 0; SELL profitable when move < 0
        is_correct = (t["side"] == "BUY" and move > 0) or (t["side"] == "SELL" and move < 0)
        if is_correct:
            correct += 1
        n += 1
    if n < 5:
        return 0.0
    precision = correct / n
    return max(0.0, min(1.0, (precision - 0.55) / 0.30))


# ---------- ANTI-SIGNALS ----------

DOXXED_SHARPS = {
    "domer", "theo", "luenberger", "fishhead", "abc",  # placeholder names; expand from leaderboard
}


def antisig_doxxed(wallet_meta: dict | None) -> float:
    if not wallet_meta:
        return 0.0
    name = (wallet_meta.get("name") or "").lower().strip()
    if name in DOXXED_SHARPS:
        return ANTISIG_DOXXED
    return 0.0


def antisig_marketmaker(trades: list[dict], wallet_meta: dict | None) -> float:
    """Touches many distinct markets with balanced buy/sell."""
    distinct = len(set(t["market_condition_id"] for t in trades))
    if distinct < MM_DISTINCT_MARKETS:
        return 0.0
    buys = sum(1 for t in trades if t["side"] == "BUY")
    total = len(trades)
    if total == 0:
        return 0.0
    ratio = buys / total
    if MM_SIDE_BALANCE <= ratio <= (1 - MM_SIDE_BALANCE):
        return ANTISIG_MM
    return 0.0


# ---------- MAIN ----------

def main() -> int:
    markets = load_markets(DATA / "markets_filtered.csv")
    wallets = load_wallets(DATA / "wallets.csv")
    print(f"loaded {len(markets)} markets, {len(wallets)} enriched wallets", file=sys.stderr)
    by_wallet = load_trades(DATA / "trades.csv")
    print(f"loaded {len(by_wallet)} wallet trade histories", file=sys.stderr)

    rows: list[dict] = []
    for i, (addr, trades) in enumerate(by_wallet.items(), start=1):
        if i % 5000 == 0:
            print(f"  scored {i}/{len(by_wallet)}", file=sys.stderr)
        if len(trades) < 2:
            continue

        wmeta = wallets.get(addr)
        confidence = min(1.0, len(trades) / CONFIDENCE_PIVOT)
        a1 = h_a1_pre_resolution_edge(trades, markets)
        a3 = h_a3_dormant_activation(trades)
        b4 = h_b4_specialist(trades, wmeta)
        b5 = h_b5_side_purity(trades, markets)
        c6 = h_c6_size_anomaly(trades)
        d8 = h_d8_brier(trades, markets) * confidence
        d9 = h_d9_direction_precision(trades, markets) * confidence
        as_dox = antisig_doxxed(wmeta)
        as_mm = antisig_marketmaker(trades, wmeta)

        composite = (
            WEIGHTS["a1"] * a1
            + WEIGHTS["a3"] * a3
            + WEIGHTS["b4"] * b4
            + WEIGHTS["b5"] * b5
            + WEIGHTS["c6"] * c6
            + WEIGHTS["d8"] * d8
            + WEIGHTS["d9"] * d9
            + as_dox
            + as_mm
        )

        in_window_vol = sum(t["size_usd"] for t in trades)
        rows.append({
            "wallet_address": addr,
            "name": (wmeta or {}).get("name") or "",
            "pseudonym": (wmeta or {}).get("pseudonym") or "",
            "lifetime_volume_usd": (wmeta or {}).get("lifetime_volume_usd", 0) or 0,
            "lifetime_profit_usd": (wmeta or {}).get("lifetime_profit_usd", 0) or 0,
            "in_window_trade_count": len(trades),
            "in_window_volume_usd": round(in_window_vol, 2),
            "distinct_markets": len(set(t["market_condition_id"] for t in trades)),
            "a1_pre_resolution_edge": round(a1, 4),
            "a3_dormant_activation": round(a3, 4),
            "b4_specialist": round(b4, 4),
            "b5_side_purity": round(b5, 4),
            "c6_size_anomaly": round(c6, 4),
            "d8_brier_excess": round(d8, 4),
            "d9_direction_precision": round(d9, 4),
            "antisignal_doxxed": as_dox,
            "antisignal_marketmaker": as_mm,
            "composite_score": round(composite, 4),
        })

    rows.sort(key=lambda r: -r["composite_score"])
    for rk, r in enumerate(rows, start=1):
        r["composite_rank"] = rk

    out_path = DATA / "wallet_scores.csv"
    fieldnames = list(rows[0].keys()) if rows else []
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # Top-20 eligibility: filter out lucky tiny-volume wallets.
    eligible = [
        r for r in rows
        if r["in_window_volume_usd"] >= TOP20_MIN_VOLUME_USD
        and r["in_window_trade_count"] >= TOP20_MIN_TRADES
    ]
    print(f"top-20 eligible after activity gate: {len(eligible)}", file=sys.stderr)
    top20 = eligible[:20]
    with (DATA / "top20_flagged.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(top20)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "wallets_scored": len(rows),
        "wallets_with_a1_signal": sum(1 for r in rows if r["a1_pre_resolution_edge"] > 0),
        "wallets_with_a3_signal": sum(1 for r in rows if r["a3_dormant_activation"] > 0),
        "wallets_with_b4_signal": sum(1 for r in rows if r["b4_specialist"] > 0),
        "wallets_with_b5_signal": sum(1 for r in rows if r["b5_side_purity"] > 0),
        "wallets_with_c6_signal": sum(1 for r in rows if r["c6_size_anomaly"] > 0),
        "wallets_with_d8_signal": sum(1 for r in rows if r["d8_brier_excess"] > 0),
        "wallets_with_d9_signal": sum(1 for r in rows if r["d9_direction_precision"] > 0),
        "doxxed_flagged": sum(1 for r in rows if r["antisignal_doxxed"] < 0),
        "marketmaker_flagged": sum(1 for r in rows if r["antisignal_marketmaker"] < 0),
        "weights": WEIGHTS,
    }
    with (DATA / "wallet_scores_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nwrote {len(rows)} wallet scores → {out_path}", file=sys.stderr)
    print(f"top 20 flagged → {DATA / 'top20_flagged.csv'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
