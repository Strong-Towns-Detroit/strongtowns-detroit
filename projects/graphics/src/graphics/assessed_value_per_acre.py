"""Assessed property value per acre."""

import sys
from pathlib import Path

import geopandas as gpd

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
sys.path.insert(0, str(FORUM / "assessed-value-per-acre"))

from build_assessed_value_asset import (  # noqa: E402
    PARCELS,
    build_graphic,
    classify,
    concentration,
)
from strongtowns_graphics import (
    MobileMapInset,
    MobileMapPocket,
    graphic_definition,
    map_on_mobile,
)


@graphic_definition("assessed_value_per_acre")
def build():
    frame = classify(gpd.read_file(
        PARCELS,
        columns=["parcel_id", "assessed_value", "total_square_footage", "geometry"],
    ))
    recorded = frame[frame["recorded"]]
    zero = int(recorded["assessed"].eq(0).sum())
    unknown = int((~frame["recorded"]).sum())
    share = concentration(frame)
    graphic = build_graphic(
        frame,
        title="Detroit's assessed property value per acre",
        subtitle=(
            "Total assessed land and improvement value divided by recorded "
            "parcel area"
        ),
        sources=(
            f"Coverage: {len(recorded):,} parcels with recorded area and "
            f"assessment; {zero:,} have a recorded assessment of $0; "
            f"{unknown:,} lack a usable area or assessment.",
            "Source: City of Detroit parcel assessment data downloaded in 2026.",
            "Values are nominal assessor records and have not been adjusted "
            "for exemptions or assessment-year differences.",
        ),
        description=(
            "Parcel map comparing total assessed land and improvement value "
            f"per acre. {share:.0%} of recorded assessed value is concentrated "
            "on 10 percent of recorded parcel acreage."
        ),
    )
    median = float(graphic.metadata["median_assessed_value_per_acre"])
    graphic = map_on_mobile(
        graphic,
        map_height=800,
        insets=(
            MobileMapInset.hero_statistic(
                pocket=MobileMapPocket.LOWER_RIGHT,
                value=f"${median / 1000:.0f}K",
                label=(
                    "MEDIAN ASSESSED VALUE",
                    "PER ACRE ACROSS PARCELS",
                    "WITH USABLE RECORDS",
                ),
            ),
        ),
    )
    return {"assessed-value-per-acre": graphic}
