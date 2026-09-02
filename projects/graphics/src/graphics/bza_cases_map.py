"""Detroit BZA relief cases map."""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import polars as pl

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
GRAPHICS = Path(__file__).resolve().parents[2]
SOURCE_DIR = FORUM / "bza-relief-atlas"
sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(GRAPHICS))

from build_atlas import (  # noqa: E402
    CATEGORY_COLOR_MAP,
    MUTED,
    primary_relief_categories,
)
from basemap import load_detroit_basemap  # noqa: E402
from strongtowns_graphics import (
    GraphicInput,
    LegendOrders,
    MapMarkerStyle,
    categorical_proportional_symbol_map,
    graphic_definition,
)


@graphic_definition(
    "bza_cases_map",
    inputs=(
        GraphicInput("applications", "detroit.bza.gemini.raw", "raw/atlas_applications.csv"),
        GraphicInput("histories", "detroit.bza.gemini.raw", "raw/case_histories.csv"),
        GraphicInput("sites", "detroit.bza.gemini.raw", "raw/map_sites.gpkg"),
        GraphicInput("boundary", "detroit.osm.basemap.raw", "detroit_boundary.geojson"),
        GraphicInput("water", "detroit.osm.basemap.raw", "detroit_water.geojson"),
        GraphicInput("roads", "detroit.base-units.streets.raw", "raw.geojson"),
    ),
)
def build(context):
    applications = pd.read_csv(context.input("applications"))
    histories = pd.read_csv(context.input("histories"))
    sites = gpd.read_file(context.input("sites")).to_crs("EPSG:3857")
    primary = primary_relief_categories(applications)
    categories = {
        key: (label, CATEGORY_COLOR_MAP[key])
        for key, label in (
            ("administrative_or_community_appeal", "Administrative/community appeal"),
            ("parking", "Parking"),
            ("nonconforming_use_or_structure", "Nonconforming use/structure"),
            ("lot_coverage", "Lot coverage"),
            ("setbacks_yards", "Setbacks/yards"),
            ("use_spacing_separation", "Use spacing/separation"),
            ("lot_dimensions", "Lot dimensions"),
            ("height", "Height"),
            ("hardship_relief", "Hardship"),
            ("floor_area_bulk", "Floor area/bulk"),
            ("multiple_buildings", "Multiple buildings"),
            ("signs_billboards", "Signs/billboards"),
            ("open_recreation_space", "Open/recreation space"),
            ("screening_landscaping", "Screening/landscaping"),
            ("fences_walls", "Fences/walls"),
            ("building_design_standards", "Building design standards"),
            ("loading", "Loading"),
            ("density_units", "Density/unit count"),
        )
    }
    categories["unspecified"] = ("Request not specified", MUTED)
    appearance_counts = histories.set_index("case_history_id")["appearance_count"]
    located = sites.drop_duplicates(
        ["case_history_id", "site_id", "parcel_id"]
    ).copy()
    located["category"] = located["case_history_id"].map(primary).fillna("unspecified")
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
        basemap=load_detroit_basemap(
            context.input("boundary"), context.input("roads"), context.input("water")
        ),
        title="Detroit Board of Zoning Appeals cases by relief requested",
        subtitle="Cases by primary request recorded in meeting minutes, 2019–2026",
        category_legend_heading="Type of request",
        magnitude_legend_heading="HEARINGS PER CASE",
        category_order=LegendOrders.DESCENDING,
        marker_style=MapMarkerStyle(opacity=0.78, overlap_fraction=0.10),
        sources=(
            "Source: Detroit BZA minutes, 2019–2026; locations linked to City "
            "assessor parcels. Color shows the primary request type per case. "
            "To aid legibility, locations may not represent precise addresses.",
        ),
        description=(
            "Map of Detroit Board of Zoning Appeals cases by the primary type "
            "of request recorded in meeting minutes from 2019 through 2026."
        ),
    )
    return {"bza-cases-map": graphic}
