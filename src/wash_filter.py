"""
wash_filter.py
--------------
Identify wash-trade pairs in data/activity.csv and produce a clean dataset
data/activity_clean.csv plus per-wallet wash-share statistics.

Wash-trade definition (operational, conservative):
  A BUY and a SELL by the same wallet, on the same market-outcome combination,
  within MAX_PAIR_HOURS hours, at prices within PAIR_PRICE_TOLERANCE_BPS of
  each other, with USDC sizes within PAIR_SIZE_TOLERANCE_PCT, are flagged as
  a matched wash pair. Both legs of the pair are excluded from the clean set.

Operator background: Polymarket confirmed a POLY token airdrop on
2025-10-24 (chief marketing officer Matthew Modabber). Anticipation of volume-weighted airdrop
allocation drove a wave of wash trading. A Columbia University study
(published 2025-11-07) estimated ~25% of Polymarket volume is wash trading,
peaking at 60% in December 2024 and resurging through the fourth quarter of 2025. This filter is
calibrated to that operational reality.

References:
  https://decrypt.co/347842/columbia-study-25-polymarket-volume-wash-trading
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

MAX_PAIR_HOURS = 48.0           # BUY and matching SELL must be within 48h
PAIR_PRICE_TOLERANCE_BPS = 300  # within 3 percentage points (handles small slippage)
PAIR_SIZE_TOLERANCE_PCT = 0.10  # within 10% notional

# Position-net detection: per (wallet, market, outcome), compute total BUYs and SELLs.
# If gross volume is significant but net position is tiny, the wallet round-tripped —
# all trades in that group are wash. This catches multi-leg wash patterns that the
# pairwise matcher misses (e.g., 3 BUYs + 2 SELLs that net out).
POSITION_NET_THRESHOLD = 0.10  # net / gross < 10% → wash


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(DATA / "activity.csv"))
    ap.add_argument("--out", dest="out", default=str(DATA / "activity_clean.csv"))
    ap.add_argument("--wash-out", dest="wash_out", default=str(DATA / "activity_wash.csv"))
    ap.add_argument("--per-wallet", default=str(DATA / "wallet_wash_stats.csv"))
    ap.add_argument("--summary", default=str(DATA / "wash_filter_summary.json"))
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.inp)))
    for r in rows:
        try:
            r["timestamp_unix"] = int(r["timestamp_unix"])
            r["price"] = float(r["price"])
            r["size_usdc"] = float(r["size_usdc"])
        except (ValueError, KeyError):
            r["timestamp_unix"] = 0
            r["price"] = 0.0
            r["size_usdc"] = 0.0

    # Group by (wallet, condition_id, outcome)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["wallet_address"].lower(), r["condition_id"], r["outcome"])
        groups[key].append(r)

    print(f"input activity records: {len(rows)}", file=sys.stderr)
    print(f"wallet-market-outcome groups: {len(groups)}", file=sys.stderr)

    wash_flags = set()  # indices of rows marked as wash
    for key, ts in groups.items():
        ts.sort(key=lambda r: r["timestamp_unix"])

        # PASS 1: pairwise matcher (catches obvious BUY+SELL pairs at near-same price)
        used = [False] * len(ts)
        for i, a in enumerate(ts):
            if used[i] or a["side"] != "BUY":
                continue
            for j in range(i + 1, len(ts)):
                if used[j] or ts[j]["side"] != "SELL":
                    continue
                dt_hours = (ts[j]["timestamp_unix"] - a["timestamp_unix"]) / 3600
                if dt_hours > MAX_PAIR_HOURS:
                    break
                price_gap_bps = abs(a["price"] - ts[j]["price"]) * 10000
                if price_gap_bps > PAIR_PRICE_TOLERANCE_BPS:
                    continue
                if a["size_usdc"] == 0 or ts[j]["size_usdc"] == 0:
                    continue
                size_gap = abs(a["size_usdc"] - ts[j]["size_usdc"]) / max(a["size_usdc"], ts[j]["size_usdc"])
                if size_gap > PAIR_SIZE_TOLERANCE_PCT:
                    continue
                used[i] = used[j] = True
                wash_flags.add(id(a))
                wash_flags.add(id(ts[j]))
                break

        # PASS 2: position-net detector. Sum BUYs and SELLs in this (wallet, market,
        # outcome) group. If |BUYs - SELLs| / (BUYs + SELLs) < threshold AND gross
        # volume >= $1K, the wallet round-tripped — flag ALL trades in the group.
        buys = sum(r["size_usdc"] for r in ts if r["side"] == "BUY")
        sells = sum(r["size_usdc"] for r in ts if r["side"] == "SELL")
        gross = buys + sells
        if gross >= 1000:
            net_share = abs(buys - sells) / gross
            if net_share < POSITION_NET_THRESHOLD:
                for r in ts:
                    wash_flags.add(id(r))

    clean_rows = [r for r in rows if id(r) not in wash_flags]
    wash_rows = [r for r in rows if id(r) in wash_flags]

    fieldnames = list(rows[0].keys()) if rows else []
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in clean_rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    with open(args.wash_out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in wash_rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})

    # Per-wallet stats
    per_wallet: dict[str, dict] = defaultdict(lambda: {"total_vol": 0.0, "wash_vol": 0.0, "total_n": 0, "wash_n": 0})
    for r in rows:
        addr = r["wallet_address"].lower()
        per_wallet[addr]["total_vol"] += r["size_usdc"]
        per_wallet[addr]["total_n"] += 1
        if id(r) in wash_flags:
            per_wallet[addr]["wash_vol"] += r["size_usdc"]
            per_wallet[addr]["wash_n"] += 1

    with open(args.per_wallet, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["wallet_address", "total_vol_usd", "wash_vol_usd",
                                          "total_n", "wash_n", "wash_vol_share", "wash_n_share",
                                          "clean_vol_usd", "label"])
        w.writeheader()
        for addr, s in per_wallet.items():
            wv_share = s["wash_vol"] / s["total_vol"] if s["total_vol"] > 0 else 0
            wn_share = s["wash_n"] / s["total_n"] if s["total_n"] > 0 else 0
            label = "volume_farmer" if wv_share >= 0.50 else ("partial_washer" if wv_share >= 0.10 else "clean")
            w.writerow({
                "wallet_address": addr,
                "total_vol_usd": round(s["total_vol"], 2),
                "wash_vol_usd": round(s["wash_vol"], 2),
                "total_n": s["total_n"],
                "wash_n": s["wash_n"],
                "wash_vol_share": round(wv_share, 4),
                "wash_n_share": round(wn_share, 4),
                "clean_vol_usd": round(s["total_vol"] - s["wash_vol"], 2),
                "label": label,
            })

    total_vol = sum(r["size_usdc"] for r in rows)
    wash_vol = sum(r["size_usdc"] for r in wash_rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_records": len(rows),
        "wash_records": len(wash_rows),
        "clean_records": len(clean_rows),
        "total_volume_usd": round(total_vol, 2),
        "wash_volume_usd": round(wash_vol, 2),
        "wash_volume_share": round(wash_vol / total_vol if total_vol > 0 else 0, 4),
        "wash_definition": {
            "max_pair_hours": MAX_PAIR_HOURS,
            "price_tolerance_bps": PAIR_PRICE_TOLERANCE_BPS,
            "size_tolerance_pct": PAIR_SIZE_TOLERANCE_PCT,
        },
        "wallet_labels": dict([
            ("volume_farmer", sum(1 for s in per_wallet.values() if s["wash_vol"] / max(s["total_vol"], 1) >= 0.50)),
            ("partial_washer", sum(1 for s in per_wallet.values() if 0.10 <= s["wash_vol"] / max(s["total_vol"], 1) < 0.50)),
            ("clean", sum(1 for s in per_wallet.values() if s["wash_vol"] / max(s["total_vol"], 1) < 0.10)),
        ]),
    }
    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nwrote clean → {args.out}", file=sys.stderr)
    print(f"wrote wash  → {args.wash_out}", file=sys.stderr)
    print(f"wrote per-wallet stats → {args.per_wallet}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
