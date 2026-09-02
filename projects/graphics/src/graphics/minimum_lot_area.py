"""Residential minimum lot area."""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
PARCEL_DIR = FORUM / "parcel-geometry"
sys.path.insert(0, str(PARCEL_DIR))

from build_minimum_lot_size_asset import (  # noqa: E402
    build_graphic, classify_lot_area, select_residential_area_cases,
)
from strongtowns_graphics import (
    GraphicInput,
    MobileMapInset,
    MobileMapPocket,
    graphic_definition,
    map_on_mobile,
)


@graphic_definition(
    "minimum_lot_area",
    inputs=(
        GraphicInput("parcels", "detroit.parcels", "accepted.parquet"),
        GraphicInput("histories", "detroit.bza.gemini.raw", "raw/case_histories.csv"),
        GraphicInput("categories", "detroit.bza.gemini.raw", "raw/case_categories.csv"),
    ),
)
def build(context):
    frame = classify_lot_area(gpd.read_parquet(
        context.input("parcels"),
        columns=["parcel_id", "zoning_district", "total_square_footage",
                 "taxpayer_1", "taxpayer_2", "geometry"],
    ))
    histories = pd.read_csv(context.input("histories"))
    categories = pd.read_csv(context.input("categories"))
    cases = select_residential_area_cases(histories, categories)
    evaluated = frame[frame["evaluated"]]
    affected = int(evaluated["below_minimum"].sum())
    total = len(evaluated)
    affected_share = affected / total
    base = build_graphic(
        frame,
        cases,
        title="Detroit's Zoning Code mandates suburban lot sizes",
        subtitle=(
            "Recorded R1–R6 parcel area compared with the 5,000-square-foot minimum"
        ),
        sources=(
            "Sources: City of Detroit parcel data; Detroit BZA minutes, "
            "2019–2026; Detroit Code §§50-13-1–7, 50-13-21.",
        ),
        description=(
            f"{affected:,} of {total:,} evaluated R1 through R6 parcels are "
            "more than one percent below 5,000 square feet. "
            f"{len(cases)} BZA case histories sought residential "
            "minimum-lot-area relief."
        ),
    )
    graphic = map_on_mobile(
        base,
        insets=(
            MobileMapInset.hero_statistic(
                pocket=MobileMapPocket.LOWER_RIGHT,
                value=f"{affected_share:.0%}",
                label=(
                    "OF EVALUATED R1–R6 PARCELS",
                    "FALL BELOW DETROIT'S",
                    "MINIMUM LOT AREA",
                ),
            ),
        ),
    )
    return {"minimum-lot-area": graphic}
