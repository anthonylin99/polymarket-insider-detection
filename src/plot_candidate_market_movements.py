"""
plot_candidate_market_movements.py
----------------------------------
Render one chart per selected candidate market.

Each chart is intentionally standalone for Word/PDF submission: it labels the
candidate wallet's entry window, average entry price, worst post-entry drawdown,
and final resolution.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt

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
    },
    "Will Drake be the third most streamed Spotify artist for 2025?": {
        "file": "kevindoto_drake_entry.png",
        "title": "Kevindoto: Drake not #3 Spotify",
        "subtitle": "$5.5k NO, 40.9c average entry",
        "color": "#d28b45",
    },
    "Will 'Arirang' - BTS debut week album sales be less than 3m?": {
        "file": "allyourmonies_bts_entry.png",
        "title": "AllYourMonies: BTS sales below 3m",
        "subtitle": "$5.7k YES, 71.6c average entry",
        "color": "#496a9a",
    },
    "Will a contestant numbered 151 - 175 win Beast Games: Season 2?": {
        "file": "cookiejar_beast_games_entry.png",
        "title": "cookiejar: Beast Games 151-175",
        "subtitle": "$5.8k YES, 78.2c average entry",
        "color": "#7b4c7e",
    },
}


def pct(value: str) -> float:
    return float(value) * 100


def load_rows(path: Path) -> dict[str, list[dict]]:
    rows_by_question: dict[str, list[dict]] = {}
    for row in csv.DictReader(open(path)):
        row["relative_time_to_resolution"] = float(row["relative_time_to_resolution"])
        row["price"] = float(row["price"])
        rows_by_question.setdefault(row["market_question"], []).append(row)
    return rows_by_question


def load_movements(path: Path) -> dict[str, dict]:
    return {row["market_question"]: row for row in csv.DictReader(open(path))}


def render_chart(question: str, rows: list[dict], movement: dict, out_dir: Path) -> Path:
    meta = CHART_META[question]
    rows = sorted(rows, key=lambda r: r["relative_time_to_resolution"])
    buy_rows = [r for r in rows if r["is_candidate_buy"] == "True"]
    first_buy = min(buy_rows, key=lambda r: r["relative_time_to_resolution"])
    last_buy = max(buy_rows, key=lambda r: r["relative_time_to_resolution"])
    worst = min(rows, key=lambda r: r["price"])

    x = [r["relative_time_to_resolution"] * 100 for r in rows]
    y = [r["price"] for r in rows]
    buy_x = [r["relative_time_to_resolution"] * 100 for r in buy_rows]
    buy_y = [r["price"] for r in buy_rows]
    first_x = first_buy["relative_time_to_resolution"] * 100
    last_x = last_buy["relative_time_to_resolution"] * 100
    worst_x = worst["relative_time_to_resolution"] * 100

    fig, ax = plt.subplots(figsize=(6.4, 2.65))
    fig.patch.set_facecolor("#fbfaf6")
    ax.set_facecolor("#fffdf8")
    ax.plot(x, y, color=meta["color"], linewidth=1.9)
    ax.scatter(buy_x, buy_y, color="#111111", s=24, zorder=4)
    ax.axvspan(first_x, last_x, color="#d28b45", alpha=0.13, linewidth=0)
    ax.axvline(first_x, color="#111111", linestyle="--", linewidth=0.9)
    ax.axhline(float(movement["candidate_avg_entry_price"]), color="#6b7b76", linestyle=":", linewidth=0.9)
    ax.axhline(1.0, color="#8aa89f", linewidth=0.8, linestyle=":")
    ax.scatter([worst_x], [worst["price"]], color="#c44536", s=24, zorder=5)

    ax.annotate(
        "first buy",
        xy=(first_x, first_buy["price"]),
        xytext=(min(first_x + 8, 75), min(first_buy["price"] + 0.22, 0.93)),
        arrowprops={"arrowstyle": "->", "color": "#111111", "lw": 0.8},
        fontsize=8,
        color="#17201c",
    )
    ax.annotate(
        f"low {worst['price']:.2f}",
        xy=(worst_x, worst["price"]),
        xytext=(min(worst_x + 8, 74), max(worst["price"] + 0.16, 0.18)),
        arrowprops={"arrowstyle": "->", "color": "#c44536", "lw": 0.8},
        fontsize=8,
        color="#6f211a",
    )
    ax.text(
        0.99,
        0.08,
        f"last pre-resolution {float(movement['last_price_before_resolution']):.3f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#33423d",
    )

    ax.set_title(meta["title"], fontsize=11, loc="left", color="#102b24", pad=10)
    ax.text(0, 1.01, meta["subtitle"], transform=ax.transAxes, ha="left", va="bottom", fontsize=8.5, color="#53605b")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Progress from first candidate buy to resolution (%)", fontsize=8.3, color="#33423d")
    ax.set_ylabel("Winning contract price", fontsize=8.3, color="#33423d")
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
