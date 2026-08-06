#!/usr/bin/env python3
"""Classify Detroit BZA cases by requested relief using auditable text rules."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "bza_dataset_gemini/all_cases.csv"
DEFAULT_OUTPUT = HERE / "bza_dataset_gemini"

# Categories are multi-label. Patterns target the requested waiver or appeal,
# not merely the proposed land use. Every match is retained as evidence.
RELIEF_RULES: dict[str, list[str]] = {
    "lot_dimensions": [
        r"\b(?:deficient|minimum|insufficient|excessive)\s+lot\s+(?:area|size|width|square footage)\b",
        r"\blot\s+(?:area|size|width)\s+(?:variance|waiver|required|proposed)\b",
    ],
    "setbacks_yards": [
        r"\bdeficient\s+(?:front|rear|side)?\s*(?:yard\s+)?set\s?back\b",
        r"\b(?:front|rear|side)\s+(?:yard\s+)?set\s?back\s+(?:variance|required|proposed|deficien)",
        r"\bdeficient\s+(?:front|rear|side)\s+yard\b",
    ],
    "lot_coverage": [
        r"\b(?:excessive|maximum)\s+lot coverage\b",
        r"\blot coverage\s+(?:variance|waiver|required|allowed|proposed|maximum)\b",
    ],
    "parking_supply": [
        r"\bparking variance\b",
        r"\bdeficient\s+(?:off[- ]street[- ]?)?parking\b",
        r"\b(?:off[- ]street\s+)?parking\s+(?:spaces?\s+)?(?:required|variance|waiver)\b",
        r"\bwaiv\w*\s+(?:the\s+)?(?:required\s+)?parking\b",
    ],
    "parking_layout": [
        r"\b(?:excessive|maximum|deficient)\s+parking lot (?:size|distance|setback)\b",
        r"\bdeficient\s+(?:parking\s+)?aisle width\b",
        r"\bparking\s+(?:location|layout|maneuvering|access|setback)\s+(?:variance|waiver|required|proposed)\b",
        r"\bparking (?:area|lot) (?:in|within) (?:the )?(?:front|side|rear) yard\b",
        r"\b(?:insufficient|deficient)\s+stacking space\b",
    ],
    "height": [
        r"\b(?:excessive|maximum|deficient)\s+(?:building|structure|sign|fence|wall|container)?\s*height\b",
        r"\bheight\s+(?:variance|waiver|required|allowed|proposed)\b",
    ],
    "floor_area_bulk": [
        r"\b(?:excessive|maximum|deficient)\s+(?:floor area ratio|building footprint|bulk)\b",
        r"\b(?:floor area ratio|building footprint|bulk)\s+(?:variance|waiver|required|proposed)\b",
    ],
    "density_units": [
        r"\b(?:excessive|maximum)\s+(?:residential\s+)?density\b",
        r"\bdensity\s+(?:variance|waiver|required|allowed|proposed)\b",
        r"\b(?:excessive|maximum)\s+(?:number of\s+)?dwelling units\b",
    ],
    "open_recreation_space": [
        r"\bdeficient\s+(?:recreational|open)\s+space\b",
        r"\b(?:recreational|open)\s+space\s+(?:variance|waiver|required|proposed|ratio)\b",
    ],
    "screening_landscaping": [
        r"\bdeficient\s+(?:residential|right[- ]of[- ]way|parking|landscape)?\s*screen(?:ing)?\b",
        r"\b(?:screening|landscaping|opacity)\s+(?:variance|waiver|required|deficien|proposed)\b",
        r"\bdeficient\s+(?:landscaping|opacity)\b",
    ],
    "loading": [
        r"\bdeficient\s+(?:off[- ]street\s+)?loading\b",
        r"\bloading\s+(?:spaces?|berths?)?\s*(?:variance|waiver|required|proposed)\b",
    ],
    "signs_billboards": [
        r"\b(?:sign|billboard)\s+(?:variance|waiver|appeal)\b",
        r"\bnonconforming billboard\b",
        r"\b(?:excessive|deficient)\s+(?:sign|billboard|electronic message board)\b",
        r"\b(?:add|erect|replace|establish).{0,60}\b(?:sign|billboard)\b",
        r"^(?:(?:roof|advertising|identification)\s+)?sign$",
        r"^billboard$",
    ],
    "fences_walls": [
        r"\b(?:fence|wall)\s+(?:variance|waiver|required|proposed)\b",
        r"\b(?:excessive|deficient)\s+(?:fence|wall)\b",
    ],
    "multiple_buildings": [
        r"\bmore than one principal (?:detached )?(?:residential )?building\b",
        r"\bexcessive number of principal (?:detached )?(?:residential )?buildings\b",
        r"\bnumber of (?:principal )?buildings\s+(?:variance|waiver|required|maximum)\b",
    ],
    "use_spacing_separation": [
        r"\b(?:dimensional\s+)?spacing variance\b",
        r"\bvariance of spacing regulation\b",
        r"\b(?:drug[- ]free zone|within \d[\d,]{2,} (?:radial )?feet|minimum spacing|separation distance)\b",
    ],
    "nonconforming_use_or_structure": [
        r"\b(?:expand|expansion|intensif\w*|change|re[- ]establish|establish).{0,80}\bnonconforming\b",
        r"\bnonconforming (?:use|structure|building|billboard)\b",
        r"\bnonconforming\s+(?:restaurant|retail|store|garage|marina|café|cafe)\b",
    ],
    "hardship_relief": [r"\bhardship relief\b"],
    "administrative_or_community_appeal": [
        r"\bappeals? (?:the |a )?(?:decision|determination|approval|denial)\b",
        r"\bappeals?.{0,100}\b(?:decision|determination|approval|denial)\b",
        r"\brequests? (?:to )?(?:reverse|review) .{0,60}\b(?:decision|denial|approval)\b",
        r"\breversal of (?:the )?(?:decision|denial|approval)\b",
        r"\bcommunity appeal\b",
        r"\b(?:reverse|affirm|uphold) (?:the )?bseed\b",
    ],
}

ROUTE_RULES: dict[str, list[str]] = {
    "dimensional_variance": [r"\bdimensional variance", r"\bdimensional waiver"],
    "administrative_appeal": [
        r"\bappeals? (?:the |a )?(?:decision|determination|approval|denial)\b",
        r"\bappeals?.{0,100}\b(?:decision|determination|approval|denial)\b",
        r"\brequests? (?:to )?(?:reverse|review) .{0,60}\b(?:decision|denial|approval)\b",
        r"\breversal of (?:the )?(?:decision|denial|approval)\b",
        r"\bcommunity appeal\b",
    ],
    "use_or_spacing_variance": [
        r"\bspacing variance\b", r"\bvariance of spacing regulation\b",
        r"\buse variance\b",
    ],
    "nonconforming_review": [r"\bnonconforming (?:use|structure|building|billboard)\b"],
    "hardship_petition": [r"\bhardship relief\b"],
}

BOILERPLATE = [
    r"the board (?:of zoning appeals )?shall be authorized to hear dimensional variance requests "
    r"for matters that are beyond the scope of .*?(?:administrative adjustments?)[,;:]?",
    r"for a variance of the minimum setbacks?[.;:]?",
    r"\bsections? 50-\d[^.;)]*[.;)]?",
    r"\bap\s*$",
]


def normalize_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = re.sub(r"\s+", " ", text.lower()).strip()
    for pattern in BOILERPLATE:
        text = re.sub(pattern, " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def basic_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    return re.sub(r"\s+", " ", text.lower()).strip()


def classify(text: str, rules: dict[str, list[str]]) -> tuple[list[str], dict[str, list[str]]]:
    labels: list[str] = []
    evidence: dict[str, list[str]] = {}
    for label, patterns in rules.items():
        matches: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                phrase = re.sub(r"\s+", " ", match.group(0)).strip()
                if phrase not in matches:
                    matches.append(phrase)
        if matches:
            labels.append(label)
            evidence[label] = matches
    return labels, evidence


def run(input_path: Path, output_dir: Path) -> None:
    frame = pd.read_csv(input_path)
    frame["source_text"] = frame.apply(
        lambda row: basic_text(
            row.get("proposal")
            if not pd.isna(row.get("proposal"))
            else row.get("action")
        ),
        axis=1,
    )
    frame["classification_text"] = frame["source_text"].map(normalize_text)
    relief, relief_evidence, routes, route_evidence = [], [], [], []
    for text, source_text in zip(frame["classification_text"], frame["source_text"]):
        labels, evidence = classify(text, RELIEF_RULES)
        route_labels, route_matches = classify(source_text, ROUTE_RULES)
        relief.append("|".join(labels))
        relief_evidence.append(json.dumps(evidence, ensure_ascii=False))
        routes.append("|".join(route_labels))
        route_evidence.append(json.dumps(route_matches, ensure_ascii=False))
    frame["relief_categories"] = relief
    frame["relief_evidence"] = relief_evidence
    frame["case_routes"] = routes
    frame["route_evidence"] = route_evidence
    frame["relief_category_count"] = frame["relief_categories"].map(
        lambda value: 0 if not value else len(value.split("|"))
    )
    frame["classification_source"] = "direct"

    # A later postponement or dismissal often omits the underlying proposal.
    # Inherit classifications from another occurrence of the same printed case
    # number, except case numbers proven ambiguous by appearing twice on one
    # meeting date (the corpus contains one such printed-number collision).
    ambiguous_numbers = set(
        frame.groupby(["case_number", "meeting_date"]).size().loc[lambda x: x > 1]
        .reset_index()["case_number"]
    )
    for case_number, indexes in frame.groupby("case_number").groups.items():
        if case_number in ambiguous_numbers:
            continue
        group = frame.loc[indexes]
        relief_union = sorted({
            label for value in group["relief_categories"] for label in value.split("|") if label
        })
        route_union = sorted({
            label for value in group["case_routes"] for label in value.split("|") if label
        })
        for index in indexes:
            inherited = False
            if not frame.at[index, "relief_categories"] and relief_union:
                frame.at[index, "relief_categories"] = "|".join(relief_union)
                inherited = True
            if not frame.at[index, "case_routes"] and route_union:
                frame.at[index, "case_routes"] = "|".join(route_union)
                inherited = True
            if inherited:
                frame.at[index, "classification_source"] = "inherited_case_history"
    empty = frame["relief_categories"].eq("") & frame["case_routes"].eq("")
    dimensional_unspecified = (
        frame["relief_categories"].eq("")
        & frame["case_routes"].str.contains("dimensional_variance", regex=False)
    )
    frame.loc[dimensional_unspecified, "relief_categories"] = (
        "dimensional_relief_unspecified"
    )
    frame.loc[dimensional_unspecified, "classification_source"] = "route_only"
    empty = frame["relief_categories"].eq("") & frame["case_routes"].eq("")
    frame.loc[empty, "relief_categories"] = "request_not_stated"
    frame.loc[empty, "classification_source"] = "not_stated"
    frame["relief_category_count"] = frame["relief_categories"].map(
        lambda value: 0 if not value else len(value.split("|"))
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "classified_cases.csv", index=False)
    frame.to_json(
        output_dir / "classified_cases.json", orient="records", indent=2, force_ascii=False
    )

    minutes = frame[frame["record_type"].eq("minutes_case")]
    category_counts = Counter(
        label
        for labels in minutes["relief_categories"]
        for label in labels.split("|")
        if label
    )
    route_counts = Counter(
        label
        for labels in minutes["case_routes"]
        for label in labels.split("|")
        if label
    )
    summary_rows = [
        {"classification": label, "cases": count, "kind": "relief"}
        for label, count in category_counts.most_common()
    ] + [
        {"classification": label, "cases": count, "kind": "route"}
        for label, count in route_counts.most_common()
    ]
    pd.DataFrame(summary_rows).to_csv(output_dir / "classification_summary.csv", index=False)

    not_stated = minutes["relief_categories"].eq("request_not_stated")
    unspecified = minutes["relief_categories"].eq("dimensional_relief_unspecified")
    audit = {
        "minutes_cases": int(len(minutes)),
        "with_specific_relief_category": int((~not_stated & ~unspecified).sum()),
        "dimensional_relief_unspecified": int(unspecified.sum()),
        "with_case_route": int(minutes["case_routes"].ne("").sum()),
        "request_not_stated": int(not_stated.sum()),
        "multi_relief": int(minutes["relief_category_count"].gt(1).sum()),
        "relief_counts": dict(category_counts.most_common()),
        "route_counts": dict(route_counts.most_common()),
        "request_not_stated_occurrence_ids": minutes.loc[
            not_stated, "occurrence_id"
        ].tolist(),
    }
    (output_dir / "classification_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.input, args.output_dir)


if __name__ == "__main__":
    main()
