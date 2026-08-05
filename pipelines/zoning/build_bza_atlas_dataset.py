#!/usr/bin/env python3
"""Build the one-row-per-case/category tables used by the BZA relief atlas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "bza_dataset_gemini"
DEFAULT_OUTPUT = HERE / "bza_dataset_gemini"

MIN_CASES = 10
MIN_MATCH_SHARE = 0.80

CORE_CATEGORIES = {
    "administrative_or_community_appeal",
    "parking_supply",
    "use_spacing_separation",
    "setbacks_yards",
    "nonconforming_use_or_structure",
}
DIMENSIONAL_CATEGORIES = {
    "lot_coverage",
    "lot_dimensions",
    "height",
    "open_recreation_space",
    "parking_layout",
    "floor_area_bulk",
    "screening_landscaping",
    "signs_billboards",
}
APPENDIX_CATEGORIES = {
    "multiple_buildings",
    "fences_walls",
    "loading",
}
QA_CATEGORIES = {
    "dimensional_relief_unspecified",
    "request_not_stated",
}
ANALYSIS_ONLY_CATEGORIES = {"hardship_relief"}


def atlas_tier(category: str) -> str:
    if category in CORE_CATEGORIES:
        return "core"
    if category in DIMENSIONAL_CATEGORIES:
        return "dimensional"
    if category in APPENDIX_CATEGORIES:
        return "rare_appendix"
    if category in QA_CATEGORIES:
        return "qa_only"
    if category in ANALYSIS_ONLY_CATEGORIES:
        return "analysis_only"
    return "unassigned"


def build_tables(
    histories: pd.DataFrame,
    categories: pd.DataFrame,
    sites: gpd.GeoDataFrame,
) -> tuple[pd.DataFrame, gpd.GeoDataFrame, pd.DataFrame, dict]:
    histories = histories.drop_duplicates("case_history_id").copy()
    categories = categories.drop_duplicates(["case_history_id", "category"]).copy()

    applications = categories.merge(
        histories,
        on="case_history_id",
        how="left",
        validate="many_to_one",
    )
    missing_histories = applications["printed_case_number"].isna()
    if missing_histories.any():
        ids = applications.loc[missing_histories, "case_history_id"].tolist()
        raise ValueError(f"Categories without case histories: {ids[:5]}")

    sites = sites.drop_duplicates(
        ["case_history_id", "site_id", "parcel_id"]
    ).copy()
    mapped_ids = set(sites["case_history_id"])
    applications["mapped"] = applications["case_history_id"].isin(mapped_ids)
    applications["atlas_tier"] = applications["category"].map(atlas_tier)

    grouped = applications.groupby("category", sort=False)
    summary = grouped.agg(
        case_histories=("case_history_id", "nunique"),
        mapped_case_histories=("mapped", "sum"),
    ).reset_index()
    summary["match_share"] = (
        summary["mapped_case_histories"] / summary["case_histories"]
    )
    summary["atlas_tier"] = summary["category"].map(atlas_tier)
    summary["meets_count_gate"] = summary["case_histories"].ge(MIN_CASES)
    summary["meets_match_gate"] = summary["match_share"].ge(MIN_MATCH_SHARE)
    summary["publication_eligible"] = (
        summary["meets_count_gate"]
        & summary["meets_match_gate"]
        & ~summary["atlas_tier"].isin(["qa_only", "analysis_only", "unassigned"])
    )
    summary["gate_reason"] = summary.apply(gate_reason, axis=1)
    tier_order = {
        "core": 0,
        "dimensional": 1,
        "rare_appendix": 2,
        "analysis_only": 3,
        "qa_only": 4,
        "unassigned": 5,
    }
    summary["_tier_order"] = summary["atlas_tier"].map(tier_order)
    summary = summary.sort_values(
        ["_tier_order", "case_histories", "category"],
        ascending=[True, False, True],
    ).drop(columns="_tier_order")

    site_columns = [
        "case_history_id", "site_id", "site_key", "parcel_id", "address",
        "match_method", "geometry",
    ]
    mapped = sites[site_columns].merge(
        applications,
        on="case_history_id",
        how="inner",
        validate="many_to_many",
    )
    mapped = gpd.GeoDataFrame(mapped, geometry="geometry", crs=sites.crs)

    audit = {
        "case_histories": int(histories["case_history_id"].nunique()),
        "categorized_case_histories": int(
            applications["case_history_id"].nunique()
        ),
        "category_assignments": int(len(applications)),
        "mapped_category_assignments": int(applications["mapped"].sum()),
        "publication_gate": {
            "minimum_case_histories": MIN_CASES,
            "minimum_match_share": MIN_MATCH_SHARE,
        },
        "eligible_categories": summary.loc[
            summary["publication_eligible"], "category"
        ].tolist(),
        "ineligible_categories": summary.loc[
            ~summary["publication_eligible"], "category"
        ].tolist(),
    }
    return applications, mapped, summary, audit


def gate_reason(row: pd.Series) -> str:
    if row["atlas_tier"] == "qa_only":
        return "quality-assurance category"
    if row["atlas_tier"] == "analysis_only":
        return "analytical tag, not a relief geometry"
    if row["atlas_tier"] == "unassigned":
        return "category has no atlas tier"
    failures = []
    if not row["meets_count_gate"]:
        failures.append(f"fewer than {MIN_CASES} histories")
    if not row["meets_match_gate"]:
        failures.append(f"less than {MIN_MATCH_SHARE:.0%} mapped")
    return "; ".join(failures) if failures else "eligible"


def run(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    histories = pd.read_csv(input_dir / "case_histories.csv")
    categories = pd.read_csv(input_dir / "case_categories.csv")
    sites = gpd.read_file(input_dir / "map_sites.gpkg")
    applications, mapped, summary, audit = build_tables(
        histories, categories, sites
    )
    applications.to_csv(output_dir / "atlas_applications.csv", index=False)
    mapped.to_file(output_dir / "atlas_category_sites.gpkg", driver="GPKG")
    summary.to_csv(output_dir / "atlas_category_summary.csv", index=False)
    (output_dir / "atlas_dataset_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False))
    print(json.dumps(audit, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
