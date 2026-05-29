"""
identify_candidate_leads.py
---------------------------
Build a reviewed lead queue from pulled Polymarket trades.

The screen looks for clustered, correct-side buys at non-trivial prices in
markets where a real-world information channel is plausible. It is intentionally
conservative: the output is a follow-up queue, not an allegation list.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

WINDOW_START = datetime.fromisoformat("2025-11-01T00:00:00+00:00")
WINDOW_END = datetime.fromisoformat("2026-05-01T23:59:59+00:00")

# Tier 2 (triage) thresholds. Wider than the Tier 1 ranking screen in
# score_wallets.py (20-70c / $5,000 / 48h) on purpose: this stage casts a
# broad net to surface names for manual review, then the report applies
# stricter judgement. See report/heuristics.md "Two-tier screening".
MIN_SIGNAL_NOTIONAL_USD = 3_000.0
MIN_HOURS_PRE_RESOLUTION = 24.0
PRICE_LO = 0.20
PRICE_HI = 0.85
VOLUME_FARMER_WASH_SHARE = 0.50

# (wallet_address, condition_id) positions profiled in the report. Keyed by
# market so a wallet's other qualifying trades are not auto-profiled.
REPORT_SELECTION = {
    ("0xcd71fd5370880f3d92bb941e628c05840fe0d127", "0x2a46bac806f455a2fd53322cd830298d2ff86a1a6e40f5133e03786396d5445b"),  # Kevindoto / Weeknd #3
    ("0xcd71fd5370880f3d92bb941e628c05840fe0d127", "0x947d1021c37d975fb9a2f81d9b7da2579dd6cbf18d9c1e147e7a8f95480cd01a"),  # Kevindoto / Drake not #3
    ("0x8564848285e54c65f6cc2e3930b49362fbd84b2e", "0x19304977d87e5b37f5c40719a3e935c136acd5705b1398afdb4179b0dbdda19b"),  # AllYourMonies / BTS sales
    ("0xbacd00c9080a82ded56f504ee8810af732b0ab35", "0x0d880d85cadbe01cf69b30215a8f7304f0bc3e31f6f92218b0b02c9f145e9780"),  # ScottyNooo / Lady Gaga 3 Grammys
}


def parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(open(path)))


def load_markets(path: Path) -> dict[str, dict]:
    markets = {}
    for row in read_csv(path):
        row["closed_time_dt"] = parse_ts(row.get("closed_time") or row.get("end_date") or "")
        row["volume_usd_float"] = float(row.get("volume_usd") or 0)
        markets[row["condition_id"]] = row
    return markets


def load_wallets(path: Path) -> dict[str, dict]:
    wallets = {}
    for row in read_csv(path):
        addr = row["wallet_address"].lower()
        for key in ("lifetime_profit_usd", "lifetime_volume_usd", "current_portfolio_value_usd"):
            row[key] = float(row.get(key) or 0)
        row["in_window_trade_count"] = int(float(row.get("in_window_trade_count") or 0))
        wallets[addr] = row
    return wallets


def load_wash_stats(path: Path) -> dict[str, dict]:
    stats = {}
    for row in read_csv(path):
        addr = row["wallet_address"].lower()
        row["wash_vol_share"] = float(row.get("wash_vol_share") or 0)
        row["total_n"] = int(float(row.get("total_n") or 0))
        stats[addr] = row
    return stats


def load_activity(path: Path) -> dict[str, list[dict]]:
    by_wallet: dict[str, list[dict]] = defaultdict(list)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as f:
        for row in csv.DictReader(f):
            try:
                row["timestamp_dt"] = parse_ts(row["timestamp_utc"])
                row["size_usdc_float"] = float(row["size_usdc"])
            except (KeyError, ValueError):
                continue
            if row["timestamp_dt"] is None:
                continue
            by_wallet[row["wallet_address"].lower()].append(row)
    for rows in by_wallet.values():
        rows.sort(key=lambda r: r["timestamp_dt"])
    return by_wallet


def possible_channel(topic_label: str, question: str) -> str:
    text = question.lower()
    if "contestant" in text or "beast games" in text:
        return "production, casting, editing, or show-result access"
    if "album sales" in text or "debut week" in text:
        return "label, distributor, chart-reporting, or sales-operations access"
    if "release" in text or "announce" in text:
        return "label, management, distribution, or public-relations access"
    if topic_label == "music_streaming_rank":
        return "platform analytics, label dashboard, or distributor streaming-data access"
    if topic_label == "awards":
        return "voter, awards-industry, public-relations, or leak access"
    if topic_label == "creator_platform_metric":
        return "creator-side or platform analytics access"
    if topic_label == "attention_index_google_search":
        return "mostly public trend data; weaker nonpublic-information channel"
    return "unclear information channel; requires manual review"


def row_score(row: dict) -> float:
    score = 0.0
    score += min(40.0, row["signal_notional_usd"] / 500.0)
    score += min(25.0, row["implied_profit_usd"] / 500.0)
    if row["weighted_avg_price"] <= 0.60:
        score += 15.0
    elif row["weighted_avg_price"] <= 0.75:
        score += 8.0
    if row["min_hours_pre_resolution"] >= 168:
        score += 10.0
    elif row["min_hours_pre_resolution"] >= 48:
        score += 6.0
    wash = row["wash_vol_share"]
    if wash is None:
        score += 2.0
    elif wash < 0.15:
        score += 10.0
    elif wash < 0.35:
        score += 5.0
    if row["notional_vs_prior_median"] and row["notional_vs_prior_median"] >= 50:
        score += 8.0
    if row["topic_label"] == "attention_index_google_search":
        score -= 20.0
    return round(max(0.0, score), 2)


def review_label(row: dict) -> str:
    if row["wash_vol_share"] is not None and row["wash_vol_share"] >= VOLUME_FARMER_WASH_SHARE:
        return "Excluded volume farmer"
    if (row["wallet_address"], row["market_condition_id"]) in REPORT_SELECTION:
        return "Selected follow-up"
    if row["topic_label"] == "attention_index_google_search":
        return "Public-data control"
    if row["lead_score"] >= 60:
        return "Watchlist"
    return "Lower priority"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default=str(DATA / "markets_reviewed.csv"))
    ap.add_argument("--trades", default=str(DATA / "trades.csv.gz"))
    ap.add_argument("--wallets", default=str(DATA / "wallets.csv"))
    ap.add_argument("--wash-stats", default=str(DATA / "wallet_wash_stats.csv"))
    ap.add_argument("--activity", default=str(DATA / "activity_clean.csv.gz"))
    ap.add_argument("--out", default=str(DATA / "candidate_wallet_leads.csv"))
    ap.add_argument("--summary", default=str(DATA / "candidate_wallet_leads_summary.json"))
    args = ap.parse_args()

    markets = load_markets(Path(args.markets))
    wallets = load_wallets(Path(args.wallets))
    wash_stats = load_wash_stats(Path(args.wash_stats))
    activity = load_activity(Path(args.activity))

    groups: dict[tuple[str, str, str], dict] = {}
    with gzip.open(args.trades, "rt", newline="") as f:
        for trade in csv.DictReader(f):
            market = markets.get(trade["market_condition_id"])
            if not market or market["closed_time_dt"] is None:
                continue
            try:
                ts = parse_ts(trade["timestamp_utc"])
                price = float(trade["price"])
                size = float(trade["size_usd"])
            except (TypeError, ValueError):
                continue
            if ts is None or not (WINDOW_START <= ts <= WINDOW_END):
                continue
            if trade["side"] != "BUY" or trade["outcome"] != market.get("resolved_outcome"):
                continue
            hours_pre = (market["closed_time_dt"] - ts).total_seconds() / 3600
            if hours_pre < MIN_HOURS_PRE_RESOLUTION or not (PRICE_LO <= price <= PRICE_HI):
                continue

            wallet = trade["wallet_address"].lower()
            key = (wallet, trade["market_condition_id"], trade["outcome"])
            group = groups.setdefault(
                key,
                {
                    "wallet_address": wallet,
                    "wallet_pseudonym_from_trade": trade.get("wallet_pseudonym") or trade.get("wallet_name") or "",
                    "market_condition_id": trade["market_condition_id"],
                    "event_id": trade.get("event_id", ""),
                    "market_question": trade["market_question"],
                    "topic_label": market.get("topic_label") or market.get("bucket") or "",
                    "resolved_outcome": market.get("resolved_outcome", ""),
                    "side_bought": trade["outcome"],
                    "prices": [],
                    "sizes": [],
                    "hours": [],
                    "timestamps": [],
                    "implied_profit_usd": 0.0,
                },
            )
            group["prices"].append(price)
            group["sizes"].append(size)
            group["hours"].append(hours_pre)
            group["timestamps"].append(ts)
            group["implied_profit_usd"] += (1 - price) / price * size

    rows = []
    for group in groups.values():
        signal_notional = sum(group["sizes"])
        if signal_notional < MIN_SIGNAL_NOTIONAL_USD:
            continue
        wallet = group["wallet_address"]
        wallet_row = wallets.get(wallet, {})
        stats = wash_stats.get(wallet)
        first_ts = min(group["timestamps"])
        prior_sizes = [
            row["size_usdc_float"]
            for row in activity.get(wallet, [])
            if row["timestamp_dt"] < first_ts
        ]
        prior_median = statistics.median(prior_sizes) if prior_sizes else None
        wash_share = stats["wash_vol_share"] if stats else None
        row = {
            "wallet_address": wallet,
            "wallet_pseudonym": wallet_row.get("pseudonym") or group["wallet_pseudonym_from_trade"],
            "review_label": "",
            "lead_score": 0.0,
            "lead_rank": "",
            "market_condition_id": group["market_condition_id"],
            "event_id": group["event_id"],
            "market_question": group["market_question"],
            "topic_label": group["topic_label"],
            "possible_information_channel": possible_channel(group["topic_label"], group["market_question"]),
            "resolved_outcome": group["resolved_outcome"],
            "side_bought": group["side_bought"],
            "signal_trade_count": len(group["sizes"]),
            "signal_notional_usd": round(signal_notional, 2),
            "weighted_avg_price": round(sum(p * s for p, s in zip(group["prices"], group["sizes"])) / signal_notional, 4),
            "min_price": round(min(group["prices"]), 4),
            "max_price": round(max(group["prices"]), 4),
            "min_hours_pre_resolution": round(min(group["hours"]), 1),
            "max_hours_pre_resolution": round(max(group["hours"]), 1),
            "implied_profit_usd": round(group["implied_profit_usd"], 2),
            "first_buy_timestamp_utc": min(group["timestamps"]).isoformat(),
            "last_buy_timestamp_utc": max(group["timestamps"]).isoformat(),
            "lifetime_profit_usd": round(wallet_row.get("lifetime_profit_usd", 0.0), 2),
            "lifetime_volume_usd": round(wallet_row.get("lifetime_volume_usd", 0.0), 2),
            "in_window_trade_count": wallet_row.get("in_window_trade_count", ""),
            "wash_vol_share": None if wash_share is None else round(wash_share, 4),
            "wash_label": "" if not stats else stats.get("label", ""),
            "activity_capped": "" if not stats else stats.get("total_n", 0) >= 2_000,
            "prior_activity_count": len(prior_sizes),
            "prior_median_size_usd": "" if prior_median is None else round(prior_median, 2),
            "notional_vs_prior_median": "" if not prior_median else round(signal_notional / prior_median, 1),
        }
        row["lead_score"] = row_score(row)
        row["review_label"] = review_label(row)
        rows.append(row)

    # Rank purely on merit: public-data controls (Google-trend markets) are
    # pulled out of the insider queue, then everything else is ordered by the
    # transparent lead_score. No wallet is pinned to the top by hand.
    def is_control(r: dict) -> bool:
        return r["topic_label"] == "attention_index_google_search"

    rows.sort(
        key=lambda r: (
            is_control(r),
            -r["lead_score"],
            -r["signal_notional_usd"],
            r["wallet_address"],
        )
    )
    rank = 0
    for r in rows:
        if is_control(r):
            r["lead_rank"] = ""
        else:
            rank += 1
            r["lead_rank"] = rank

    fieldnames = [
        "wallet_address", "wallet_pseudonym", "review_label", "lead_rank", "lead_score",
        "market_condition_id", "event_id", "market_question", "topic_label", "possible_information_channel",
        "resolved_outcome", "side_bought", "signal_trade_count", "signal_notional_usd",
        "weighted_avg_price", "min_price", "max_price", "min_hours_pre_resolution",
        "max_hours_pre_resolution", "implied_profit_usd", "first_buy_timestamp_utc",
        "last_buy_timestamp_utc", "lifetime_profit_usd", "lifetime_volume_usd",
        "in_window_trade_count", "wash_vol_share", "wash_label", "activity_capped",
        "prior_activity_count", "prior_median_size_usd", "notional_vs_prior_median",
    ]
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    selected_wallets = sorted({r["wallet_address"] for r in rows if r["review_label"] == "Selected follow-up"})
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_rows": len(rows),
        "selected_follow_up_wallets": selected_wallets,
        "selected_follow_up_rows": sum(1 for r in rows if r["review_label"] == "Selected follow-up"),
        "screen": {
            "window_start": WINDOW_START.isoformat(),
            "window_end": WINDOW_END.isoformat(),
            "price_band": [PRICE_LO, PRICE_HI],
            "min_hours_pre_resolution": MIN_HOURS_PRE_RESOLUTION,
            "min_signal_notional_usd": MIN_SIGNAL_NOTIONAL_USD,
        },
    }
    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
