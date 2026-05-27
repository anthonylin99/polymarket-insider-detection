"""
activity_pull.py
----------------
Re-pull complete trade history (both BUY and SELL legs) for top wallets via
the public Polymarket activity endpoint. The original backfill_trades.py used
data-api/trades which dropped at least some SELL legs of wash-trade pairs.

This script is the definitive trade source for downstream wash-trade detection
and clean-data heuristic scoring. Output: data/activity.csv.

Selection: top N wallets by in-window USD volume from data/trades.csv (default
N=500). This captures every wallet with material activity. Smaller wallets do
not need full activity since they cannot produce statistically meaningful
insider signal anyway.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
ACTIVITY = "https://data-api.polymarket.com/activity"
HEADERS = {"User-Agent": "polymarket-insider-detection/0.2 (research)"}


def fetch_activity(addr: str, max_records: int = 2000) -> list[dict]:
    out: list[dict] = []
    offset = 0
    page = 500
    while len(out) < max_records:
        try:
            r = requests.get(
                ACTIVITY,
                params={"user": addr, "limit": page, "offset": offset, "type": "TRADE"},
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError):
            break
        if not data:
            break
        out.extend(data)
        if len(data) < page:
            break
        offset += page
        time.sleep(0.05)
    return out[:max_records]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default=str(DATA / "trades.csv"))
    ap.add_argument("--out", default=str(DATA / "activity.csv"))
    ap.add_argument("--summary", default=str(DATA / "activity_pull_summary.json"))
    ap.add_argument("--top-n", type=int, default=500,
                    help="Pull full activity for the top-N wallets by in-window USD volume")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    by_w_vol: dict[str, float] = defaultdict(float)
    by_w_count: dict[str, int] = defaultdict(int)
    for r in csv.DictReader(open(args.trades)):
        w = r["wallet_address"].lower()
        if not w:
            continue
        try:
            by_w_vol[w] += float(r["size_usd"])
        except (KeyError, ValueError):
            pass
        by_w_count[w] += 1

    ranked = sorted(by_w_vol, key=lambda w: -by_w_vol[w])
    targets = ranked[:args.top_n]
    print(f"top-{args.top_n} wallets by in-window vol cover ${sum(by_w_vol[w] for w in targets):,.0f} "
          f"of ${sum(by_w_vol.values()):,.0f} total ({100*sum(by_w_vol[w] for w in targets)/sum(by_w_vol.values()):.1f}%)",
          file=sys.stderr)

    out_f = open(args.out, "w", newline="")
    fieldnames = [
        "wallet_address", "timestamp_unix", "timestamp_utc", "side", "outcome",
        "price", "size_usdc", "tx_hash", "market_slug", "event_slug", "title",
        "condition_id", "asset",
    ]
    w = csv.DictWriter(out_f, fieldnames=fieldnames)
    w.writeheader()

    success = 0
    total_acts = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_activity, addr): addr for addr in targets}
        done = 0
        for fut in as_completed(futures):
            addr = futures[fut]
            done += 1
            if done % 50 == 0:
                print(f"  [{done}/{len(targets)}] enriched={success} acts={total_acts}", file=sys.stderr)
            try:
                acts = fut.result()
            except Exception as e:
                print(f"  ! {addr}: {e}", file=sys.stderr)
                continue
            if not acts:
                continue
            success += 1
            for a in acts:
                ts_unix = int(a.get("timestamp", 0) or 0)
                w.writerow({
                    "wallet_address": addr,
                    "timestamp_unix": ts_unix,
                    "timestamp_utc": datetime.fromtimestamp(ts_unix, tz=timezone.utc).isoformat() if ts_unix else "",
                    "side": a.get("side", ""),
                    "outcome": a.get("outcome", ""),
                    "price": float(a.get("price", 0) or 0),
                    "size_usdc": float(a.get("usdcSize", 0) or 0),
                    "tx_hash": a.get("transactionHash", ""),
                    "market_slug": a.get("slug", ""),
                    "event_slug": a.get("eventSlug", ""),
                    "title": a.get("title", ""),
                    "condition_id": a.get("conditionId", ""),
                    "asset": a.get("asset", ""),
                })
            total_acts += len(acts)

    out_f.close()
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "top_n_target": args.top_n,
        "wallets_with_activity": success,
        "total_activity_records": total_acts,
        "endpoint": ACTIVITY,
        "note": "Activity endpoint captures both BUY and SELL legs, including the wash-trade pairs that data-api/trades dropped from the original backfill.",
    }
    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nwrote {total_acts} activity records from {success} wallets → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
