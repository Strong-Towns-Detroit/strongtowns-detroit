"""Residential setback-envelope compliance."""

import sys
from pathlib import Path

import pandas as pd
import geopandas as gpd

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
PARCEL_DIR = FORUM / "parcel-geometry"
sys.path.insert(0, str(PARCEL_DIR))

from build_residential_setback_asset import (  # noqa: E402
    build_graphic,
    select_house_setback_cases,
)
from strongtowns_graphics import GraphicInput, graphic_definition, map_on_mobile


@graphic_definition(
    "residential_setback_envelope",
    inputs=(
        GraphicInput(
            "classification",
            "detroit.residential-setback-envelope",
            "classification.parquet",
        ),
        GraphicInput("histories", "detroit.bza.gemini.raw", "raw/case_histories.csv"),
        GraphicInput("categories", "detroit.bza.gemini.raw", "raw/case_categories.csv"),
        GraphicInput("roads", "detroit.base-units.streets.raw", "raw.geojson"),
    ),
)
def build(context):
    frame = gpd.read_parquet(context.input("classification"))
    histories = pd.read_csv(context.input("histories"))
    categories = pd.read_csv(context.input("categories"))
    cases = select_house_setback_cases(histories, categories)
    evaluated = frame[frame["evaluated"]]
    affected = int(evaluated["crosses_envelope"].sum())
    total = len(evaluated)
    within = total - affected
    unknown = int((frame["in_scope"] & ~frame["evaluated"]).sum())
    other = int((~frame["in_scope"]).sum())
    candidate = int(
        (frame["in_scope"] & frame["candidate_multi_parcel_site"]).sum()
    )
    base = build_graphic(
        frame,
        cases,
        categories,
        roads_path=context.input("roads"),
        title="Detroit’s single- and two-family setback envelope",
        subtitle=(
            "Existing homes compared with Detroit’s required front, rear, "
            "and side yards"
        ),
        sources=(
            f"Ordinary rectangular lots only; {candidate:,} sites without one "
            "clear principal building are not evaluated. Front edges use City "
            "Base Units street links.",
            "Crossing requires more than 10 sq. ft. or 1% of the footprint "
            "outside both permissible side-yard allocations. Result: "
            f"{affected:,} cross · {within:,} within · {unknown:,} not "
            f"evaluated · {other:,} other type.",
        ),
        description=(
            f"{affected:,} of {total:,} evaluated single- and two-family "
            "principal building footprints extend outside the ordinary current "
            "setback envelope."
        ),
    )
    graphic = map_on_mobile(base)
    return {"residential-setback-envelope": graphic}
