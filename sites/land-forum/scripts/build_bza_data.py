#!/usr/bin/env python3
"""Build the compact public case file consumed by the Land Forum atlas."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
ROOT = SITE.parents[1]
DATA = ROOT / "pipelines/zoning/bza_dataset_gemini"
OUTPUT = SITE / "public/data/bza-cases.json"

CATEGORY_ORDER = [
    "administrative_or_community_appeal",
    "parking_supply",
    "use_spacing_separation",
    "setbacks_yards",
    "nonconforming_use_or_structure",
    "lot_coverage",
    "lot_dimensions",
    "height",
    "parking_layout",
    "screening_landscaping",
    "signs_billboards",
    "floor_area_bulk",
    "multiple_buildings",
    "open_recreation_space",
    "fences_walls",
    "loading",
]
CATEGORY_LABELS = {
    "administrative_or_community_appeal": "Administrative/community appeal",
    "parking_supply": "Parking supply",
    "use_spacing_separation": "Use spacing/separation",
    "setbacks_yards": "Setbacks/yards",
    "nonconforming_use_or_structure": "Nonconforming use/structure",
    "lot_coverage": "Lot coverage",
    "lot_dimensions": "Lot dimensions",
    "height": "Height",
    "parking_layout": "Parking layout",
    "screening_landscaping": "Screening/landscaping",
    "signs_billboards": "Signs/billboards",
    "floor_area_bulk": "Floor area/bulk",
    "multiple_buildings": "Multiple buildings",
    "open_recreation_space": "Open/recreation space",
    "fences_walls": "Fences/walls",
    "loading": "Loading",
}
OUTCOME_LABELS = {
    "granted_reversed": "Request granted",
    "denied_upheld": "Request denied",
    "dismissed_withdrawn": "Dismissed or withdrawn",
    "procedural_unresolved": "No final decision recorded",
    "mixed_or_other_decided": "Mixed or other decision",
}


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def main() -> None:
    histories = pd.read_csv(DATA / "case_histories.csv").drop_duplicates(
        "case_history_id"
    )
    applications = pd.read_csv(DATA / "atlas_applications.csv")
    sites = gpd.read_file(DATA / "map_sites.gpkg").to_crs(4326)
    sites["point"] = sites.geometry.representative_point()

    primary = {}
    priority = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    for case_id, group in applications.groupby("case_history_id"):
        categories = {
            category for category in group["category"].dropna()
            if category in CATEGORY_LABELS
        }
        primary[case_id] = (
            min(categories, key=lambda category: priority[category])
            if categories else "unspecified"
        )

    points = (
        sites.groupby("case_history_id", as_index=False)
        .agg(
            lon=("point", lambda values: sum(p.x for p in values) / len(values)),
            lat=("point", lambda values: sum(p.y for p in values) / len(values)),
            address=("address", lambda values: clean(next(iter(values), ""))),
        )
    )
    records = histories.merge(points, on="case_history_id", how="inner")
    public = []
    for row in records.itertuples(index=False):
        category = primary.get(row.case_history_id, "unspecified")
        public.append(
            {
                "id": row.case_history_id,
                "caseNumber": clean(row.printed_case_number) or "Case number unavailable",
                "address": clean(row.address) or clean(row.location) or "Location unavailable",
                "location": clean(row.location),
                "petitioner": clean(row.petitioner) or "Petitioner not recorded",
                "proposal": clean(row.proposal),
                "category": category,
                "categoryLabel": CATEGORY_LABELS.get(
                    category, "Request not specified"
                ),
                "outcome": clean(row.final_outcome),
                "outcomeLabel": OUTCOME_LABELS.get(
                    clean(row.final_outcome), "Outcome not classified"
                ),
                "firstDate": clean(row.first_meeting_date),
                "lastDate": clean(row.last_meeting_date),
                "appearances": int(row.appearance_count),
                "lat": round(float(row.lat), 6),
                "lon": round(float(row.lon), 6),
            }
        )
    OUTPUT.write_text(
        json.dumps(public, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {len(public)} cases to {OUTPUT}")


if __name__ == "__main__":
    main()
