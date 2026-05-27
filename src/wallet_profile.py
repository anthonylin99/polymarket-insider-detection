"""
wallet_profile.py
-----------------
Builds polysights-style organized dossiers for a set of target wallets.
Reads data/activity_clean.csv (wash-filtered), data/wallets.csv (lifetime
stats), data/markets_filtered.csv (resolution metadata), and produces:

  data/profiles/<addr>.json   one structured profile per wallet
  data/profiles/INDEX.csv     summary table across all profiles

Each profile includes:
  - identity (address, display name, pseudonym, bio, profile image)
  - lifetime stats (lifetime volume / profit / 30d profit / portfolio value)
  - in-window activity summary (real and wash split)
  - top markets by USD exposure (real trades)
  - resolved-position outcomes (win rate, average price, P&L)
  - trade-size distribution
  - vintage (first ever activity timestamp)
  - behavioral tags (volume_farmer / partial_washer / clean ; specialist / generalist)

This is the structured representation the report's case studies render from.
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

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
PROFILE_DIR = DATA / "profiles"
PROFILE_DIR.mkdir(exist_ok=True)
LB = "https://lb-api.polymarket.com"
DAPI = "https://data-api.polymarket.com"
HEADERS = {"User-Agent": "polymarket-insider-detection/0.2 (research)"}


def safe_get(url: str, params: dict) -> list | None:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return None
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def first(data: list | None, key: str, default=0.0):
    if not data:
        return default
    return data[0].get(key, default) if isinstance(data, list) else default


def load_markets() -> dict[str, dict]:
    out = {}
    for r in csv.DictReader(open(DATA / "markets_filtered.csv")):
        cid = r["condition_id"]
        try:
            r["resolved_price"] = float(r.get("resolved_price") or 0)
            r["volume_usd"] = float(r.get("volume_usd") or 0)
        except ValueError:
            pass
        out[cid] = r
    return out


def build_profile(addr: str, all_acts: list[dict], wash_stats: dict | None,
                  markets: dict[str, dict]) -> dict:
    # Live lifetime metrics
    pall = safe_get(f"{LB}/profit", {"window": "all", "address": addr})
    p30 = safe_get(f"{LB}/profit", {"window": "30d", "address": addr})
    vall = safe_get(f"{LB}/volume", {"window": "all", "address": addr})
    val = safe_get(f"{DAPI}/value", {"user": addr})

    name = first(pall, "name", "")
    pseudonym = first(pall, "pseudonym", "")
    bio = first(pall, "bio", "")
    profile_image = first(pall, "profileImage", "")
    lifetime_profit = float(first(pall, "amount", 0) or 0)
    profit_30d = float(first(p30, "amount", 0) or 0)
    lifetime_vol = float(first(vall, "amount", 0) or 0)
    portfolio_value = float(first(val, "value", 0) or 0)

    # All-trades summary
    all_acts_sorted = sorted(all_acts, key=lambda a: int(a.get("timestamp_unix", 0) or 0))
    first_ts = int(all_acts_sorted[0]["timestamp_unix"]) if all_acts_sorted else 0
    last_ts = int(all_acts_sorted[-1]["timestamp_unix"]) if all_acts_sorted else 0
    first_iso = datetime.fromtimestamp(first_ts, tz=timezone.utc).isoformat() if first_ts else ""
    last_iso = datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat() if last_ts else ""

    # Real-trades only (already wash-filtered if loaded from activity_clean.csv)
    real_trades = all_acts_sorted
    sizes = [float(a["size_usdc"]) for a in real_trades if float(a.get("size_usdc", 0)) > 0]
    size_median = statistics.median(sizes) if sizes else 0
    size_max = max(sizes) if sizes else 0
    n_trades = len(real_trades)

    # Per-market exposure
    by_mkt: dict[str, dict] = defaultdict(lambda: {"vol": 0.0, "trades": [], "title": ""})
    for a in real_trades:
        cid = a["condition_id"]
        by_mkt[cid]["vol"] += float(a.get("size_usdc", 0) or 0)
        by_mkt[cid]["trades"].append(a)
        by_mkt[cid]["title"] = a.get("title", "")
    distinct_markets = len(by_mkt)

    # In-scope markets (those in our filtered pop-culture set)
    in_scope_mkts = {cid: data for cid, data in by_mkt.items() if cid in markets}
    in_scope_vol = sum(d["vol"] for d in in_scope_mkts.values())

    # Resolved-position outcomes (win / loss based on first BUY's outcome)
    resolved_positions = []
    for cid, d in in_scope_mkts.items():
        m = markets[cid]
        if not m["resolved_outcome"]:
            continue
        buys = [t for t in d["trades"] if t.get("side") == "BUY"]
        if not buys:
            continue
        side_outcome = buys[0]["outcome"]
        won = side_outcome == m["resolved_outcome"]
        wavg_price = sum(float(t["price"]) * float(t["size_usdc"]) for t in buys) / max(d["vol"], 1)
        resolved_positions.append({
            "market": m["market_question"],
            "condition_id": cid,
            "side_outcome": side_outcome,
            "resolved_outcome": m["resolved_outcome"],
            "won": won,
            "buy_volume_usd": round(sum(float(t["size_usdc"]) for t in buys), 2),
            "wavg_buy_price": round(wavg_price, 4),
            "n_buys": len(buys),
            "end_date": m["end_date"][:10],
        })
    resolved_positions.sort(key=lambda p: -p["buy_volume_usd"])
    n_resolved = len(resolved_positions)
    n_won = sum(1 for p in resolved_positions if p["won"])

    # Tags
    tags = []
    if wash_stats:
        vol_share = wash_stats.get("wash_vol_share", 0)
        if vol_share >= 0.50:
            tags.append("volume_farmer")
        elif vol_share >= 0.10:
            tags.append("partial_washer")
        else:
            tags.append("clean")
    if in_scope_vol > 0 and lifetime_vol > 0 and in_scope_vol / lifetime_vol >= 0.50:
        tags.append("pop_culture_specialist")
    if distinct_markets >= 30:
        tags.append("generalist")

    return {
        "wallet_address": addr,
        "identity": {
            "name": name,
            "pseudonym": pseudonym,
            "bio": bio,
            "profile_image": profile_image,
        },
        "lifetime": {
            "volume_usd": lifetime_vol,
            "profit_usd": lifetime_profit,
            "profit_30d_usd": profit_30d,
            "portfolio_value_usd": portfolio_value,
        },
        "activity_window": {
            "first_trade_utc": first_iso,
            "last_trade_utc": last_iso,
            "lifespan_days": round((last_ts - first_ts) / 86400, 1) if first_ts and last_ts else 0,
        },
        "trading_summary": {
            "real_trades": n_trades,
            "real_volume_usd": round(sum(sizes), 2),
            "median_trade_usd": round(size_median, 2),
            "max_trade_usd": round(size_max, 2),
            "distinct_markets": distinct_markets,
            "in_scope_volume_usd": round(in_scope_vol, 2),
            "in_scope_volume_share_of_lifetime": round(in_scope_vol / lifetime_vol, 4) if lifetime_vol > 0 else None,
        },
        "wash_stats": wash_stats or {},
        "in_scope_positions_resolved": n_resolved,
        "in_scope_positions_won": n_won,
        "in_scope_win_rate": round(n_won / n_resolved, 4) if n_resolved > 0 else None,
        "top_in_scope_markets": resolved_positions[:10],
        "tags": tags,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--activity", default=str(DATA / "activity_clean.csv"))
    ap.add_argument("--wash-stats", default=str(DATA / "wallet_wash_stats.csv"))
    ap.add_argument("--targets", nargs="*", help="Specific wallet addresses to profile")
    ap.add_argument("--top-n", type=int, default=50, help="Top N by clean volume if no targets passed")
    args = ap.parse_args()

    markets = load_markets()

    # Load activity_clean.csv grouped by wallet
    by_w: dict[str, list[dict]] = defaultdict(list)
    for r in csv.DictReader(open(args.activity)):
        by_w[r["wallet_address"].lower()].append(r)

    # Load wash stats
    wash_map: dict[str, dict] = {}
    for r in csv.DictReader(open(args.wash_stats)):
        try:
            for k in ("total_vol_usd", "wash_vol_usd", "clean_vol_usd",
                      "wash_vol_share", "wash_n_share"):
                r[k] = float(r.get(k, 0) or 0)
            for k in ("total_n", "wash_n"):
                r[k] = int(r.get(k, 0) or 0)
        except ValueError:
            pass
        wash_map[r["wallet_address"].lower()] = r

    if args.targets:
        targets = [t.lower() for t in args.targets]
    else:
        # Top N by clean volume
        ranked = sorted(wash_map.values(), key=lambda r: -r["clean_vol_usd"])
        targets = [r["wallet_address"] for r in ranked[:args.top_n]]

    index_rows = []
    for i, addr in enumerate(targets, start=1):
        print(f"[{i}/{len(targets)}] profiling {addr}", file=sys.stderr)
        try:
            prof = build_profile(addr, by_w.get(addr, []), wash_map.get(addr), markets)
        except Exception as e:
            print(f"  ! {addr}: {e}", file=sys.stderr)
            continue
        out_path = PROFILE_DIR / f"{addr}.json"
        with out_path.open("w") as f:
            json.dump(prof, f, indent=2)
        index_rows.append({
            "wallet_address": addr,
            "name": prof["identity"]["name"],
            "lifetime_volume_usd": prof["lifetime"]["volume_usd"],
            "lifetime_profit_usd": prof["lifetime"]["profit_usd"],
            "in_scope_volume_usd": prof["trading_summary"]["in_scope_volume_usd"],
            "in_scope_positions_resolved": prof["in_scope_positions_resolved"],
            "in_scope_win_rate": prof["in_scope_win_rate"],
            "wash_vol_share": prof["wash_stats"].get("wash_vol_share", 0),
            "first_trade_utc": prof["activity_window"]["first_trade_utc"],
            "tags": ",".join(prof["tags"]),
        })

    with (PROFILE_DIR / "INDEX.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index_rows[0].keys()) if index_rows else [])
        w.writeheader()
        w.writerows(index_rows)

    print(f"\nwrote {len(index_rows)} profiles to {PROFILE_DIR}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
