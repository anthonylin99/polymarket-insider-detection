"""
backfill_trades.py
------------------
For each market in data/markets_filtered.csv, pull available trades from the
public Polymarket trade endpoint and write them to data/trades.csv.

Endpoint:
  GET https://data-api.polymarket.com/trades
  Params: market=<conditionId>, limit (max 500), offset

Pagination notes from May 2026 testing:
  - limit is hard-capped at 500 per call.
  - offset paginates server-side. We page in 500-row steps until an empty page
    or until --max-trades-per-market is hit.
  - Very high-volume markets above $5 million can have tens of thousands of
    trades; we cap per-market to keep the dataset tractable and avoid runaway runtime.
    The cap is recorded per-market in trades_backfill_summary.json so the
    next engineer knows where coverage is partial.

Output schema (trades.csv):
  trade_id, timestamp_utc, market_condition_id, event_id, market_question, bucket,
  wallet_address, wallet_name, wallet_pseudonym, side, outcome, outcome_index,
  price, size_usd, tx_hash
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


def fetch_market_trades(condition_id: str, max_trades: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    page_size = 500
    while len(rows) < max_trades:
        try:
            r = requests.get(
                DATA_API,
                params={"market": condition_id, "limit": page_size, "offset": offset},
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            page = r.json()
        except (requests.RequestException, ValueError) as e:
            print(f"  ! fetch error at offset {offset}: {e}", file=sys.stderr)
            break
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
        time.sleep(0.1)  # gentle rate limit
    return rows[:max_trades]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default=str(DATA / "markets_filtered.csv"))
    ap.add_argument("--out", default=str(DATA / "trades.csv"))
    ap.add_argument("--summary", default=str(DATA / "trades_backfill_summary.json"))
    ap.add_argument("--max-trades-per-market", type=int, default=10_000)
    ap.add_argument("--min-volume", type=float, default=0.0,
                    help="Skip markets below this lifetime volume (USD). 0 = no skip.")
    args = ap.parse_args()

    markets = list(csv.DictReader(open(args.markets)))
    print(f"input markets: {len(markets)}", file=sys.stderr)

    per_market_summary: list[dict] = []
    total_trades = 0
    seen_trade_ids: set[str] = set()
    fieldnames = [
        "trade_id", "timestamp_utc", "market_condition_id", "event_id",
        "market_question", "bucket", "wallet_address", "wallet_name",
        "wallet_pseudonym", "side", "outcome", "outcome_index", "price",
        "size_usd", "tx_hash",
    ]
    out_f = open(args.out, "w", newline="")
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    writer.writeheader()

    for i, m in enumerate(markets, start=1):
        cid = m["condition_id"]
        if not cid:
            continue
        vol = float(m.get("volume_usd") or 0)
        if vol < args.min_volume:
            continue
        print(f"[{i}/{len(markets)}] vol=${vol:>11,.0f} {m['market_question'][:70]}", file=sys.stderr)
        trades = fetch_market_trades(cid, args.max_trades_per_market)
        kept_here = 0
        for t in trades:
            tid = t.get("transactionHash", "") + "_" + str(t.get("timestamp", "")) + "_" + str(t.get("proxyWallet", ""))
            if tid in seen_trade_ids:
                continue
            seen_trade_ids.add(tid)
            ts_unix = t.get("timestamp")
            ts_iso = datetime.fromtimestamp(int(ts_unix), tz=timezone.utc).isoformat() if ts_unix else ""
            price = float(t.get("price") or 0)
            size_shares = float(t.get("size") or 0)
            size_usd = price * size_shares  # endpoint `size` is in shares; value = price * shares
            writer.writerow({
                "trade_id": tid,
                "timestamp_utc": ts_iso,
                "market_condition_id": cid,
                "event_id": m.get("event_id"),
                "market_question": m.get("market_question"),
                "bucket": m.get("bucket"),
                "wallet_address": (t.get("proxyWallet") or "").lower(),
                "wallet_name": t.get("name") or "",
                "wallet_pseudonym": t.get("pseudonym") or "",
                "side": t.get("side"),
                "outcome": t.get("outcome"),
                "outcome_index": t.get("outcomeIndex"),
                "price": price,
                "size_usd": round(size_usd, 4),
                "tx_hash": t.get("transactionHash"),
            })
            kept_here += 1
        total_trades += kept_here
        per_market_summary.append({
            "condition_id": cid,
            "question": m["market_question"],
            "bucket": m["bucket"],
            "volume_usd": vol,
            "trades_pulled": len(trades),
            "trades_written": kept_here,
            "capped": len(trades) >= args.max_trades_per_market,
        })

    out_f.close()

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_markets": len(markets),
        "markets_processed": len(per_market_summary),
        "max_trades_per_market": args.max_trades_per_market,
        "total_trades_written": total_trades,
        "unique_wallets": len({}),  # filled below
        "capped_markets": sum(1 for r in per_market_summary if r["capped"]),
        "per_market": per_market_summary,
    }
    # Recompute unique wallets from output file.
    wallets: set[str] = set()
    for row in csv.DictReader(open(args.out)):
        if row["wallet_address"]:
            wallets.add(row["wallet_address"])
    summary["unique_wallets"] = len(wallets)

    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nwrote {total_trades} trades from {len(per_market_summary)} markets, {len(wallets)} unique wallets",
          file=sys.stderr)
    print(f"capped markets (hit --max-trades-per-market={args.max_trades_per_market}): "
          f"{summary['capped_markets']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
