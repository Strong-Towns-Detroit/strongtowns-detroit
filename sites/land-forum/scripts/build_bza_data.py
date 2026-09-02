#!/usr/bin/env python3
"""Build the compact public case file consumed by the Land Forum atlas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from strongtowns_detroit.repositories import data_repository

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
ROOT = SITE.parents[1]
DATA_REPOSITORY = data_repository()
DATA = DATA_REPOSITORY / "pipelines/zoning/bza_dataset_gemini"
OUTPUT = SITE / "public/data/bza-cases.json"
MAP_OUTPUT = SITE / "public/data/bza-map.json"
CONTEXT_OUTPUT = SITE / "public/data/detroit-context.geojson"
ROADS = (
    ROOT / "projects/detroit-land-use-forum/spirit-plaza-accessibility"
    / "output/road_context.geojson"
)
CITY_BOUNDARY = (
    DATA_REPOSITORY / "pipelines/housingDataAnalysis/street_simplification"
    / "output/detroit_boundary.geojson"
)
ATLAS_CODE = (
    ROOT / "projects/detroit-land-use-forum/bza-relief-atlas"
)
sys.path.insert(0, str(ATLAS_CODE))
from build_atlas import (  # noqa: E402
    primary_relief_categories,
)

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
    occurrences = pd.read_csv(DATA / "case_occurrences.csv").fillna("")
    applications = pd.read_csv(DATA / "atlas_applications.csv")
    sites = gpd.read_file(DATA / "map_sites.gpkg").to_crs(4326)
    sites["point"] = sites.geometry.representative_point()

    primary = primary_relief_categories(applications)

    points = (
        sites.groupby("case_history_id", as_index=False)
        .agg(
            lon=("point", lambda values: sum(p.x for p in values) / len(values)),
            lat=("point", lambda values: sum(p.y for p in values) / len(values)),
            address=("address", lambda values: clean(next(iter(values), ""))),
        )
    )
    records = histories.merge(points, on="case_history_id", how="inner")
    hearings_by_case = {}
    for case_id, group in occurrences.groupby("case_history_id"):
        hearings_by_case[case_id] = [
            {
                "date": clean(row.meeting_date),
                "status": clean(row.decision_status),
                "decision": clean(row.decision),
                "file": clean(row.source_file),
            }
            for row in group.sort_values("meeting_date").itertuples(index=False)
        ]
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
                "hearings": hearings_by_case.get(row.case_history_id, []),
                "lat": round(float(row.lat), 6),
                "lon": round(float(row.lon), 6),
            }
        )
    OUTPUT.write_text(
        json.dumps(public, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    build_map_assets(histories, sites.to_crs(3857), primary)
    print(f"Wrote {len(public)} cases to {OUTPUT}")


def build_map_assets(
    histories: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    primary: dict[str, str | None],
) -> None:
    """Export the atlas context and true locations of appearance-sized sites."""
    sites = sites.drop_duplicates(
        ["case_history_id", "site_id", "parcel_id"]
    ).copy()
    case_values = histories.set_index("case_history_id")["appearance_count"]
    sites["primary_category"] = (
        sites["case_history_id"].map(primary).fillna("unspecified")
    )
    sites["appearance_count"] = (
        sites["case_history_id"].map(case_values).fillna(1).astype(int)
    )

    case_keys = list(
        sites[["case_history_id", "primary_category"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    parent = {key: key for key in case_keys}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        keep, merge = sorted([left_root, right_root], key=str)
        parent[merge] = keep

    for identity_column in ["site_id", "parcel_id"]:
        identities = sites.dropna(subset=[identity_column])
        for (_, category), group in identities.groupby(
            [identity_column, "primary_category"]
        ):
            keys = [
                (case_id, category)
                for case_id in group["case_history_id"].unique()
            ]
            for key in keys[1:]:
                union(keys[0], key)

    sites["project_group"] = [
        find((case_id, category))[0]
        for case_id, category in zip(
            sites["case_history_id"], sites["primary_category"]
        )
    ]
    case_sites = sites.drop_duplicates(
        ["case_history_id", "project_group", "primary_category"]
    )
    aggregate = (
        case_sites.groupby(["project_group", "primary_category"])
        .agg(
            appearances=("appearance_count", "sum"),
            case_ids=("case_history_id", lambda values: sorted(set(values))),
        )
    )
    dissolved = sites.dissolve(by=["project_group", "primary_category"])
    dissolved = dissolved.join(aggregate)
    true_points = gpd.GeoSeries(
        dissolved.geometry.representative_point(), crs=3857
    ).to_crs(4326)
    map_records = []
    for index, ((project_group, category), row) in enumerate(
        dissolved.iterrows()
    ):
        point = true_points.iloc[index]
        map_records.append(
            {
                "id": f"{project_group}:{category}",
                "category": category,
                "categoryLabel": CATEGORY_LABELS.get(
                    category, "Request not specified"
                ),
                "appearances": int(row["appearances"]),
                "caseIds": row["case_ids"],
                "lat": round(point.y, 6),
                "lon": round(point.x, 6),
            }
        )
    MAP_OUTPUT.write_text(
        json.dumps(map_records, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    roads = gpd.read_file(ROADS).to_crs(3857)
    major = roads[roads["road_class"].isin(["major", "arterial"])].copy()
    city_simple = (
        gpd.read_file(CITY_BOUNDARY)
        .to_crs(3857)
        .geometry.iloc[0]
        .simplify(35, preserve_topology=True)
    )
    city_simple = gpd.GeoSeries([city_simple], crs=3857).to_crs(4326).iloc[0]
    road_features = []
    for row in major.itertuples(index=False):
        geometry = row.geometry.simplify(35, preserve_topology=True)
        geometry = gpd.GeoSeries([geometry], crs=3857).to_crs(4326).iloc[0]
        road_features.append(
            {
                "type": "Feature",
                "properties": {
                    "roadClass": row.road_class,
                    "roadWidthM": float(row.road_width_m),
                    "widthSource": row.width_source,
                },
                "geometry": mapping(geometry),
            }
        )
    context = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"kind": "city"},
                "geometry": mapping(city_simple),
            },
            *road_features,
        ],
    }
    CONTEXT_OUTPUT.write_text(
        json.dumps(context, separators=(",", ":")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
