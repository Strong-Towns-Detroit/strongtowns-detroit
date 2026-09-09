#!/usr/bin/env python3
"""Build the compact public case file consumed by the Land Forum atlas."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from atlas_inputs import resolve_inputs

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
ROOT = SITE.parents[1]
ATLAS_CODE = (
    ROOT / "projects/detroit-land-use-forum/bza-relief-atlas"
)
sys.path.insert(0, str(ATLAS_CODE))

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


def source_url(value):
    from urllib.parse import urlsplit
    text = clean(value)
    try:
        parsed = urlsplit(text)
        return text if parsed.scheme in {"https", "http"} and parsed.netloc else None
    except ValueError:
        return None


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=ROOT / "strongtowns-data.lock.json")
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--output", type=Path, default=SITE / "public/data")
    parser.add_argument("--check", action="store_true", help="Verify pinned inputs without writing output.")
    parser.add_argument("--studio-only", action="store_true", help="Publish the all-case studio bundle without replacing atlas assets.")
    args = parser.parse_args(argv)
    inputs, metadata = resolve_inputs(args.lock, args.repository)
    if args.check:
        print(json.dumps({"ready": True, "inputs": metadata}, indent=2))
        return
    build(inputs, metadata, args.output, studio_only=args.studio_only)


def build(inputs, metadata, output, studio_only=False):
    from build_atlas import primary_relief_categories, CATEGORY_LABELS as primary_labels
    output.mkdir(parents=True, exist_ok=True)
    OUTPUT = output / "bza-cases.json"
    histories = pd.read_csv(inputs["histories"]).drop_duplicates(
        "case_history_id"
    )
    occurrences = pd.read_csv(inputs["occurrences"]).fillna("")
    applications = pd.read_csv(inputs["applications"])
    sites = gpd.read_file(inputs["sites"]).to_crs(4326)
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
    records = histories.merge(points, on="case_history_id", how="left", validate="one_to_one")
    hearings_by_case = {}
    for case_id, group in occurrences.groupby("case_history_id"):
        hearings_by_case[case_id] = [
            {
                "date": clean(row.meeting_date),
                "status": clean(row.decision_status),
                "decision": clean(row.decision),
                "file": clean(row.source_file),
                "sourceUrl": source_url(getattr(row, "source_url", "")),
            }
            for row in group.sort_values("meeting_date").itertuples(index=False)
        ]
    public = []
    for row in records.itertuples(index=False):
        category = primary.get(row.case_history_id) or "unspecified"
        public.append(
            {
                "id": row.case_history_id,
                "caseNumber": clean(row.printed_case_number) or "Case number unavailable",
                "address": clean(row.address) or clean(row.location) or "Location unavailable",
                "location": clean(row.location),
                "petitioner": clean(row.petitioner) or "Petitioner not recorded",
                "proposal": clean(row.proposal),
                "category": category,
                "categoryLabel": primary_labels.get(
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
                "lat": round(float(row.lat), 6) if pd.notna(row.lat) else None,
                "lon": round(float(row.lon), 6) if pd.notna(row.lon) else None,
            }
        )
    write_studio_bundle(public, metadata, output, primary_labels)
    if studio_only:
        return
    mapped = [row for row in public if row["lat"] is not None and row["lon"] is not None]
    OUTPUT.write_text(
        json.dumps(mapped, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    build_map_assets(histories, sites.to_crs(3857), primary, inputs, output, primary_labels)
    (output / "bza-provenance.json").write_text(json.dumps({"inputs": metadata}, indent=2) + "\n")
    print(f"Wrote {len(mapped)} cases to {OUTPUT}")


def write_studio_bundle(records, metadata, output, category_labels=None):
    """Consumer publication derived only from pinned histories, never new classifications."""
    from collections import Counter
    from datetime import date

    def valid_date(value):
        try:
            return date.fromisoformat(value).isoformat() == value
        except (ValueError, TypeError):
            return False

    category_labels = CATEGORY_LABELS if category_labels is None else category_labels
    cases = []
    for record in sorted(records, key=lambda row: row["id"]):
        row = {key: value for key, value in record.items() if key not in {"lat", "lon", "appearances"}}
        row["mapped"] = record["lat"] is not None and record["lon"] is not None
        if row["category"] not in category_labels:
            row["category"] = "unspecified"
            row["categoryLabel"] = "Request not specified"
        else:
            row["categoryLabel"] = category_labels[row["category"]]
        if row["outcome"] not in OUTCOME_LABELS:
            row["outcome"] = "unclassified"
            row["outcomeLabel"] = "Outcome not classified"
        cases.append(row)
    dates = sorted({value for row in cases for value in [row["firstDate"], row["lastDate"], *[h["date"] for h in row["hearings"]]] if valid_date(value)})
    bundle = {"version": 1, "cases": cases, "coverage": {"firstDate": dates[0] if dates else "", "lastDate": dates[-1] if dates else ""}, "inputs": metadata}
    payload = (json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    identifier = hashlib.sha256(payload).hexdigest()
    destination = output / "bza-studio"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{identifier}.json"
    if target.exists() and target.read_bytes() != payload:
        raise ValueError("Existing content-addressed publication is corrupt; restore it before publishing.")
    target.write_bytes(payload)
    (destination / "latest.json").write_text(json.dumps({"version": 1, "bundle": identifier}) + "\n")
    mapped = [row for row in cases if row["mapped"]]
    previous = json.loads((output / "bza-cases.json").read_text()) if (output / "bza-cases.json").exists() else []
    counts = lambda rows, key: dict(sorted(Counter(row[key] for row in rows).items()))
    comparison = {"bundle": identifier, "allCases": len(cases), "mappedCases": len(mapped), "unmappedCases": len(cases) - len(mapped), "undatedCases": sum(not valid_date(row["firstDate"]) for row in cases), "previousAtlasCases": len(previous), "allCategories": counts(cases, "categoryLabel"), "mappedCategories": counts(mapped, "categoryLabel"), "previousAtlasCategories": counts(previous, "categoryLabel"), "allOutcomes": counts(cases, "outcomeLabel"), "mappedOutcomes": counts(mapped, "outcomeLabel"), "previousAtlasOutcomes": counts(previous, "outcomeLabel"), "mappedIdsAdded": sorted({row["id"] for row in mapped} - {row["id"] for row in previous}), "mappedIdsRemoved": sorted({row["id"] for row in previous} - {row["id"] for row in mapped})}
    (destination / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(f"Studio: {len(cases)} cases ({len(mapped)} mapped), bundle {identifier}")


def build_map_assets(
    histories: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    primary: dict[str, str | None],
    inputs: dict[str, Path],
    output: Path,
    category_labels=None,
) -> None:
    """Export the atlas context and true locations of appearance-sized sites."""
    category_labels = CATEGORY_LABELS if category_labels is None else category_labels
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
                "categoryLabel": category_labels.get(
                    category, "Request not specified"
                ),
                "appearances": int(row["appearances"]),
                "caseIds": row["case_ids"],
                "lat": round(point.y, 6),
                "lon": round(point.x, 6),
            }
        )
    (output / "bza-map.json").write_text(
        json.dumps(map_records, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    roads = gpd.read_file(inputs["roads"]).to_crs(3857)
    major = roads[roads["road_class"].isin(["major", "arterial"])].copy()
    city_simple = (
        gpd.read_file(inputs["boundary"])
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
    (output / "detroit-context.geojson").write_text(
        json.dumps(context, separators=(",", ":")),
        encoding="utf-8",
    )




if __name__ == "__main__":
    main()
