"""
plot_candidate_market_movements.py
----------------------------------
Render one chart per selected candidate market.

Each chart is intentionally standalone for Word/PDF submission: it uses a
Polymarket-style cents axis, labels the candidate wallet's first and last buy,
shows the average entry price, and stops at the last pre-resolution trade.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORT = ROOT / "report"
CHART_DIR = REPORT / "charts"


CHART_META = {
    "Will The Weeknd be the third most streamed Spotify artist for 2025?": {
        "file": "kevindoto_weeknd_entry.png",
        "title": "Kevindoto: The Weeknd #3 Spotify",
        "subtitle": "$10.5k YES, 45.3c average entry",
        "color": "#0f4c3f",
        "first_offset": (18, 40),
        "last_label_y": 15,
        "last_label_ha": "right",
        "low_offset": (28, 22),
    },
    "Will Drake be the third most streamed Spotify artist for 2025?": {
        "file": "kevindoto_drake_entry.png",
        "title": "Kevindoto: Drake not #3 Spotify",
        "subtitle": "$5.5k NO, 40.9c average entry",
        "color": "#d28b45",
        "first_offset": (20, 20),
        "last_label_y": 12,
        "last_label_ha": "left",
        "low_offset": (16, 22),
    },
    "Will 'Arirang' - BTS debut week album sales be less than 3m?": {
        "file": "allyourmonies_bts_entry.png",
        "title": "AllYourMonies: BTS sales below 3m",
        "subtitle": "$5.7k YES, 71.6c average entry",
        "color": "#496a9a",
        "first_offset": (22, 40),
        "last_label_y": 13,
        "last_label_ha": "left",
        "low_offset": (22, 14),
    },
    "Will a contestant numbered 151 - 175 win Beast Games: Season 2?": {
        "file": "cookiejar_beast_games_entry.png",
        "title": "cookiejar: Beast Games 151-175",
        "subtitle": "$5.8k YES, 78.2c average entry",
        "color": "#7b4c7e",
        "first_offset": (45, -6),
        "last_label_y": 13,
        "last_label_ha": "left",
        "low_offset": (22, 16),
    },
}


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def cents(value: float) -> float:
    return value * 100


def load_rows(path: Path) -> dict[str, list[dict]]:
    rows_by_question: dict[str, list[dict]] = {}
    for row in csv.DictReader(open(path)):
        row["relative_time_to_resolution"] = float(row["relative_time_to_resolution"])
        row["price"] = float(row["price"])
        row["timestamp_dt"] = parse_dt(row["timestamp_utc"])
        rows_by_question.setdefault(row["market_question"], []).append(row)
    return rows_by_question


def load_movements(path: Path) -> dict[str, dict]:
    return {row["market_question"]: row for row in csv.DictReader(open(path))}


def render_chart(question: str, rows: list[dict], movement: dict, out_dir: Path) -> Path:
    meta = CHART_META[question]
    last_pre_resolution = parse_dt(movement["last_price_before_resolution_utc"])
    rows = sorted(
        [r for r in rows if r["timestamp_dt"] <= last_pre_resolution],
        key=lambda r: r["timestamp_dt"],
    )
    buy_rows = [r for r in rows if r["is_candidate_buy"] == "True"]
    first_buy = min(buy_rows, key=lambda r: r["timestamp_dt"])
    last_buy = max(buy_rows, key=lambda r: r["timestamp_dt"])
    worst = min(rows, key=lambda r: r["price"])

    x = [r["timestamp_dt"] for r in rows]
    y = [cents(r["price"]) for r in rows]
    buy_x = [r["timestamp_dt"] for r in buy_rows]
    buy_y = [cents(r["price"]) for r in buy_rows]
    first_x = first_buy["timestamp_dt"]
    last_x = last_buy["timestamp_dt"]
    worst_x = worst["timestamp_dt"]
    avg_entry = cents(float(movement["candidate_avg_entry_price"]))

    fig, ax = plt.subplots(figsize=(6.4, 2.65))
    fig.patch.set_facecolor("#fbfaf6")
    ax.set_facecolor("#fffdf8")
    ax.plot(x, y, color=meta["color"], linewidth=1.9)
    ax.scatter(buy_x, buy_y, color="#111111", s=24, zorder=4)
    ax.axvline(first_x, color="#111111", linestyle="--", linewidth=0.9)
    if last_x != first_x:
        ax.axvline(last_x, color="#555555", linestyle="--", linewidth=0.8)
    ax.axhline(avg_entry, color="#6b7b76", linestyle=":", linewidth=0.9)
    ax.scatter([worst_x], [cents(worst["price"])], color="#c44536", s=24, zorder=5)

    ax.annotate(
        f"first buy\n{cents(first_buy['price']):.0f}c",
        xy=(first_x, cents(first_buy["price"])),
        xytext=meta["first_offset"],
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "color": "#111111", "lw": 0.8},
        fontsize=8,
        color="#17201c",
        bbox={"boxstyle": "round,pad=0.15", "fc": "#fffdf8", "ec": "none", "alpha": 0.94},
        zorder=8,
    )
    if last_x != first_x:
        ax.text(
            last_x,
            meta["last_label_y"],
            f"last buy\n{cents(last_buy['price']):.0f}c",
            fontsize=8,
            color="#33423d",
            ha=meta["last_label_ha"],
            va="bottom",
            bbox={"boxstyle": "round,pad=0.15", "fc": "#fffdf8", "ec": "none", "alpha": 0.94},
            zorder=8,
        )
    if worst_x != first_x or abs(worst["price"] - first_buy["price"]) > 0.001:
        ax.annotate(
            f"low {cents(worst['price']):.0f}c",
            xy=(worst_x, cents(worst["price"])),
            xytext=meta["low_offset"],
            textcoords="offset points",
            arrowprops={"arrowstyle": "->", "color": "#c44536", "lw": 0.8},
            fontsize=8,
            color="#6f211a",
            bbox={"boxstyle": "round,pad=0.12", "fc": "#fffdf8", "ec": "none", "alpha": 0.9},
            zorder=8,
        )
    ax.set_title(meta["title"], fontsize=11, loc="left", color="#102b24", pad=10)
    ax.text(0, 1.01, meta["subtitle"], transform=ax.transAxes, ha="left", va="bottom", fontsize=8.5, color="#53605b")
    span = max(x) - min(x)
    ax.set_xlim(min(x), max(x) + span * 0.04)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Market trading time", fontsize=8.3, color="#33423d")
    ax.set_ylabel("Contract price", fontsize=8.3, color="#33423d")
    ax.yaxis.set_major_locator(MultipleLocator(25))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{int(value)}c"))
    span_days = (max(x) - min(x)).total_seconds() / 86_400
    if span_days <= 4:
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d\n%H:%M"))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    ax.grid(True, axis="y", color="#d8ded8", linewidth=0.6)
    ax.tick_params(labelsize=8, colors="#33423d")
    for spine in ax.spines.values():
        spine.set_color("#cbd8d2")

    out_path = out_dir / meta["file"]
    fig.tight_layout(pad=0.8)
    fig.savefig(out_path, dpi=190, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default=str(DATA / "candidate_market_price_points.csv"))
    ap.add_argument("--movements", default=str(DATA / "candidate_market_movements.csv"))
    ap.add_argument("--out-dir", default=str(CHART_DIR))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_by_question = load_rows(Path(args.points))
    movements = load_movements(Path(args.movements))

    outputs = []
    for question in CHART_META:
        outputs.append(render_chart(question, rows_by_question[question], movements[question], out_dir))

    # Keep a small manifest so support packages can include the chart set without
    # relying on implicit filenames.
    manifest = out_dir / "manifest.txt"
    manifest.write_text("\n".join(str(p.name) for p in outputs) + "\n")
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
