"""Detroit BZA cases grouped by proposed use."""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import polars as pl

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
GRAPHICS = Path(__file__).resolve().parents[2]
SOURCE_DIR = FORUM / "bza-use-types"
sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(GRAPHICS))

from build_use_type_assets import (  # noqa: E402
    CLASSIFICATIONS,
    FAMILY_COLORS,
    SITES,
    selected_cases,
)
from basemap import load_detroit_basemap  # noqa: E402
from strongtowns_graphics import (
    LegendOrders,
    MapMarkerStyle,
    MobileMapInset,
    MobileMapPocket,
    categorical_proportional_symbol_map,
    graphic_definition,
)


@graphic_definition("bza_proposed_use_map")
def build():
    cases = selected_cases(pd.read_csv(CLASSIFICATIONS))
    sites = gpd.read_file(SITES).to_crs("EPSG:3857")
    categories = {
        key: (label, FAMILY_COLORS[key])
        for key, label in (
            ("housing", "Residential projects"),
            ("cannabis_or_controlled_use", "Cannabis or controlled use"),
            ("vehicle_oriented", "Vehicle sales and services"),
            ("mixed_use", "Mixed-use"),
            ("retail_or_personal_service", "Retail or personal service"),
            ("food_or_beverage", "Food or beverage"),
            ("institutional_or_civic", "Institutional or civic"),
            ("parking_only", "Parking"),
            ("industrial_or_logistics", "Industrial or logistics"),
            ("signage", "Signage"),
            ("office_or_medical", "Office or medical"),
            ("recreation_or_open_space", "Recreation or open space"),
            ("other", "Other / insufficient detail"),
            ("religious", "Religious"),
        )
    }
    case_categories = cases.set_index("case_history_id")["display_family"]
    appearance_counts = cases.set_index("case_history_id")["appearance_count"]
    located = sites[
        sites["case_history_id"].isin(cases["case_history_id"])
    ].drop_duplicates(["case_history_id", "site_id", "parcel_id"]).copy()
    located["category"] = located["case_history_id"].map(case_categories)
    located["magnitude"] = (
        located["case_history_id"].map(appearance_counts).fillna(1).astype(int)
    )
    dissolved = located.dissolve(by=["case_history_id", "category"])
    points = dissolved.geometry.representative_point()
    records = []
    for (case_id, category), point in points.items():
        label, color = categories[category]
        records.append(
            {
                "point_id": str(case_id),
                "easting": point.x,
                "northing": point.y,
                "category": category,
                "category_label": label,
                "color": color,
                "magnitude": int(dissolved.loc[(case_id, category), "magnitude"]),
                "category_count": 1,
            }
        )

    graphic = categorical_proportional_symbol_map(
        pl.DataFrame(records),
        basemap=load_detroit_basemap(),
        title="Over one quarter of Detroit's BZA cases involve residential projects",
        subtitle=(
            "Cases grouped by the project described in meeting minutes, 2019–2026"
        ),
        category_legend_heading="Proposed use",
        magnitude_legend_heading="HEARINGS PER CASE",
        category_order=LegendOrders.DESCENDING,
        marker_style=MapMarkerStyle(opacity=0.78, overlap_fraction=0.10),
        sources=(
            "Source: Detroit BZA minutes, 2019–2026; locations linked to City "
            "assessor parcels. Proposed-use labels are analytic groupings derived from the minutes. "
            "To aid legibility, locations may not represent precise addresses.",
        ),
        description=(
            f"A map of {len(records)} located Detroit BZA case histories grouped "
            "by the proposed use described in meeting minutes."
        ),
    )
    return {"bza-proposed-use-map": graphic}
