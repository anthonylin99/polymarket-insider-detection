"""
score_wallets.py
----------------
Conservative scoring for the Inca submission.

The score treats middling-price, correct-side conviction as the primary signal
and moves near-certain sweep trading into an anti-signal / benign-sharp label.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Tier 1 (ranking) thresholds. Stricter than the Tier 2 triage screen in
# identify_candidate_leads.py (20-85c / $3,000 / 24h) on purpose: this stage
# ranks the whole wallet universe, so a tighter band keeps the score precise.
# See report/heuristics.md "Two-tier screening".
PRIMARY_PRICE_LO = 0.20
PRIMARY_PRICE_HI = 0.70
PRIMARY_MIN_SIZE_USD = 5_000.0
PRIMARY_MIN_HOURS_PRE_RES = 48.0
PRIMARY_PROFIT_CAP_USD = 100_000.0

SIZE_ANOMALY_MIN_PRIOR_TRADES = 30
SIZE_ANOMALY_MIN_SIZE_USD = 5_000.0
SIZE_ANOMALY_MEDIAN_MULTIPLIER = 50.0

ACCURACY_PRICE_LO = 0.20
ACCURACY_PRICE_HI = 0.80
ACCURACY_MIN_SIZE_USD = 1_000.0
ACCURACY_CONFIDENCE_PIVOT = 20

MIN_RANK_VOLUME_USD = 5_000.0
VOLUME_FARMER_WASH_SHARE = 0.50
ACTIVITY_CAP_RECORDS = 2_000

WEIGHTS = {
    "primary_conviction_signal": 0.60,
    "size_anomaly_signal": 0.20,
    "scope_concentration_signal": 0.10,
    "middling_price_accuracy_signal": 0.10,
    "sweep_penalty": -0.20,
}


def parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None


def load_markets(path: Path) -> dict[str, dict]:
    markets = {}
    for row in csv.DictReader(open(path)):
        cid = row["condition_id"]
        row["closed_time_dt"] = parse_ts(row.get("closed_time") or row.get("end_date") or "")
        row["volume_usd_float"] = float(row.get("volume_usd") or 0)
        markets[cid] = row
    return markets


def load_activity(path: Path) -> dict[str, list[dict]]:
    by_wallet: dict[str, list[dict]] = defaultdict(list)
    for row in csv.DictReader(open(path)):
        try:
            row["price"] = float(row["price"])
            row["size_usdc"] = float(row["size_usdc"])
            row["timestamp_unix"] = int(row["timestamp_unix"])
            row["timestamp_dt"] = parse_ts(row["timestamp_utc"])
        except (KeyError, ValueError):
            continue
        if row["timestamp_dt"] is None:
            continue
        by_wallet[row["wallet_address"].lower()].append(row)
    for trades in by_wallet.values():
        trades.sort(key=lambda r: r["timestamp_unix"])
    return by_wallet


def load_wash_stats(path: Path) -> dict[str, dict]:
    stats = {}
    for row in csv.DictReader(open(path)):
        for key in ("total_vol_usd", "wash_vol_usd", "clean_vol_usd", "wash_vol_share", "wash_n_share"):
            row[key] = float(row.get(key) or 0)
        for key in ("total_n", "wash_n"):
            row[key] = int(row.get(key) or 0)
        stats[row["wallet_address"].lower()] = row
    return stats


def primary_conviction_signal(trades: list[dict], markets: dict[str, dict]) -> tuple[float, list[dict]]:
    hits = []
    for trade in trades:
        market = markets.get(trade["condition_id"])
        if not market or not market["closed_time_dt"]:
            continue
        if trade["side"] != "BUY" or trade["outcome"] != market.get("resolved_outcome"):
            continue
        if not (PRIMARY_PRICE_LO <= trade["price"] <= PRIMARY_PRICE_HI):
            continue
        if trade["size_usdc"] < PRIMARY_MIN_SIZE_USD:
            continue
        hours_pre_res = (market["closed_time_dt"] - trade["timestamp_dt"]).total_seconds() / 3600
        if hours_pre_res < PRIMARY_MIN_HOURS_PRE_RES:
            continue
        implied_profit = (1 - trade["price"]) / trade["price"] * trade["size_usdc"]
        hits.append({
            "trade": trade,
            "market": market,
            "hours_pre_res": hours_pre_res,
            "implied_profit_usd": implied_profit,
        })
    total_profit = sum(h["implied_profit_usd"] for h in hits)
    return min(1.0, total_profit / PRIMARY_PROFIT_CAP_USD), hits


def size_anomaly_signal(trades: list[dict], in_scope_ids: set[str]) -> tuple[float, int]:
    hits = 0
    prior_sizes: list[float] = []
    for trade in trades:
        if trade["condition_id"] in in_scope_ids and trade["size_usdc"] >= SIZE_ANOMALY_MIN_SIZE_USD:
            if len(prior_sizes) >= SIZE_ANOMALY_MIN_PRIOR_TRADES:
                median_prior = statistics.median(prior_sizes)
                if median_prior > 0 and trade["size_usdc"] / median_prior >= SIZE_ANOMALY_MEDIAN_MULTIPLIER:
                    hits += 1
        prior_sizes.append(trade["size_usdc"])
    return min(1.0, hits / 5.0), hits


def scope_concentration_signal(trades: list[dict], markets: dict[str, dict]) -> float:
    total_vol = sum(t["size_usdc"] for t in trades)
    in_scope = [t for t in trades if t["condition_id"] in markets]
    in_scope_vol = sum(t["size_usdc"] for t in in_scope)
    if total_vol <= 0 or in_scope_vol <= 0:
        return 0.0
    by_event = Counter()
    for trade in in_scope:
        event_id = markets[trade["condition_id"]].get("event_id") or trade["condition_id"]
        by_event[event_id] += trade["size_usdc"]
    max_event_share = max(by_event.values()) / in_scope_vol if by_event else 0.0
    return (in_scope_vol / total_vol) * max_event_share


def middling_price_accuracy_signal(trades: list[dict], markets: dict[str, dict]) -> tuple[float, int, float]:
    n = 0
    correct = 0
    for trade in trades:
        if trade["condition_id"] not in markets:
            continue
        if trade["side"] != "BUY" or trade["size_usdc"] < ACCURACY_MIN_SIZE_USD:
            continue
        if not (ACCURACY_PRICE_LO <= trade["price"] <= ACCURACY_PRICE_HI):
            continue
        n += 1
        if trade["outcome"] == markets[trade["condition_id"]].get("resolved_outcome"):
            correct += 1
    if n == 0:
        return 0.0, 0, 0.0
    hit_rate = correct / n
    shrink = min(1.0, n / ACCURACY_CONFIDENCE_PIVOT)
    score = max(0.0, min(1.0, (hit_rate - 0.65) / 0.35)) * shrink
    return score, n, hit_rate


def sweep_penalty(trades: list[dict], markets: dict[str, dict]) -> tuple[float, float]:
    buy_vol = 0.0
    near_certain_correct_vol = 0.0
    for trade in trades:
        if trade["condition_id"] not in markets or trade["side"] != "BUY":
            continue
        buy_vol += trade["size_usdc"]
        if trade["price"] >= 0.90 and trade["outcome"] == markets[trade["condition_id"]].get("resolved_outcome"):
            near_certain_correct_vol += trade["size_usdc"]
    if buy_vol <= 0:
        return 0.0, 0.0
    share = near_certain_correct_vol / buy_vol
    score = min(1.0, near_certain_correct_vol / 50_000.0) * share
    return score, share


def confidence_label(row: dict) -> str:
    if row["wash_vol_share"] >= VOLUME_FARMER_WASH_SHARE:
        return "Volume farmer"
    if row["in_scope_volume_usd"] < MIN_RANK_VOLUME_USD:
        return "Insufficient data"
    if row["primary_signal_trade_count"] >= 3 and row["primary_signal_notional_usd"] >= 100_000 and row["wash_vol_share"] < 0.10:
        return "Lead"
    if row["primary_signal_trade_count"] > 0 or (row["composite_score"] >= 0.20 and row["sweep_penalty"] < 0.45):
        return "Watchlist"
    if row["sweep_penalty"] >= 0.45 and row["primary_signal_trade_count"] == 0:
        return "Benign sharp"
    return "Insufficient data"


def composite_from(row: dict, drop: str | None = None) -> float:
    parts = {
        "primary_conviction_signal": WEIGHTS["primary_conviction_signal"] * row["primary_conviction_signal"],
        "size_anomaly_signal": WEIGHTS["size_anomaly_signal"] * row["size_anomaly_signal"],
        "scope_concentration_signal": WEIGHTS["scope_concentration_signal"] * row["scope_concentration_signal"],
        "middling_price_accuracy_signal": WEIGHTS["middling_price_accuracy_signal"] * row["middling_price_accuracy_signal"],
        "sweep_penalty": WEIGHTS["sweep_penalty"] * row["sweep_penalty"],
    }
    if drop:
        parts[drop] = 0.0
    return max(0.0, sum(parts.values()))


def rank_rows(rows: list[dict], score_key: str) -> dict[str, int]:
    ranked = sorted(rows, key=lambda r: (-r[score_key], r["wallet_address"]))
    return {row["wallet_address"]: i for i, row in enumerate(ranked, start=1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default=str(DATA / "markets_reviewed.csv"))
    ap.add_argument("--activity", default=str(DATA / "activity_clean.csv"))
    ap.add_argument("--wash-stats", default=str(DATA / "wallet_wash_stats.csv"))
    ap.add_argument("--scores-out", default=str(DATA / "wallet_scores_reviewed.csv"))
    ap.add_argument("--top-out", default=str(DATA / "top20_reviewed.csv"))
    ap.add_argument("--primary-signal-out", default=str(DATA / "primary_signal_evidence.csv"))
    ap.add_argument("--sensitivity-out", default=str(DATA / "rank_sensitivity.csv"))
    ap.add_argument("--summary", default=str(DATA / "wallet_scores_reviewed_summary.json"))
    args = ap.parse_args()

    markets = load_markets(Path(args.markets))
    activity = load_activity(Path(args.activity))
    wash_stats = load_wash_stats(Path(args.wash_stats))
    in_scope_ids = set(markets)

    rows: list[dict] = []
    primary_hits_by_wallet: dict[str, list[dict]] = {}
    for addr, trades in activity.items():
        in_scope_trades = [t for t in trades if t["condition_id"] in in_scope_ids]
        in_scope_volume = sum(t["size_usdc"] for t in in_scope_trades)
        primary_score, primary_hits = primary_conviction_signal(trades, markets)
        h2, h2_hits = size_anomaly_signal(trades, in_scope_ids)
        h3 = scope_concentration_signal(trades, markets)
        h4, h4_n, h4_hit_rate = middling_price_accuracy_signal(trades, markets)
        sweep, sweep_share = sweep_penalty(trades, markets)
        stats = wash_stats.get(addr, {})

        raw_activity_records = int(stats.get("total_n", len(trades)) or len(trades))
        row = {
            "wallet_address": addr,
            "in_scope_trade_count": len(in_scope_trades),
            "in_scope_volume_usd": round(in_scope_volume, 2),
            "clean_activity_records": len(trades),
            "raw_activity_records": raw_activity_records,
            "activity_capped": raw_activity_records >= ACTIVITY_CAP_RECORDS,
            "wash_vol_share": round(float(stats.get("wash_vol_share", 0.0)), 4),
            "wash_label": stats.get("label", ""),
            "primary_conviction_signal": round(primary_score, 4),
            "primary_signal_trade_count": len(primary_hits),
            "primary_signal_notional_usd": round(sum(h["trade"]["size_usdc"] for h in primary_hits), 2),
            "primary_signal_implied_profit_usd": round(sum(h["implied_profit_usd"] for h in primary_hits), 2),
            "size_anomaly_signal": round(h2, 4),
            "size_anomaly_trade_count": h2_hits,
            "scope_concentration_signal": round(h3, 4),
            "middling_price_accuracy_signal": round(h4, 4),
            "middling_price_trade_count": h4_n,
            "middling_price_hit_rate": round(h4_hit_rate, 4),
            "sweep_penalty": round(sweep, 4),
            "near_certain_correct_share": round(sweep_share, 4),
        }
        row["composite_score"] = round(composite_from(row), 4)
        row["confidence_label"] = confidence_label(row)
        rows.append(row)
        primary_hits_by_wallet[addr] = primary_hits

    rows.sort(key=lambda r: (-r["composite_score"], r["wallet_address"]))
    for rank, row in enumerate(rows, start=1):
        row["composite_rank"] = rank

    fieldnames = [
        "wallet_address", "confidence_label", "composite_rank", "composite_score",
        "in_scope_trade_count", "in_scope_volume_usd", "clean_activity_records", "raw_activity_records",
        "activity_capped", "wash_vol_share", "wash_label",
        "primary_conviction_signal", "primary_signal_trade_count", "primary_signal_notional_usd", "primary_signal_implied_profit_usd",
        "size_anomaly_signal", "size_anomaly_trade_count", "scope_concentration_signal",
        "middling_price_accuracy_signal", "middling_price_trade_count", "middling_price_hit_rate",
        "sweep_penalty", "near_certain_correct_share",
    ]
    with open(args.scores_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    eligible = [
        r for r in rows
        if r["wash_vol_share"] < VOLUME_FARMER_WASH_SHARE
        and r["in_scope_volume_usd"] >= MIN_RANK_VOLUME_USD
    ]
    eligible.sort(key=lambda r: (-r["composite_score"], r["wallet_address"]))
    top20 = eligible[:20]
    with open(args.top_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(top20)

    primary_rows = []
    for row in top20:
        for hit in primary_hits_by_wallet.get(row["wallet_address"], []):
            trade = hit["trade"]
            market = hit["market"]
            primary_rows.append({
                "wallet_address": row["wallet_address"],
                "market_condition_id": market["condition_id"],
                "market_question": market["market_question"],
                "topic_label": market.get("topic_label", ""),
                "resolved_outcome": market["resolved_outcome"],
                "side_outcome": trade["outcome"],
                "buy_price": round(trade["price"], 6),
                "buy_size_usd": round(trade["size_usdc"], 2),
                "hours_pre_res": round(hit["hours_pre_res"], 1),
                "implied_profit_usd": round(hit["implied_profit_usd"], 2),
                "buy_timestamp_utc": trade["timestamp_utc"],
            })
    if primary_rows:
        with open(args.primary_signal_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(primary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(sorted(primary_rows, key=lambda r: r["buy_timestamp_utc"]))

    sensitivity_fields = [
        "wallet_address", "base_rank", "base_score",
        "rank_without_primary_signal", "rank_without_size_anomaly", "rank_without_scope_concentration",
        "rank_without_middling_accuracy", "rank_without_sweep_penalty", "max_rank_delta",
    ]
    alt_rows = [dict(r) for r in eligible]
    rank_maps = {"base": rank_rows(alt_rows, "composite_score")}
    drops = {
        "rank_without_primary_signal": "primary_conviction_signal",
        "rank_without_size_anomaly": "size_anomaly_signal",
        "rank_without_scope_concentration": "scope_concentration_signal",
        "rank_without_middling_accuracy": "middling_price_accuracy_signal",
        "rank_without_sweep_penalty": "sweep_penalty",
    }
    for out_col, drop_key in drops.items():
        for row in alt_rows:
            row[out_col] = round(composite_from(row, drop=drop_key), 4)
        rank_maps[out_col] = rank_rows(alt_rows, out_col)

    sensitivity = []
    for row in top20:
        base_rank = rank_maps["base"][row["wallet_address"]]
        ranks = {col: rank_maps[col][row["wallet_address"]] for col in drops}
        sensitivity.append({
            "wallet_address": row["wallet_address"],
            "base_rank": base_rank,
            "base_score": row["composite_score"],
            **ranks,
            "max_rank_delta": max(abs(v - base_rank) for v in ranks.values()),
        })
    with open(args.sensitivity_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sensitivity_fields)
        writer.writeheader()
        writer.writerows(sensitivity)

    label_counts = Counter(r["confidence_label"] for r in rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "markets_used": len(markets),
        "wallets_scored": len(rows),
        "eligible_ranked_wallets": len(eligible),
        "confidence_label_counts": dict(label_counts),
        "wallets_with_primary_signal": sum(1 for r in rows if r["primary_signal_trade_count"] > 0),
        "wallets_with_size_anomaly": sum(1 for r in rows if r["size_anomaly_trade_count"] > 0),
        "wallets_activity_capped": sum(1 for r in rows if r["activity_capped"]),
        "weights": WEIGHTS,
        "thresholds": {
            "primary_signal_price_band": [PRIMARY_PRICE_LO, PRIMARY_PRICE_HI],
            "primary_signal_min_size_usd": PRIMARY_MIN_SIZE_USD,
            "primary_signal_min_hours_pre_resolution": PRIMARY_MIN_HOURS_PRE_RES,
            "size_anomaly_min_prior_trades": SIZE_ANOMALY_MIN_PRIOR_TRADES,
            "size_anomaly_median_multiplier": SIZE_ANOMALY_MEDIAN_MULTIPLIER,
            "volume_farmer_wash_share": VOLUME_FARMER_WASH_SHARE,
            "activity_cap_records": ACTIVITY_CAP_RECORDS,
        },
    }
    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
