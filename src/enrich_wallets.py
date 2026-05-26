"""
enrich_wallets.py
-----------------
For each unique wallet that appears in data/trades.csv, hit the public Polymarket
profile / leaderboard endpoints and write data/wallets.csv.

Endpoints used (all public, no auth):
  lb-api.polymarket.com/profit?window=all&address=<addr>   -> lifetime $ profit
  lb-api.polymarket.com/profit?window=30d&address=<addr>   -> 30-day $ profit
  lb-api.polymarket.com/volume?window=all&address=<addr>   -> lifetime $ volume
  data-api.polymarket.com/value?user=<addr>                -> current portfolio value

These metrics feed multiple heuristics:
  - D8/D9 baseline accuracy and direction precision require lifetime volume + P&L
    to normalize the in-window resolved performance against the wallet's broader
    track record.
  - Anti-signals (doxxed sharps, market-makers) need lifetime volume + name/
    pseudonym to identify named accounts.
  - B4 single-niche specialist needs lifetime volume to compare against
    in-window pop-culture volume share.

Run is rate-limited to ~5 req/s per endpoint to be polite to the public API.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
LB = "https://lb-api.polymarket.com"
DAPI = "https://data-api.polymarket.com"
HEADERS = {"User-Agent": "polymarket-insider-detection/0.1 (research)"}


def safe_get(url: str, params: dict) -> list | None:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def first(data: list | None, key: str, default=0.0):
    if not data:
        return default
    return data[0].get(key, default)


def enrich(addr: str) -> dict:
    p_all = safe_get(f"{LB}/profit", {"window": "all", "address": addr})
    p_30 = safe_get(f"{LB}/profit", {"window": "30d", "address": addr})
    v_all = safe_get(f"{LB}/volume", {"window": "all", "address": addr})
    val = safe_get(f"{DAPI}/value", {"user": addr})

    pseudonym = first(p_all, "pseudonym", "")
    name = first(p_all, "name", "")
    bio = first(p_all, "bio", "")

    return {
        "wallet_address": addr,
        "pseudonym": pseudonym,
        "name": name,
        "bio": bio,
        "profile_image": first(p_all, "profileImage", ""),
        "lifetime_profit_usd": float(first(p_all, "amount", 0) or 0),
        "profit_30d_usd": float(first(p_30, "amount", 0) or 0),
        "lifetime_volume_usd": float(first(v_all, "amount", 0) or 0),
        "current_portfolio_value_usd": float(first(val, "value", 0) or 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default=str(DATA / "trades.csv"))
    ap.add_argument("--out", default=str(DATA / "wallets.csv"))
    ap.add_argument("--summary", default=str(DATA / "wallets_enrich_summary.json"))
    ap.add_argument("--min-trades", type=int, default=3,
                    help="Skip wallets with fewer than N in-window trades")
    ap.add_argument("--min-volume-usd", type=float, default=1000.0,
                    help="OR-include wallets with >= this in-window USD volume regardless of trade count")
    ap.add_argument("--workers", type=int, default=10, help="Concurrent HTTP workers")
    args = ap.parse_args()

    # Collect unique wallets and their in-window trade counts + volume.
    counts: dict[str, int] = {}
    volumes: dict[str, float] = {}
    for r in csv.DictReader(open(args.trades)):
        w = r.get("wallet_address", "").lower()
        if not w:
            continue
        counts[w] = counts.get(w, 0) + 1
        try:
            volumes[w] = volumes.get(w, 0.0) + float(r.get("size_usd") or 0)
        except ValueError:
            pass

    total_unique = len(counts)
    eligible = [
        w for w in counts
        if counts[w] >= args.min_trades or volumes.get(w, 0) >= args.min_volume_usd
    ]
    eligible.sort(key=lambda w: -volumes.get(w, 0))
    print(f"unique wallets in trades: {total_unique}", file=sys.stderr)
    print(f"eligible (>={args.min_trades} trades OR >=${args.min_volume_usd:.0f} vol): "
          f"{len(eligible)}", file=sys.stderr)
    wallets = eligible

    fieldnames = [
        "wallet_address", "pseudonym", "name", "bio", "profile_image",
        "lifetime_profit_usd", "profit_30d_usd", "lifetime_volume_usd",
        "current_portfolio_value_usd", "in_window_trade_count",
    ]
    out_f = open(args.out, "w", newline="")
    w_writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    w_writer.writeheader()

    success = 0
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(enrich, addr): addr for addr in wallets}
        for fut in as_completed(futures):
            addr = futures[fut]
            done += 1
            if done % 500 == 0:
                print(f"  [{done}/{len(wallets)}] ({success} enriched)", file=sys.stderr)
            try:
                row = fut.result()
                row["in_window_trade_count"] = counts[addr]
                w_writer.writerow(row)
                success += 1
            except Exception as e:
                print(f"  ! {addr}: {e}", file=sys.stderr)

    out_f.close()

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "unique_wallets_in_trades": total_unique,
        "eligible_wallets": len(wallets),
        "wallets_enriched": success,
        "min_trades": args.min_trades,
        "min_volume_usd": args.min_volume_usd,
        "endpoints": [
            "lb-api.polymarket.com/profit?window=all",
            "lb-api.polymarket.com/profit?window=30d",
            "lb-api.polymarket.com/volume?window=all",
            "data-api.polymarket.com/value",
        ],
    }
    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {success} wallets to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
