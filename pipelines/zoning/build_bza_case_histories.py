#!/usr/bin/env python3
"""Collapse BZA meeting occurrences into stable, auditable case histories."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "bza_dataset_gemini/classified_cases.csv"
DEFAULT_OVERRIDES = HERE / "bza_case_history_overrides.csv"
DEFAULT_OUTPUT = HERE / "bza_dataset_gemini"


def normalize_case_number(value: object) -> str:
    text = "" if pd.isna(value) else str(value).upper()
    return re.sub(r"[^A-Z0-9]+", "-", text).strip("-")


def make_history_id(case_number: object, discriminator: str = "default") -> str:
    case_key = normalize_case_number(case_number) or "NO-CASE-NUMBER"
    digest = hashlib.sha1(f"{case_key}|{discriminator}".encode()).hexdigest()[:10]
    return f"bza-{case_key.lower()}-{digest}"


def split_labels(value: object) -> set[str]:
    if pd.isna(value) or not str(value):
        return set()
    return {label for label in str(value).split("|") if label}


def representative(group: pd.DataFrame, column: str) -> object:
    values = group[column].dropna().astype(str)
    if values.empty:
        return pd.NA
    # Detailed text is preferable to later procedural shorthand.
    return values.loc[values.str.len().idxmax()]


def build_histories(
    frame: pd.DataFrame, overrides: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    minutes = frame[frame["record_type"].eq("minutes_case")].copy()
    minutes["meeting_date"] = pd.to_datetime(minutes["meeting_date"])
    override_map = overrides.set_index("occurrence_id")["history_discriminator"].to_dict()
    minutes["history_discriminator"] = minutes["occurrence_id"].map(override_map).fillna("default")
    minutes["case_history_id"] = minutes.apply(
        lambda row: make_history_id(row["case_number"], row["history_discriminator"]),
        axis=1,
    )

    duplicate_case_dates = (
        minutes.groupby(["case_number", "meeting_date"]).size().loc[lambda x: x > 1]
    )
    unresolved_collisions = []
    for case_number, meeting_date in duplicate_case_dates.index:
        collision = minutes[
            minutes["case_number"].eq(case_number)
            & minutes["meeting_date"].eq(meeting_date)
        ]
        if collision["case_history_id"].nunique() != len(collision):
            unresolved_collisions.append(
                {"case_number": case_number, "meeting_date": str(meeting_date.date())}
            )

    histories = []
    categories = []
    for history_id, group in minutes.groupby("case_history_id", sort=True):
        relief = sorted(
            set().union(*(split_labels(value) for value in group["relief_categories"]))
        )
        routes = sorted(
            set().union(*(split_labels(value) for value in group["case_routes"]))
        )
        histories.append(
            {
                "case_history_id": history_id,
                "printed_case_number": group["case_number"].iloc[0],
                "history_discriminator": group["history_discriminator"].iloc[0],
                "first_meeting_date": group["meeting_date"].min().date().isoformat(),
                "last_meeting_date": group["meeting_date"].max().date().isoformat(),
                "appearance_count": int(group["meeting_date"].nunique()),
                "occurrence_count": int(len(group)),
                "occurrence_ids": "|".join(group.sort_values("meeting_date")["occurrence_id"]),
                "meeting_dates": "|".join(
                    sorted(group["meeting_date"].dt.date.astype(str).unique())
                ),
                "petitioner": representative(group, "petitioner"),
                "location": representative(group, "location"),
                "proposal": representative(group, "proposal"),
                "relief_categories": "|".join(relief),
                "case_routes": "|".join(routes),
            }
        )
        for category in relief:
            source_rows = group[
                group["relief_categories"].fillna("").map(
                    lambda value: category in split_labels(value)
                )
            ]
            sources = sorted(set(source_rows["classification_source"].dropna()))
            evidence = []
            for value in source_rows["relief_evidence"].dropna():
                parsed = json.loads(value)
                evidence.extend(parsed.get(category, []))
            categories.append(
                {
                    "case_history_id": history_id,
                    "category": category,
                    "classification_sources": "|".join(sources),
                    "evidence": json.dumps(sorted(set(evidence)), ensure_ascii=False),
                }
            )

    histories_frame = pd.DataFrame(histories).sort_values(
        ["first_meeting_date", "printed_case_number", "case_history_id"]
    )
    categories_frame = pd.DataFrame(categories).sort_values(
        ["category", "case_history_id"]
    )
    occurrence_columns = [
        "occurrence_id", "case_history_id", "case_number", "meeting_date",
        "decision_status", "decision", "decision_basis", "source_file",
    ]
    occurrences_frame = minutes[occurrence_columns].copy()
    occurrences_frame["meeting_date"] = occurrences_frame["meeting_date"].dt.date.astype(str)

    repeated_numbers = int(
        histories_frame.groupby("printed_case_number").size().gt(1).sum()
    )
    audit = {
        "minutes_occurrences": int(len(minutes)),
        "case_histories": int(len(histories_frame)),
        "collapsed_occurrences": int(len(minutes) - len(histories_frame)),
        "histories_with_multiple_appearances": int(
            histories_frame["appearance_count"].gt(1).sum()
        ),
        "printed_numbers_with_multiple_histories": repeated_numbers,
        "override_rows_used": int(
            minutes["occurrence_id"].isin(set(overrides["occurrence_id"])).sum()
        ),
        "unresolved_same_date_number_collisions": unresolved_collisions,
    }
    return histories_frame, occurrences_frame, categories_frame, audit


def run(input_path: Path, overrides_path: Path, output_dir: Path) -> None:
    frame = pd.read_csv(input_path)
    overrides = pd.read_csv(overrides_path)
    missing = sorted(set(overrides["occurrence_id"]) - set(frame["occurrence_id"]))
    if missing:
        raise ValueError(f"Override occurrence IDs absent from corpus: {missing}")
    histories, occurrences, categories, audit = build_histories(frame, overrides)
    if audit["unresolved_same_date_number_collisions"]:
        raise ValueError(
            "Unresolved duplicate printed case numbers: "
            f"{audit['unresolved_same_date_number_collisions']}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    histories.to_csv(output_dir / "case_histories.csv", index=False)
    occurrences.to_csv(output_dir / "case_occurrences.csv", index=False)
    categories.to_csv(output_dir / "case_categories.csv", index=False)
    (output_dir / "case_history_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.input, args.overrides, args.output_dir)


if __name__ == "__main__":
    main()
