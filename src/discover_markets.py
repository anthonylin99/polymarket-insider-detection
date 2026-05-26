"""
discover_markets.py
-------------------
Polymarket pop-culture market discovery for the Inca Investigations Analyst challenge.

Pulls events from the public Gamma API across in-scope tag IDs (reality TV, awards,
music/film release performance, celebrities), filters to the challenge window
(Nov 1, 2025 - May 1, 2026), expands each event into its constituent binary markets,
and writes data/markets.csv.

Window is applied on `endDate` (resolution date), which is what matters for the
heuristics in report/heuristics.md.

API reference:
- https://gamma-api.polymarket.com/events
- https://gamma-api.polymarket.com/tags
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

GAMMA = "https://gamma-api.polymarket.com"
WINDOW_START = datetime(2025, 11, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 5, 1, tzinfo=timezone.utc)

# In-scope tag IDs (slug — label), curated from /tags scan on 2026-05-26.
# Reality-TV bucket: tv, season-finale, top-model, bachelorette, plus broad celebrities/celebrity
# Awards bucket: (no first-class awards tag — captured via keyword fallback below)
# Release-performance bucket: music, music-industry, albums, charts, apple-music,
#                              release-date, public-release, animated-feature-film
IN_SCOPE_TAG_IDS: list[int] = [
    100,     # music
    286,     # celebrities
    330,     # season-finale
    429,     # music-industry
    448,     # swift (Taylor Swift markets — pop culture)
    724,     # charts
    1310,    # albums
    1344,    # public-release
    1347,    # apple-music
    1490,    # animated-feature-film
    1535,    # celebrity
    5,       # release-date
    100338,  # tv
    101864,  # top-model
    104280,  # bachelorette
    102136,  # Timothée Chalamet
]

# Keyword fallback: events whose title matches these patterns are kept even if their
# tag set doesn't include any of the above (awards bodies rarely tagged consistently).
AWARDS_KEYWORDS = [
    "oscar", "academy award", "grammy", "emmy", "tony award", "golden globe",
    "bafta", "sag award", "mtv vma", "vma", "billboard music award",
    "people's choice", "critics choice", "met gala",
]
RELEASE_KEYWORDS = [
    "box office", "opening weekend", "rotten tomatoes", "metacritic",
    "billboard 200", "billboard hot 100", "first-week", "first week",
    "debut at #1", "number one album", "streaming", "spotify", "imdb",
]
REALITY_KEYWORDS = [
    "survivor", "love island", "bachelor", "bachelorette", "big brother",
    "the voice", "american idol", "dancing with the stars", "rupaul",
    "drag race", "top chef", "masterchef", "real housewives",
    "the apprentice", "the challenge", "beast games", "squid game",
    "elimination", "winner",
]
ALL_KEYWORDS = AWARDS_KEYWORDS + RELEASE_KEYWORDS + REALITY_KEYWORDS

# Hard excludes (avoid sports/politics/crypto bleeding through generic tags like "music")
EXCLUDE_KEYWORDS = [
    "nfl", "nba", "mlb", "nhl", "ufc", "f1 ", "premier league", "champions league",
    "world cup", "super bowl", "election", "president", "trump", "biden", "harris",
    "bitcoin", "ethereum", "crypto", "btc ", "eth ",
]

HEADERS = {"User-Agent": "polymarket-insider-detection/0.1 (research)"}
OUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR.mkdir(exist_ok=True)


def in_window(end_date_iso: str | None) -> bool:
    if not end_date_iso:
        return False
    try:
        ts = datetime.fromisoformat(end_date_iso.replace("Z", "+00:00"))
    except ValueError:
        return False
    return WINDOW_START <= ts <= WINDOW_END


def keyword_match(title: str) -> bool:
    t = (title or "").lower()
    if any(x in t for x in EXCLUDE_KEYWORDS):
        return False
    return any(x in t for x in ALL_KEYWORDS)


def bucket(title: str, tag_labels: list[str]) -> str:
    t = (title or "").lower()
    if any(k in t for k in AWARDS_KEYWORDS):
        return "awards"
    if any(k in t for k in REALITY_KEYWORDS) or any(k in tag_labels for k in ("tv", "bachelorette", "top-model", "season-finale")):
        return "reality_tv"
    if any(k in t for k in RELEASE_KEYWORDS) or any(k in tag_labels for k in ("music", "albums", "charts", "release-date", "public-release", "animated-feature-film", "apple-music")):
        return "release_performance"
    return "other"


def fetch_events_for_tag(tag_id: int) -> Iterable[dict[str, Any]]:
    """Paginate /events for a given tag_id, restricted to closed/resolved events."""
    offset = 0
    page_size = 100
    while True:
        params = {
            "tag_id": tag_id,
            "closed": "true",
            "limit": page_size,
            "offset": offset,
            "order": "endDate",
            "ascending": "false",
        }
        r = requests.get(f"{GAMMA}/events", params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        page = r.json()
        if not page:
            return
        for ev in page:
            yield ev
        if len(page) < page_size:
            return
        offset += page_size
        # Stop pagination once we drop below the window (events are ordered desc by endDate).
        if all(not in_window(ev.get("endDate")) and (ev.get("endDate") or "9999") < WINDOW_START.isoformat() for ev in page):
            return
        time.sleep(0.2)


def fetch_open_events_for_tag(tag_id: int) -> Iterable[dict[str, Any]]:
    """Open events in window — captures markets that have not resolved yet (less relevant
    for the heuristics but useful for completeness of the dataset)."""
    offset = 0
    page_size = 100
    while True:
        params = {
            "tag_id": tag_id,
            "closed": "false",
            "limit": page_size,
            "offset": offset,
        }
        r = requests.get(f"{GAMMA}/events", params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        page = r.json()
        if not page:
            return
        for ev in page:
            yield ev
        if len(page) < page_size:
            return
        offset += page_size
        time.sleep(0.2)


def safe_json(s: str | list | None) -> list:
    if s is None:
        return []
    if isinstance(s, list):
        return s
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return []


def main() -> int:
    seen_event_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    per_tag_counts: dict[int, int] = {}

    for tag_id in IN_SCOPE_TAG_IDS:
        print(f"[tag {tag_id}] discovering events...", file=sys.stderr)
        kept = 0
        for ev in list(fetch_events_for_tag(tag_id)) + list(fetch_open_events_for_tag(tag_id)):
            eid = str(ev.get("id"))
            if eid in seen_event_ids:
                continue

            end_iso = ev.get("endDate") or ""
            title = ev.get("title") or ""
            ev_tag_labels = [t.get("slug") for t in ev.get("tags", []) if isinstance(t, dict)]

            window_ok = in_window(end_iso)
            kw_ok = keyword_match(title)
            # Keep if (a) endDate in window AND tag is in-scope, OR (b) keyword-matches our pop-culture lists
            if not (window_ok or kw_ok):
                continue
            if not window_ok and not kw_ok:
                continue
            if any(x in title.lower() for x in EXCLUDE_KEYWORDS):
                continue

            seen_event_ids.add(eid)
            kept += 1
            ev_bucket = bucket(title, ev_tag_labels)

            for mkt in ev.get("markets", []) or []:
                outcomes = safe_json(mkt.get("outcomes"))
                outcome_prices = safe_json(mkt.get("outcomePrices"))
                resolved_outcome = None
                resolved_price = None
                if mkt.get("closed") and outcomes and outcome_prices:
                    try:
                        idx = max(range(len(outcome_prices)), key=lambda i: float(outcome_prices[i]))
                        resolved_outcome = outcomes[idx]
                        resolved_price = float(outcome_prices[idx])
                    except (ValueError, IndexError):
                        pass

                rows.append({
                    "event_id": eid,
                    "event_slug": ev.get("slug"),
                    "event_title": title,
                    "market_id": mkt.get("id"),
                    "market_question": mkt.get("question"),
                    "market_slug": mkt.get("slug"),
                    "condition_id": mkt.get("conditionId"),
                    "category": mkt.get("category") or ev.get("category"),
                    "bucket": ev_bucket,
                    "tag_id_source": tag_id,
                    "tag_labels": "|".join(ev_tag_labels) if ev_tag_labels else "",
                    "start_date": mkt.get("startDate") or ev.get("startDate"),
                    "end_date": mkt.get("endDate") or end_iso,
                    "closed_time": mkt.get("closedTime"),
                    "active": mkt.get("active"),
                    "closed": mkt.get("closed"),
                    "archived": mkt.get("archived"),
                    "volume_usd": float(mkt.get("volumeNum") or 0),
                    "liquidity_usd": float(mkt.get("liquidityNum") or 0),
                    "outcomes": "|".join(outcomes) if outcomes else "",
                    "resolved_outcome": resolved_outcome,
                    "resolved_price": resolved_price,
                    "resolution_source": mkt.get("resolutionSource") or ev.get("resolutionSource"),
                    "market_maker_address": mkt.get("marketMakerAddress"),
                    "ev_volume_usd_total": float(ev.get("volume") or 0),
                })
        per_tag_counts[tag_id] = kept
        print(f"[tag {tag_id}] kept {kept} events", file=sys.stderr)

    # De-dupe markets across tag overlap (a market can be in multiple tags).
    by_market = {}
    for r in rows:
        key = r["market_id"]
        if key not in by_market:
            by_market[key] = r
    rows = list(by_market.values())

    rows.sort(key=lambda r: (r.get("end_date") or "", r.get("event_id") or ""))

    out_path = OUT_DIR / "markets.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with out_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    # Discovery summary for the data dictionary.
    in_window_count = sum(1 for r in rows if in_window(r.get("end_date")))
    resolved_count = sum(1 for r in rows if r.get("closed"))
    bucket_counts: dict[str, int] = {}
    for r in rows:
        bucket_counts[r["bucket"]] = bucket_counts.get(r["bucket"], 0) + 1

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
        "tag_ids_queried": IN_SCOPE_TAG_IDS,
        "total_markets_written": len(rows),
        "markets_in_window_by_end_date": in_window_count,
        "markets_closed_resolved": resolved_count,
        "bucket_counts": bucket_counts,
        "per_tag_event_counts": per_tag_counts,
    }
    with (OUT_DIR / "markets_discovery_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nwrote {len(rows)} markets to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
