"""Residential setback-envelope compliance."""

import sys
from pathlib import Path

import pandas as pd

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
PARCEL_DIR = FORUM / "parcel-geometry"
sys.path.insert(0, str(PARCEL_DIR))

from build_residential_setback_asset import (  # noqa: E402
    BZA,
    MERGED_RESULTS,
    build_graphic,
    load_and_classify,
    load_merged_classification,
    select_house_setback_cases,
)
from strongtowns_detroit.graphics import graphic_definition, map_on_mobile


@graphic_definition("residential_setback_envelope")
def build():
    frame = (
        load_merged_classification()
        if MERGED_RESULTS.exists()
        else load_and_classify(building_types=("single_family", "two_family"))
    )
    histories = pd.read_csv(BZA / "case_histories.csv")
    categories = pd.read_csv(BZA / "case_categories.csv")
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
