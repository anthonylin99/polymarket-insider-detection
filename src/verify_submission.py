"""
verify_submission.py
--------
Fast consistency checks for the Inca submission artifacts.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_MARKET_PATTERNS = {
    "ai_model": re.compile(r"\b(ai model|openai|deepseek|xai|anthropic|zhipu|mistral|alibaba)\b", re.I),
    "sports_framed": re.compile(r"\b(super bowl|big game halftime|halftime show)\b", re.I),
    "celebrity_legal_personal": re.compile(
        r"\b(prison|sex trafficking|found guilty|sentenced|married|engaged|divorce|pregnant|baby: boy or girl)\b",
        re.I,
    ),
}


def read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(open(path)))


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    markets = read_csv(DATA / "markets_reviewed.csv")
    candidate_leads = read_csv(DATA / "candidate_wallet_leads.csv")
    candidate_movements = read_csv(DATA / "candidate_market_movements.csv")
    wash_stats = read_csv(DATA / "wallet_wash_stats.csv")
    report_text = (ROOT / "report" / "report.md").read_text()

    for row in markets:
        text = f"{row.get('event_title', '')} {row.get('market_question', '')}"
        if not row.get("condition_id"):
            errors.append(f"blank condition_id: {row.get('market_question')}")
        if not row.get("resolved_outcome"):
            errors.append(f"missing resolved_outcome: {row.get('market_question')}")
        if not row.get("include_reason"):
            errors.append(f"missing include_reason: {row.get('market_question')}")
        for label, pattern in FORBIDDEN_MARKET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"forbidden {label} market retained: {row.get('market_question')}")

    expected_selected = {
        "0xcd71fd5370880f3d92bb941e628c05840fe0d127",
        "0x8564848285e54c65f6cc2e3930b49362fbd84b2e",
        "0x614ef98a8be021de3a974942b2fb98794ff34f1b",
    }
    selected_rows = [r for r in candidate_leads if r["review_label"] == "Selected follow-up"]
    selected_wallets = {r["wallet_address"] for r in selected_rows}
    if not expected_selected.issubset(selected_wallets):
        errors.append(f"selected wallet set missing expected leads: {sorted(expected_selected - selected_wallets)}")
    if any(r["topic_label"] == "attention_index_google_search" for r in selected_rows):
        errors.append("Google-search public-data control was selected as a follow-up lead")
    if len(selected_rows) < 3:
        errors.append(f"expected at least 3 selected follow-up rows, found {len(selected_rows)}")

    if len(candidate_movements) != len(selected_rows):
        errors.append(
            f"candidate movement rows ({len(candidate_movements)}) do not match selected rows ({len(selected_rows)})"
        )
    for row in candidate_movements:
        if float(row["last_price_before_resolution"]) < 0.95:
            errors.append(f"unexpected weak pre-resolution price for {row['wallet_pseudonym']}: {row['market_question']}")
        if float(row["settlement_price"]) != 1.0:
            errors.append(f"unexpected settlement price for {row['wallet_pseudonym']}: {row['market_question']}")

    forbidden_report_phrases = ["/pagebreak", "v2", "first version", "Takeaway for Inca Digital"]
    for phrase in forbidden_report_phrases:
        if phrase in report_text:
            errors.append(f"report contains forbidden phrase: {phrase}")

    capped_wallets = sum(1 for r in wash_stats if int(r["total_n"]) >= 2_000)
    if capped_wallets < 1:
        errors.append("activity cap disclosure count is zero")
    if any(r["activity_capped"] == "True" for r in selected_rows) and "capped by public endpoints" not in report_text:
        warnings.append("At least one selected wallet activity history is capped at 2,000 records; report must disclose this.")

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "markets_checked": len(markets),
        "candidate_rows_checked": len(candidate_leads),
        "candidate_movement_rows_checked": len(candidate_movements),
        "selected_follow_up_wallets": sorted(selected_wallets),
        "selected_follow_up_rows": len(selected_rows),
        "capped_wallets_in_activity_sample": capped_wallets,
        "errors": errors,
        "warnings": warnings,
    }
    with open(DATA / "verification_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
