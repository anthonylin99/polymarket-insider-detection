"""
review_markets.py
--------------------
Market review for the interview-ready report.

The filter narrows the universe to media / attention-index markets:
Google Year in Search, Spotify / music charts, YouTube / creator metrics,
awards, and entertainment-release markets.

The script preserves the raw Gamma discovery file and writes a reviewed
market set with explicit topic labels and include reasons.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

POP_MEDIA_TOPICS = {
    "attention_index_google_search",
    "music_streaming_rank",
    "creator_platform_metric",
    "awards",
    "entertainment_release",
}

AWARDS = re.compile(
    r"oscar|academy award|grammy|emmy|tony award|golden globe|bafta|sag award|"
    r"met gala|vma|billboard music award|people's choice|critics choice",
    re.I,
)
GOOGLE_SEARCH = re.compile(r"#1 searched (person|tv show|movie|song) on google", re.I)
MUSIC_STREAMING = re.compile(
    r"spotify|apple music|billboard|most streamed|top song|top album|top artist|"
    r"monthly listeners|debut(?:s|ed)? at #1",
    re.I,
)
CREATOR_PLATFORM = re.compile(r"youtube|subscriber|mrbeast|twitch|kick streamer|creator", re.I)
ENTERTAINMENT_RELEASE = re.compile(
    r"box office|opening weekend|rotten tomatoes|metacritic|imdb|release(?:d)?|"
    r"new episode|series premiere|series finale|season \d+|stranger things|album|song",
    re.I,
)

AI_MODEL = re.compile(
    r"\b(ai model|openai|deepseek|xai|anthropic|zhipu|mistral|alibaba)\b", re.I
)
SPORTS_FRAMED = re.compile(
    r"\b(super bowl|big game halftime|halftime show|nfl|nba|mlb|nhl|ufc|"
    r"champions league|world cup|wimbledon|f1|formula 1)\b",
    re.I,
)
LEGAL_OR_PERSONAL = re.compile(
    r"\b(prison|sex trafficking|found guilty|sentenced|married|engaged|divorce|"
    r"pregnant|baby: boy or girl|dating|breakup|break up)\b",
    re.I,
)
POLITICS_MACRO_CRYPTO = re.compile(
    r"\b(election|president|senate|congress|fed |fomc|rate cut|rate hike|"
    r"bitcoin|ethereum|solana|crypto|btc |eth )\b",
    re.I,
)


def in_window(end_iso: str | None, start: str, end: str) -> bool:
    if not end_iso:
        return False
    return start <= end_iso[:10] <= end


def classify(row: dict) -> tuple[str | None, str | None, str | None]:
    """Return (topic_label, include_reason, exclusion_reason)."""
    text = f"{row.get('event_title', '')} {row.get('market_question', '')}"

    if AI_MODEL.search(text):
        return None, None, "ai_model_benchmark"
    if SPORTS_FRAMED.search(text):
        return None, None, "sports_framed_market"
    if LEGAL_OR_PERSONAL.search(text):
        return None, None, "celebrity_legal_or_personal_life"

    is_google = bool(GOOGLE_SEARCH.search(text))
    if is_google:
        return (
            "attention_index_google_search",
            "Google Year in Search attention-index market; retained as a shared resolver complex.",
            None,
        )

    if POLITICS_MACRO_CRYPTO.search(text):
        return None, None, "politics_macro_or_crypto"

    if AWARDS.search(text):
        return "awards", "Awards market with plausible voter / industry information asymmetry.", None
    if MUSIC_STREAMING.search(text):
        return (
            "music_streaming_rank",
            "Music or streaming chart market with measurable public and industry data.",
            None,
        )
    if CREATOR_PLATFORM.search(text):
        return (
            "creator_platform_metric",
            "Creator / platform attention metric with public data and possible insider-adjacent access.",
            None,
        )
    if ENTERTAINMENT_RELEASE.search(text):
        return (
            "entertainment_release",
            "Entertainment release or performance market with production / distribution information asymmetry.",
            None,
        )

    return None, None, "not_media_attention_index"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(DATA / "markets.csv"))
    ap.add_argument("--out", default=str(DATA / "markets_reviewed.csv"))
    ap.add_argument("--excluded-out", default=str(DATA / "markets_excluded.csv"))
    ap.add_argument("--summary", default=str(DATA / "markets_reviewed_summary.json"))
    ap.add_argument("--min-volume", type=float, default=50_000.0)
    ap.add_argument("--window-start", default="2025-11-01")
    ap.add_argument("--window-end", default="2026-05-01")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.inp)))
    kept: list[dict] = []
    excluded: list[dict] = []
    drop_reasons: Counter[str] = Counter()

    for row in rows:
        row = dict(row)
        row["original_bucket"] = row.get("bucket", "")

        if not in_window(row.get("end_date"), args.window_start, args.window_end):
            reason = "out_of_window"
        elif row.get("closed") != "True":
            reason = "not_closed"
        elif not row.get("condition_id"):
            reason = "missing_condition_id"
        elif not row.get("resolved_outcome"):
            reason = "missing_resolved_outcome"
        else:
            try:
                volume = float(row.get("volume_usd") or 0)
            except ValueError:
                volume = 0.0
            if volume < args.min_volume:
                reason = "below_volume_floor"
            else:
                topic, include_reason, exclusion_reason = classify(row)
                if topic:
                    row["topic_label"] = topic
                    row["include_reason"] = include_reason or ""
                    row["exclusion_reason"] = ""
                    kept.append(row)
                    continue
                reason = exclusion_reason or "not_media_attention_index"

        row["topic_label"] = ""
        row["include_reason"] = ""
        row["exclusion_reason"] = reason
        drop_reasons[reason] += 1
        excluded.append(row)

    kept.sort(key=lambda r: (r["topic_label"], r["end_date"], r["market_question"]))
    excluded.sort(key=lambda r: (r["exclusion_reason"], r.get("end_date", ""), r.get("market_question", "")))

    if kept:
        with open(args.out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(kept[0].keys()))
            writer.writeheader()
            writer.writerows(kept)

    if excluded:
        with open(args.excluded_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(excluded[0].keys()))
            writer.writeheader()
            writer.writerows(excluded)

    topic_counts = Counter(r["topic_label"] for r in kept)
    topic_volume = Counter()
    for r in kept:
        topic_volume[r["topic_label"]] += float(r.get("volume_usd") or 0)

    baseline_path = DATA / "markets_filtered.csv"
    removed_by_review = []
    if baseline_path.exists():
        baseline = {r["condition_id"]: r for r in csv.DictReader(open(baseline_path))}
        kept_ids = {r["condition_id"] for r in kept}
        removed_by_review = [r for cid, r in baseline.items() if cid not in kept_ids]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": args.inp,
        "output_path": args.out,
        "excluded_output_path": args.excluded_out,
        "window": [args.window_start, args.window_end],
        "min_volume_usd": args.min_volume,
        "raw_count": len(rows),
        "kept_count": len(kept),
        "kept_distinct_events": len({r["event_id"] for r in kept}),
        "kept_total_lifetime_volume_usd": round(sum(float(r.get("volume_usd") or 0) for r in kept), 2),
        "drop_reasons": dict(drop_reasons),
        "kept_by_topic": dict(topic_counts),
        "kept_volume_by_topic": {k: round(v, 2) for k, v in topic_volume.items()},
        "removed_by_review_count": len(removed_by_review),
        "removed_by_review_lifetime_volume_usd": round(
            sum(float(r.get("volume_usd") or 0) for r in removed_by_review), 2
        ),
    }
    with open(args.summary, "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
