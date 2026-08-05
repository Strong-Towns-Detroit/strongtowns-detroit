#!/usr/bin/env python3
"""Normalize BZA occurrence decisions and select a case-history outcome."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_OCCURRENCES = HERE / "bza_dataset_gemini/case_occurrences.csv"
DEFAULT_HISTORIES = HERE / "bza_dataset_gemini/case_histories.csv"
DEFAULT_OUTPUT = HERE / "bza_dataset_gemini"

POSITIVE = re.compile(
    r"\b(?:GRANT(?:ED)?|APPROV(?:E|ED)|REVERS(?:E|ED)|"
    r"OVERTURN(?:ED)?|WAIV(?:E|ED))\b"
)
NEGATIVE = re.compile(r"\b(?:DENY|DENIED|UPHELD|UPHOLD|AFFIRM(?:ED)?)\b")
PROCEDURAL = re.compile(
    r"\b(?:ADJOURN|POSTPON|UNDER ADVIS|TAKEN UNDER|RE-?HEARING|"
    r"REHEARD|RECONSIDERATION|EXPEDITED|NO ACTION)\b"
)


def normalize_occurrence(row: pd.Series) -> tuple[str, str]:
    status = str(row.get("decision_status", "")).lower()
    decision = "" if pd.isna(row.get("decision")) else str(row["decision"]).upper()
    if status == "dismissed" or re.search(r"\bDISMISS|WITHDRAW", decision):
        return "dismissed_withdrawn", "decision_status_or_text"
    if status in {"postponed", "under_advisement", "no_action"}:
        return "procedural_unresolved", "decision_status"
    if status == "not_recorded":
        return "not_recorded", "decision_status"
    if not decision or PROCEDURAL.search(decision):
        return "procedural_unresolved", "decision_text"
    if re.search(
        r"\b(?:COMMUNITY )?APPEAL DENIED\b|"
        r"\bAGGRIEVED (?:PERSON )?STANDARD NOT MET\b|"
        r"\bBSEED GRANT UPHELD\b",
        decision,
    ):
        return "denied_upheld", "decision_text"

    positive = bool(POSITIVE.search(decision))
    negative = bool(NEGATIVE.search(decision))
    if positive and negative:
        if re.search(r"\bDENIAL\s+REVERSED\b", decision) and not re.search(
            r"\bUSE\s+DENIED\b", decision
        ):
            return "granted_reversed", "decision_text"
        if re.search(r"\b(?:DECISION|DENIAL)\s+(?:UPHELD|AFFIRMED)\b", decision):
            return "denied_upheld", "decision_text"
        return "mixed_or_other_decided", "conflicting_decision_terms"
    if positive:
        return "granted_reversed", "decision_text"
    if negative or "MOTION FAILS" in decision:
        return "denied_upheld", "decision_text"
    return "mixed_or_other_decided", "unmapped_decision_text"


def build_outcomes(
    occurrences: pd.DataFrame, histories: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    occurrences = occurrences.copy()
    normalized = occurrences.apply(normalize_occurrence, axis=1)
    occurrences["normalized_outcome"] = [value[0] for value in normalized]
    occurrences["outcome_normalization_basis"] = [value[1] for value in normalized]
    occurrences["meeting_date"] = pd.to_datetime(occurrences["meeting_date"])

    final_rows = []
    conflicting_histories = []
    merits = {"granted_reversed", "denied_upheld", "mixed_or_other_decided"}
    for history_id, group in occurrences.groupby("case_history_id"):
        ordered = group.sort_values("meeting_date")
        merit_rows = ordered[ordered["normalized_outcome"].isin(merits)]
        if not merit_rows.empty:
            chosen = merit_rows.iloc[-1]
            outcome_basis = "latest_substantive_decision"
        else:
            chosen = ordered.iloc[-1]
            outcome_basis = "latest_procedural_disposition"
        substantive = set(merit_rows["normalized_outcome"])
        if "granted_reversed" in substantive and "denied_upheld" in substantive:
            conflicting_histories.append(history_id)
        final_rows.append({
            "case_history_id": history_id,
            "final_outcome": chosen["normalized_outcome"],
            "final_outcome_date": chosen["meeting_date"].date().isoformat(),
            "final_outcome_occurrence_id": chosen["occurrence_id"],
            "final_outcome_basis": outcome_basis,
        })
    finals = pd.DataFrame(final_rows)
    histories = histories.drop(
        columns=[
            "final_outcome", "final_outcome_date", "final_outcome_occurrence_id",
            "final_outcome_basis",
        ],
        errors="ignore",
    ).merge(finals, on="case_history_id", how="left")
    occurrences["meeting_date"] = occurrences["meeting_date"].dt.date.astype(str)
    audit = {
        "case_histories": int(len(histories)),
        "final_outcome_counts": histories["final_outcome"].value_counts().to_dict(),
        "occurrence_outcome_counts": occurrences[
            "normalized_outcome"
        ].value_counts().to_dict(),
        "histories_with_conflicting_substantive_outcomes": conflicting_histories,
        "mixed_or_other_occurrence_ids": occurrences.loc[
            occurrences["normalized_outcome"].eq("mixed_or_other_decided"),
            "occurrence_id",
        ].tolist(),
    }
    return occurrences, histories, audit


def run(occurrences_path: Path, histories_path: Path, output_dir: Path) -> None:
    occurrences = pd.read_csv(occurrences_path)
    histories = pd.read_csv(histories_path)
    occurrences, histories, audit = build_outcomes(occurrences, histories)
    occurrences.to_csv(output_dir / "occurrence_outcomes.csv", index=False)
    histories.to_csv(output_dir / "case_histories.csv", index=False)
    (output_dir / "outcome_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--occurrences", type=Path, default=DEFAULT_OCCURRENCES)
    parser.add_argument("--histories", type=Path, default=DEFAULT_HISTORIES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.occurrences, args.histories, args.output_dir)


if __name__ == "__main__":
    main()
