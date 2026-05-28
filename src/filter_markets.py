"""
filter_markets.py
-----------------
Reads data/markets.csv (raw Gamma discovery) and produces data/markets_filtered.csv,
the analysis set used downstream by backfill_trades.py and the heuristics scoring.

The raw dataset is preserved intact so another analyst can audit or re-derive
the universe.
This step applies:

1.  Hard date filter: end_date in [2025-11-01, 2026-05-01] (inclusive).
2.  Closed/resolved-only (heuristics need resolution outcome).
3.  Volume floor: $50,000 lifetime market volume — enough liquidity that trade
    behavior is meaningful, not noise. Configurable via --min-volume.
4.  Reclassify the 'other' bucket using a richer media and attention keyword set
    (Google searches, YouTube creators, celebrity events, awards leaks).
5.  Hard exclude sports, politics, cryptocurrency, fights, and macroeconomics
    that bled through generic tags like 'music' or 'celebrities'.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Stricter exclude list (applied to event_title.lower()).
HARD_EXCLUDE = [
    # boxing / MMA / influencer fights
    "boxing", "vs anthony joshua", "vs. chase demoor", "jake paul", "andrew tate vs",
    "ufc ", "wwe ", "wrestlemania",
    # sports
    "nfl", "nba", "mlb", "nhl", "soccer", "premier league", "champions league",
    "world cup", "super bowl", "halftime show winner", "halftime show point",
    "f1 ", "formula 1", "tennis", "wimbledon",
    # politics / macro
    "election", "president", "trump", "biden", "harris", "putin", "zelensky",
    "supreme leader", "iran's next", "venezuela", "maduro", "nato", "ceasefire",
    "obama divorce",  # tabloid politics-adjacent, low info content
    "fed ", "fomc", "rate cut", "rate hike", "interest rate",
    # cryptocurrency
    "bitcoin", "ethereum", "btc ", "eth ", "doge", "solana", "memecoin",
]

# Keyword-based reclassification of the 'other' bucket into media and attention sub-buckets.
RECLASSIFY: list[tuple[str, str]] = [
    # (regex, bucket)
    (r"#1 searched (person|tv show|movie|song) on google", "release_performance"),
    (r"most streamed|spotify|apple music|billboard", "release_performance"),
    (r"box office|opening weekend|rotten tomatoes|metacritic|imdb", "release_performance"),
    (r"mrbeast|kai cenat|kick streamer|twitch streamer|youtube", "release_performance"),
    (r"diddy|kanye|drake|taylor swift|travis kelce|kim k|kardash", "release_performance"),
    (r"survivor|love island|bachelor|bachelorette|big brother|the voice|american idol|drag race|top chef", "reality_tv"),
    (r"oscar|academy award|grammy|emmy|tony award|golden globe|bafta|met gala|vma|billboard music award|people's choice|critics choice", "awards"),
    (r"time person of the year|time poty", "awards"),
    (r"stranger things|new episode|season \d+|series premiere|series finale", "reality_tv"),
]

MEDIA_ATTENTION_BUCKETS = {"reality_tv", "awards", "release_performance"}


def reclassify_bucket(title: str, current: str) -> str:
    if current in MEDIA_ATTENTION_BUCKETS:
        return current
    t = title.lower()
    for pat, bucket in RECLASSIFY:
        if re.search(pat, t):
            return bucket
    return current  # keep as 'other'


def is_excluded(title: str) -> bool:
    t = title.lower()
    return any(x in t for x in HARD_EXCLUDE)


def in_window(end_iso: str | None, start: str, end: str) -> bool:
    if not end_iso:
        return False
    return start <= end_iso[:10] <= end


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(DATA / "markets.csv"))
    ap.add_argument("--out", dest="out", default=str(DATA / "markets_filtered.csv"))
    ap.add_argument("--summary", dest="summary", default=str(DATA / "markets_filtered_summary.json"))
    ap.add_argument("--min-volume", type=float, default=50_000.0)
    ap.add_argument("--window-start", default="2025-11-01")
    ap.add_argument("--window-end", default="2026-05-01")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.inp)))
    print(f"raw markets: {len(rows)}", file=sys.stderr)

    kept: list[dict] = []
    drop_reasons: Counter[str] = Counter()

    for r in rows:
        if not in_window(r.get("end_date"), args.window_start, args.window_end):
            drop_reasons["out_of_window"] += 1
            continue
        if r.get("closed") != "True":
            drop_reasons["not_closed"] += 1
            continue
        if is_excluded(r.get("event_title", "")):
            drop_reasons["excluded_topic"] += 1
            continue
        try:
            vol = float(r.get("volume_usd") or 0)
        except ValueError:
            vol = 0.0
        if vol < args.min_volume:
            drop_reasons["below_volume_floor"] += 1
            continue

        new_bucket = reclassify_bucket(r.get("event_title", ""), r.get("bucket", "other"))
        r["bucket"] = new_bucket
        if new_bucket not in MEDIA_ATTENTION_BUCKETS:
            drop_reasons["bucket_not_media_attention"] += 1
            continue

        # Heuristic A2 will need this; left blank for manual curation pass.
        r.setdefault("reveal_window_start", "")
        kept.append(r)

    # Sort by bucket then end_date.
    kept.sort(key=lambda r: (r["bucket"], r["end_date"]))

    if kept:
        fieldnames = list(kept[0].keys())
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(kept)

    by_bucket = Counter(r["bucket"] for r in kept)
    by_month = Counter(r["end_date"][:7] for r in kept)
    total_vol = sum(float(r["volume_usd"]) for r in kept)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": args.inp,
        "output_path": args.out,
        "window": [args.window_start, args.window_end],
        "min_volume_usd": args.min_volume,
        "raw_count": len(rows),
        "kept_count": len(kept),
        "drop_reasons": dict(drop_reasons),
        "kept_by_bucket": dict(by_bucket),
        "kept_by_month": dict(sorted(by_month.items())),
        "total_volume_usd": total_vol,
    }
    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nwrote {len(kept)} filtered markets to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
