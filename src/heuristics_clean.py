"""
heuristics_clean.py
-------------------
v2 heuristic scoring on the wash-filtered dataset (data/activity_clean.csv).

Four focused heuristics, recalibrated after the Round 1 review that surfaced
the wash-trading problem:

  H1 — Middling-price conviction
       BUY on the eventually-correct outcome at price 0.20-0.70,
       size >= $5K, >= 48 hours before resolution. The real insider signature.

  H2 — Anomalous size or fresh-wallet
       Trade >= 50x wallet's prior median size (>=5 prior trades for baseline)
       OR lifetime wallet age <= 90 days AND in-window single trade >= $10K.

  H3 — Specialist concentration on a single resolver
       >=80% of wallet's clean in-window volume in 1-3 markets that share a
       resolver, with directional purity on the eventually-correct side.

  H4 — Sample-shrunk excess accuracy
       Brier excess vs. market-implied probability, multiplied by
       min(1, n_real_trades / 15).

Inputs are activity_clean.csv (wash-removed) and wallet_wash_stats.csv. Output
is wallet_scores_clean.csv with all four heuristics plus a composite score.
Wallets with wash_vol_share >= 0.50 are excluded from the ranked output even
if they would otherwise score high. The composite weights are documented in
report/heuristics.md.
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

A1_PRICE_LO, A1_PRICE_HI = 0.20, 0.70
A1_MIN_SIZE_USD = 5000.0
A1_MIN_HOURS_PRE_RES = 48.0

H2_MEDIAN_MULTIPLIER = 50.0
H2_MIN_PRIOR_TRADES = 5
H2_FRESH_LIFETIME_DAYS = 90
H2_FRESH_MIN_SIZE_USD = 10000.0

H4_MIN_RESOLVED = 5
CONFIDENCE_PIVOT = 15

TOP_MIN_CLEAN_VOLUME_USD = 5000.0
EXCLUDE_WASH_SHARE = 0.50

WEIGHTS = {"h1": 0.40, "h2": 0.20, "h3": 0.15, "h4": 0.25}


def parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T", 1))
    except Exception:
        return None


def load_markets() -> dict[str, dict]:
    out = {}
    for r in csv.DictReader(open(DATA / "markets_filtered.csv")):
        cid = r["condition_id"]
        try:
            r["resolved_price"] = float(r.get("resolved_price") or 0)
        except ValueError:
            r["resolved_price"] = 0.0
        r["closed_time_dt"] = parse_ts(r.get("closed_time") or r.get("end_date") or "")
        out[cid] = r
    return out


def load_clean_activity() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in csv.DictReader(open(DATA / "activity_clean.csv")):
        addr = r["wallet_address"].lower()
        try:
            r["price"] = float(r["price"])
            r["size_usdc"] = float(r["size_usdc"])
            r["timestamp"] = parse_ts(r["timestamp_utc"])
            r["timestamp_unix"] = int(r["timestamp_unix"])
        except (ValueError, KeyError):
            continue
        if r["timestamp"] is None:
            continue
        out[addr].append(r)
    for addr in out:
        out[addr].sort(key=lambda t: t["timestamp_unix"])
    return out


def load_wash_stats() -> dict[str, dict]:
    out = {}
    for r in csv.DictReader(open(DATA / "wallet_wash_stats.csv")):
        try:
            r["wash_vol_share"] = float(r["wash_vol_share"])
            r["clean_vol_usd"] = float(r["clean_vol_usd"])
            r["total_vol_usd"] = float(r["total_vol_usd"])
        except ValueError:
            pass
        out[r["wallet_address"].lower()] = r
    return out


def h1_middling_conviction(trades: list[dict], markets: dict[str, dict]) -> tuple[float, list[dict]]:
    hits = []
    for t in trades:
        m = markets.get(t["condition_id"])
        if not m or not m["closed_time_dt"] or not m["resolved_outcome"]:
            continue
        if t["side"] != "BUY":
            continue
        if not (A1_PRICE_LO <= t["price"] <= A1_PRICE_HI):
            continue
        if t["size_usdc"] < A1_MIN_SIZE_USD:
            continue
        if t["outcome"] != m["resolved_outcome"]:
            continue
        hrs = (m["closed_time_dt"] - t["timestamp"]).total_seconds() / 3600
        if hrs < A1_MIN_HOURS_PRE_RES:
            continue
        # implied dollar profit if held to resolution
        implied_profit = (1 - t["price"]) / t["price"] * t["size_usdc"]
        hits.append({"trade": t, "market": m, "hours_pre_res": hrs, "implied_profit": implied_profit})
    if not hits:
        return 0.0, []
    # score: scaled by max implied profit, plus volume of hits
    total_implied = sum(h["implied_profit"] for h in hits)
    score = min(1.0, total_implied / 25_000.0)
    return score, hits


def h2_anomalous_size(trades: list[dict], in_scope_cids: set[str]) -> tuple[float, list[dict]]:
    if len(trades) < 2:
        return 0.0, []
    sizes = [t["size_usdc"] for t in trades]
    flagged = []
    for i, t in enumerate(trades):
        if t["condition_id"] not in in_scope_cids:
            continue
        if t["size_usdc"] < 1000:
            continue
        prior = sizes[:i]
        if len(prior) >= H2_MIN_PRIOR_TRADES:
            med = statistics.median(prior)
            if med > 0 and t["size_usdc"] / med >= H2_MEDIAN_MULTIPLIER:
                flagged.append({"trade": t, "median_prior": med, "multiple": t["size_usdc"] / med})
                continue
        # fresh wallet case: trade in first 90d of activity AND size >= 10K
        first_ts = trades[0]["timestamp_unix"]
        days_since_first = (t["timestamp_unix"] - first_ts) / 86400
        if days_since_first <= H2_FRESH_LIFETIME_DAYS and t["size_usdc"] >= H2_FRESH_MIN_SIZE_USD:
            flagged.append({"trade": t, "days_since_first": days_since_first, "fresh": True})
    if not flagged:
        return 0.0, []
    return min(1.0, len(flagged) / 3.0), flagged


def h3_specialist(trades: list[dict], markets: dict[str, dict], in_scope_cids: set[str]) -> float:
    in_scope_vol = sum(t["size_usdc"] for t in trades if t["condition_id"] in in_scope_cids)
    total_vol = sum(t["size_usdc"] for t in trades)
    if total_vol <= 0:
        return 0.0
    pop_share = in_scope_vol / total_vol
    if pop_share < 0.80:
        return 0.0
    by_mkt: dict[str, float] = defaultdict(float)
    for t in trades:
        if t["condition_id"] in in_scope_cids:
            by_mkt[t["condition_id"]] += t["size_usdc"]
    if not by_mkt:
        return 0.0
    concentration = max(by_mkt.values()) / sum(by_mkt.values())
    # Directional purity: did the wallet win the top market?
    top_cid = max(by_mkt, key=by_mkt.get)
    top_trades = [t for t in trades if t["condition_id"] == top_cid and t["side"] == "BUY"]
    if not top_trades:
        return 0.0
    m = markets.get(top_cid)
    if not m or not m["resolved_outcome"]:
        return 0.0
    won = top_trades[0]["outcome"] == m["resolved_outcome"]
    purity = 1.0 if won else 0.3
    return pop_share * concentration * purity


def h4_excess_accuracy(trades: list[dict], markets: dict[str, dict]) -> float:
    implied = []
    n = 0
    for t in trades:
        m = markets.get(t["condition_id"])
        if not m or not m["resolved_outcome"]:
            continue
        if t["side"] != "BUY":
            continue
        if t["outcome"] == m["resolved_outcome"]:
            impl = t["price"]
        else:
            impl = 1 - t["price"]
        implied.append((impl, 1.0))
        n += 1
    if n < H4_MIN_RESOLVED:
        return 0.0
    actual_brier = sum((p - o) ** 2 for p, o in implied) / n
    baseline_brier = 0.25  # uninformed binary baseline
    excess = max(0.0, baseline_brier - actual_brier)
    raw = min(1.0, excess / 0.15)
    confidence = min(1.0, len(trades) / CONFIDENCE_PIVOT)
    return raw * confidence


def main() -> int:
    markets = load_markets()
    in_scope_cids = set(markets.keys())
    by_w = load_clean_activity()
    wash = load_wash_stats()

    print(f"loaded {len(markets)} markets, {len(by_w)} wallets with clean activity, "
          f"{len(wash)} wallets with wash stats", file=sys.stderr)

    rows = []
    h1_hits_per_wallet: dict[str, list] = {}
    h2_hits_per_wallet: dict[str, list] = {}
    for addr, trades in by_w.items():
        if len(trades) < 2:
            continue
        h1, h1_hits = h1_middling_conviction(trades, markets)
        h2, h2_hits = h2_anomalous_size(trades, in_scope_cids)
        h3 = h3_specialist(trades, markets, in_scope_cids)
        h4 = h4_excess_accuracy(trades, markets)
        composite = WEIGHTS["h1"] * h1 + WEIGHTS["h2"] * h2 + WEIGHTS["h3"] * h3 + WEIGHTS["h4"] * h4

        in_scope_trades = [t for t in trades if t["condition_id"] in in_scope_cids]
        in_scope_vol = sum(t["size_usdc"] for t in in_scope_trades)

        ws = wash.get(addr, {})
        wash_share = float(ws.get("wash_vol_share", 0))
        clean_vol = float(ws.get("clean_vol_usd", 0)) or in_scope_vol

        rows.append({
            "wallet_address": addr,
            "in_scope_trade_count": len(in_scope_trades),
            "in_scope_volume_usd": round(in_scope_vol, 2),
            "clean_volume_usd_lifetime": round(clean_vol, 2),
            "wash_vol_share": round(wash_share, 4),
            "h1_middling_conviction": round(h1, 4),
            "h2_anomalous_size": round(h2, 4),
            "h3_specialist": round(h3, 4),
            "h4_excess_accuracy": round(h4, 4),
            "composite_score": round(composite, 4),
            "h1_hits_count": len(h1_hits),
            "h2_hits_count": len(h2_hits),
        })
        h1_hits_per_wallet[addr] = h1_hits
        h2_hits_per_wallet[addr] = h2_hits

    # Eligibility: exclude volume farmers, require minimum clean activity
    eligible = [
        r for r in rows
        if r["wash_vol_share"] < EXCLUDE_WASH_SHARE
        and r["in_scope_volume_usd"] >= TOP_MIN_CLEAN_VOLUME_USD
    ]
    eligible.sort(key=lambda r: -r["composite_score"])
    for rk, r in enumerate(eligible, start=1):
        r["composite_rank"] = rk

    fieldnames = list(eligible[0].keys()) if eligible else []
    with (DATA / "wallet_scores_clean.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(eligible)

    # Top-20 with H1 hit details
    top20 = eligible[:20]
    with (DATA / "top20_clean.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(top20)

    # Detailed H1 evidence file for the top-20
    detail_rows = []
    for r in top20:
        for h in h1_hits_per_wallet.get(r["wallet_address"], []):
            detail_rows.append({
                "wallet_address": r["wallet_address"],
                "market_condition_id": h["market"]["condition_id"],
                "market_question": h["market"]["market_question"],
                "resolved_outcome": h["market"]["resolved_outcome"],
                "side_outcome": h["trade"]["outcome"],
                "buy_price": h["trade"]["price"],
                "buy_size_usd": h["trade"]["size_usdc"],
                "hours_pre_res": round(h["hours_pre_res"], 1),
                "implied_profit_usd": round(h["implied_profit"], 2),
                "buy_timestamp_utc": h["trade"]["timestamp_utc"],
            })
    if detail_rows:
        with (DATA / "top20_h1_evidence.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()))
            w.writeheader()
            w.writerows(detail_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "wallets_scored": len(rows),
        "wallets_eligible_after_wash_exclude": len(eligible),
        "excluded_volume_farmers": sum(1 for r in rows if r["wash_vol_share"] >= EXCLUDE_WASH_SHARE),
        "wallets_with_h1_hits": sum(1 for r in rows if r["h1_middling_conviction"] > 0),
        "wallets_with_h2_hits": sum(1 for r in rows if r["h2_anomalous_size"] > 0),
        "wallets_with_h3_hits": sum(1 for r in rows if r["h3_specialist"] > 0),
        "wallets_with_h4_hits": sum(1 for r in rows if r["h4_excess_accuracy"] > 0),
        "weights": WEIGHTS,
        "thresholds": {
            "h1_price_band": [A1_PRICE_LO, A1_PRICE_HI],
            "h1_min_size_usd": A1_MIN_SIZE_USD,
            "h1_min_hours_pre_res": A1_MIN_HOURS_PRE_RES,
            "h2_median_multiplier": H2_MEDIAN_MULTIPLIER,
            "h2_fresh_lifetime_days": H2_FRESH_LIFETIME_DAYS,
            "h2_fresh_min_size_usd": H2_FRESH_MIN_SIZE_USD,
            "exclude_wash_share": EXCLUDE_WASH_SHARE,
            "top_min_clean_volume_usd": TOP_MIN_CLEAN_VOLUME_USD,
        },
    }
    with (DATA / "wallet_scores_clean_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nwrote {len(eligible)} ranked wallets → wallet_scores_clean.csv", file=sys.stderr)
    print(f"top-20 → top20_clean.csv", file=sys.stderr)
    print(f"H1 evidence detail for top-20 → top20_h1_evidence.csv", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
