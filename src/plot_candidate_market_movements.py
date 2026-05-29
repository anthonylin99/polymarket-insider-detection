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
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORT = ROOT / "report"
CHART_DIR = REPORT / "charts"


# All numeric callouts live in the header line above the plot, never inside the
# data area, so no label can ever overlap the price line or a marker.
CHART_META = {
    "Will The Weeknd be the third most streamed Spotify artist for 2025?": {
        "file": "kevindoto_weeknd_entry.png",
        "title": "Kevindoto: The Weeknd #3 Spotify",
        "position": "$10.5k YES",
        "color": "#0f4c3f",
    },
    "Will Drake be the third most streamed Spotify artist for 2025?": {
        "file": "kevindoto_drake_entry.png",
        "title": "Kevindoto: Drake not #3 Spotify",
        "position": "$5.5k NO",
        "color": "#d28b45",
    },
    "Will 'Arirang' - BTS debut week album sales be less than 3m?": {
        "file": "allyourmonies_bts_entry.png",
        "title": "AllYourMonies: BTS sales below 3m",
        "position": "$5.7k YES",
        "color": "#496a9a",
    },
    "Will Lady Gaga win 3 Grammys?": {
        "file": "scottynooo_grammys_entry.png",
        "title": "ScottyNooo: Lady Gaga not 3 Grammys",
        "position": "$9.2k NO",
        "color": "#a14a63",
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
    settle = float(movement.get("settlement_price") or 1.0)
    color = meta["color"]

    fig, ax = plt.subplots(figsize=(6.4, 3.05))
    fig.patch.set_facecolor("#fbfaf6")
    ax.set_facecolor("#fffdf8")

    # Shade the accumulation window (first buy to last buy) so the spread of
    # fills reads at a glance, then draw the price line and markers. No text is
    # ever placed inside the axes, so nothing can overlap the price line.
    if last_x != first_x:
        ax.axvspan(first_x, last_x, color=color, alpha=0.10, lw=0,
                   label="accumulation window")
    ax.fill_between(x, y, color=color, alpha=0.06, zorder=0)
    ax.plot(x, y, color=color, linewidth=2.0, zorder=2)
    ax.axhline(avg_entry, color="#6b7b76", linestyle=":", linewidth=1.1,
               label=f"avg fill {avg_entry:.0f}c", zorder=1)
    ax.scatter(buy_x, buy_y, color="#111111", s=22, zorder=4, label="candidate buys")
    ax.scatter([worst_x], [cents(worst["price"])], color="#c44536", s=34, zorder=5,
               label=f"low {cents(worst['price']):.0f}c")

    # Header: title plus the single requested callout, in the whitespace above
    # the plot where the price line can never reach.
    ax.set_title(meta["title"], fontsize=11.5, loc="left", color="#102b24",
                 pad=22, fontweight="bold")
    ax.text(0, 1.03, f"{meta['position']}  ·  avg fill {avg_entry:.0f}c",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=8.5,
            color="#53605b")

    # Zoom to the entry-and-resolution window: trim the long flat tail once the
    # contract has settled within 3c of its resolution value.
    move_end_idx = 0
    for i, r in enumerate(rows):
        if abs(r["price"] - settle) > 0.03:
            move_end_idx = i
    move_end_x = rows[move_end_idx]["timestamp_dt"]
    left = min(x)
    window = max(move_end_x - left, timedelta(hours=6))
    ax.set_xlim(left - window * 0.03, move_end_x + window * 0.14)
    ax.set_ylim(0, 105)

    ax.set_ylabel("Contract price", fontsize=8.3, color="#33423d")
    ax.yaxis.set_major_locator(MultipleLocator(25))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{int(value)}c"))
    window_days = window.total_seconds() / 86_400
    if window_days <= 4:
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d\n%H:%M"))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    ax.grid(True, axis="y", color="#e1e6e0", linewidth=0.6)
    ax.tick_params(labelsize=8, colors="#33423d")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd8d2")
    ax.spines["bottom"].set_color("#cbd8d2")

    # Legend sits below the axes in empty space, never over the data.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=4,
              fontsize=7.5, frameon=False, handletextpad=0.4, columnspacing=1.4)

    out_path = out_dir / meta["file"]
    fig.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.1)
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
