"""
analyze_candidate_markets.py
----------------------------
Pull free Polymarket trade data for selected lead markets and summarize how
each contract traded after the candidate wallet entered.

This complements the wallet screen: a suspicious entry is stronger when the
market later confirms the direction and weaker when the price action was already
fully obvious at entry.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"

DATA_API = "https://data-api.polymarket.com/trades"
HEADERS = {"User-Agent": "polymarket-insider-detection/0.1 (research)"}
PAGE_SIZE = 500


def parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None


def fetch_market_trades(condition_id: str, max_trades: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while len(rows) < max_trades:
        r = requests.get(
            DATA_API,
            params={"market": condition_id, "limit": PAGE_SIZE, "offset": offset},
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        page = r.json()
        if not page:
            break
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.1)
    return rows[:max_trades]


def trade_value_usd(trade: dict) -> float:
    return float(trade.get("price") or 0) * float(trade.get("size") or 0)


def normalize_trade(trade: dict) -> dict:
    ts = datetime.fromtimestamp(int(trade["timestamp"]), tz=timezone.utc)
    return {
        "timestamp_dt": ts,
        "timestamp_utc": ts.isoformat(),
        "wallet_address": (trade.get("proxyWallet") or "").lower(),
        "side": trade.get("side") or "",
        "outcome": trade.get("outcome") or "",
        "price": float(trade.get("price") or 0),
        "size_usd": trade_value_usd(trade),
        "tx_hash": trade.get("transactionHash") or "",
    }


def weighted_avg(rows: list[dict]) -> float:
    total = sum(r["size_usd"] for r in rows)
    if total <= 0:
        return 0.0
    return sum(r["price"] * r["size_usd"] for r in rows) / total


def nearest_price(rows: list[dict], ts: datetime, direction: str) -> dict | None:
    if direction == "before":
        candidates = [r for r in rows if r["timestamp_dt"] <= ts]
        return candidates[-1] if candidates else None
    candidates = [r for r in rows if r["timestamp_dt"] >= ts]
    return candidates[0] if candidates else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(DATA / "candidate_wallet_leads.csv"))
    ap.add_argument("--markets", default=str(DATA / "markets_reviewed.csv"))
    ap.add_argument("--out", default=str(DATA / "candidate_market_movements.csv"))
    ap.add_argument("--price-points-out", default=str(DATA / "candidate_market_price_points.csv"))
    ap.add_argument("--summary", default=str(DATA / "candidate_market_movements_summary.json"))
    ap.add_argument("--max-trades-per-market", type=int, default=5_000)
    args = ap.parse_args()

    markets = {r["condition_id"]: r for r in csv.DictReader(open(args.markets))}
    candidates = [
        r for r in csv.DictReader(open(args.candidates))
        if r["review_label"] == "Selected follow-up"
    ]
    if not candidates:
        print("no selected follow-up rows found", file=sys.stderr)
        return 1

    fetched_by_market: dict[str, list[dict]] = {}
    output_rows: list[dict] = []
    price_points: list[dict] = []
    for candidate in candidates:
        cid = candidate["market_condition_id"]
        market = markets[cid]
        closed_dt = parse_ts(market.get("closed_time") or market.get("end_date") or "")
        if closed_dt is None:
            continue
        if cid not in fetched_by_market:
            raw = fetch_market_trades(cid, args.max_trades_per_market)
            normalized = [normalize_trade(r) for r in raw]
            # De-duplicate by transaction hash, timestamp, wallet, and outcome.
            seen = set()
            clean = []
            for row in normalized:
                key = (row["tx_hash"], row["timestamp_utc"], row["wallet_address"], row["outcome"], row["side"])
                if key in seen:
                    continue
                seen.add(key)
                clean.append(row)
            fetched_by_market[cid] = sorted(clean, key=lambda r: r["timestamp_dt"])

        all_rows = fetched_by_market[cid]
        outcome_rows = [r for r in all_rows if r["outcome"] == candidate["side_bought"]]
        target_buys = [
            r for r in outcome_rows
            if r["wallet_address"] == candidate["wallet_address"]
            and r["side"] == "BUY"
            and 0.20 <= r["price"] <= 0.85
        ]
        if not target_buys:
            continue
        first_buy = min(target_buys, key=lambda r: r["timestamp_dt"])
        last_buy = max(target_buys, key=lambda r: r["timestamp_dt"])
        after_first = [r for r in outcome_rows if first_buy["timestamp_dt"] <= r["timestamp_dt"] <= closed_dt]
        after_last = [r for r in outcome_rows if last_buy["timestamp_dt"] <= r["timestamp_dt"] <= closed_dt]
        if not after_first:
            continue

        before_first = nearest_price(outcome_rows, first_buy["timestamp_dt"], "before")
        min_after = min(after_first, key=lambda r: r["price"])
        max_after = max(after_first, key=lambda r: r["price"])
        min_after_last = min(after_last, key=lambda r: r["price"]) if after_last else min_after
        last_pre_close = nearest_price(outcome_rows, closed_dt, "before")
        avg_entry = weighted_avg(target_buys)
        notional = sum(r["size_usd"] for r in target_buys)
        hours_first_to_resolution = (closed_dt - first_buy["timestamp_dt"]).total_seconds() / 3600
        hours_last_to_resolution = (closed_dt - last_buy["timestamp_dt"]).total_seconds() / 3600

        output_rows.append({
            "wallet_address": candidate["wallet_address"],
            "wallet_pseudonym": candidate["wallet_pseudonym"],
            "market_condition_id": cid,
            "market_question": candidate["market_question"],
            "resolved_outcome": market.get("resolved_outcome", ""),
            "side_bought": candidate["side_bought"],
            "api_trades_pulled": len(all_rows),
            "outcome_contract_trades": len(outcome_rows),
            "candidate_buy_trades": len(target_buys),
            "candidate_buy_notional_usd": round(notional, 2),
            "candidate_avg_entry_price": round(avg_entry, 4),
            "candidate_first_buy_utc": first_buy["timestamp_utc"],
            "candidate_last_buy_utc": last_buy["timestamp_utc"],
            "hours_first_buy_to_resolution": round(hours_first_to_resolution, 1),
            "hours_last_buy_to_resolution": round(hours_last_to_resolution, 1),
            "price_at_or_before_first_buy": "" if not before_first else round(before_first["price"], 4),
            "min_price_after_first_buy": round(min_after["price"], 4),
            "min_price_after_first_buy_utc": min_after["timestamp_utc"],
            "min_price_after_last_buy": round(min_after_last["price"], 4),
            "min_price_after_last_buy_utc": min_after_last["timestamp_utc"],
            "max_price_after_first_buy": round(max_after["price"], 4),
            "max_price_after_first_buy_utc": max_after["timestamp_utc"],
            "last_price_before_resolution": "" if not last_pre_close else round(last_pre_close["price"], 4),
            "last_price_before_resolution_utc": "" if not last_pre_close else last_pre_close["timestamp_utc"],
            "settlement_price": 1.0,
            "entry_to_last_price_change": "" if not last_pre_close else round(last_pre_close["price"] - avg_entry, 4),
            "worst_drawdown_after_first_buy": round(min_after["price"] - avg_entry, 4),
            "worst_drawdown_after_last_buy": round(min_after_last["price"] - avg_entry, 4),
        })

        duration_seconds = max(1.0, (closed_dt - first_buy["timestamp_dt"]).total_seconds())
        label = f"{candidate['wallet_pseudonym']} - {candidate['market_question']}"
        for point in after_first:
            rel = (point["timestamp_dt"] - first_buy["timestamp_dt"]).total_seconds() / duration_seconds
            price_points.append({
                "wallet_pseudonym": candidate["wallet_pseudonym"],
                "market_condition_id": cid,
                "market_question": candidate["market_question"],
                "chart_label": label,
                "timestamp_utc": point["timestamp_utc"],
                "relative_time_to_resolution": round(rel, 6),
                "price": round(point["price"], 6),
                "is_candidate_buy": point["wallet_address"] == candidate["wallet_address"] and point["side"] == "BUY",
            })

    fieldnames = [
        "wallet_address", "wallet_pseudonym", "market_condition_id", "market_question",
        "resolved_outcome", "side_bought", "api_trades_pulled", "outcome_contract_trades",
        "candidate_buy_trades", "candidate_buy_notional_usd", "candidate_avg_entry_price",
        "candidate_first_buy_utc", "candidate_last_buy_utc", "hours_first_buy_to_resolution",
        "hours_last_buy_to_resolution", "price_at_or_before_first_buy",
        "min_price_after_first_buy", "min_price_after_first_buy_utc",
        "min_price_after_last_buy", "min_price_after_last_buy_utc",
        "max_price_after_first_buy", "max_price_after_first_buy_utc",
        "last_price_before_resolution", "last_price_before_resolution_utc",
        "settlement_price", "entry_to_last_price_change",
        "worst_drawdown_after_first_buy", "worst_drawdown_after_last_buy",
    ]
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    point_fields = [
        "wallet_pseudonym", "market_condition_id", "market_question", "chart_label",
        "timestamp_utc", "relative_time_to_resolution", "price", "is_candidate_buy",
    ]
    with open(args.price_points_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=point_fields)
        writer.writeheader()
        writer.writerows(price_points)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": DATA_API,
        "selected_candidate_rows": len(candidates),
        "movement_rows": len(output_rows),
        "markets_fetched": len(fetched_by_market),
        "max_trades_per_market": args.max_trades_per_market,
        "api_trades_pulled_total": sum(len(v) for v in fetched_by_market.values()),
        "price_points_written": len(price_points),
    }
    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
