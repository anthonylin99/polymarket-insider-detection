"""
plot_candidate_market_movements.py
----------------------------------
Render a compact chart of contract prices after selected candidate entries.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORT = ROOT / "report"


SHORT_LABELS = {
    "Will The Weeknd be the third most streamed Spotify artist for 2025?": "Kevindoto: Weeknd #3 Spotify",
    "Will Drake be the third most streamed Spotify artist for 2025?": "Kevindoto: Drake not #3 Spotify",
    "Will 'Arirang' - BTS debut week album sales be less than 3m?": "AllYourMonies: BTS sales <3m",
    "Will a contestant numbered 151 - 175 win Beast Games: Season 2?": "cookiejar: Beast Games 151-175",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default=str(DATA / "candidate_market_price_points.csv"))
    ap.add_argument("--out", default=str(REPORT / "candidate_market_movements.png"))
    args = ap.parse_args()

    rows_by_question: dict[str, list[dict]] = defaultdict(list)
    for row in csv.DictReader(open(args.points)):
        row["relative_time_to_resolution"] = float(row["relative_time_to_resolution"])
        row["price"] = float(row["price"])
        rows_by_question[row["market_question"]].append(row)

    colors = ["#0f4c3f", "#d28b45", "#496a9a", "#7b4c7e"]
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 4.4), sharey=True)
    fig.patch.set_facecolor("#fbfaf6")
    axes = axes.flatten()

    for ax, (question, rows), color in zip(axes, rows_by_question.items(), colors):
        rows = sorted(rows, key=lambda r: r["relative_time_to_resolution"])
        x = [r["relative_time_to_resolution"] * 100 for r in rows]
        y = [r["price"] for r in rows]
        buy_x = [r["relative_time_to_resolution"] * 100 for r in rows if r["is_candidate_buy"] == "True"]
        buy_y = [r["price"] for r in rows if r["is_candidate_buy"] == "True"]
        ax.plot(x, y, color=color, linewidth=1.6)
        ax.scatter(buy_x, buy_y, color="#111111", s=13, alpha=0.75, label="candidate buys")
        ax.axhline(1.0, color="#8aa89f", linewidth=0.8, linestyle=":")
        ax.set_title(SHORT_LABELS.get(question, question[:45]), fontsize=9.5, loc="left", color="#102b24")
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 1.05)
        ax.grid(True, axis="y", color="#d8ded8", linewidth=0.6)
        ax.set_facecolor("#fffdf8")
        ax.tick_params(labelsize=8, colors="#33423d")
        for spine in ax.spines.values():
            spine.set_color("#cbd8d2")

    for ax in axes[2:]:
        ax.set_xlabel("Progress from first candidate buy to resolution (%)", fontsize=8.5, color="#33423d")
    for ax in axes[::2]:
        ax.set_ylabel("Winning contract price", fontsize=8.5, color="#33423d")

    fig.suptitle("Contract Movement After Candidate Entry", fontsize=13, color="#102b24", x=0.08, y=0.985, ha="left")
    fig.text(
        0.08,
        0.925,
        "Black dots mark the candidate wallet's qualifying buys. Each contract ultimately resolved at 1.00.",
        fontsize=8.8,
        color="#53605b",
        ha="left",
    )
    plt.tight_layout(rect=[0.04, 0.04, 0.99, 0.86])
    fig.savefig(args.out, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.12)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
