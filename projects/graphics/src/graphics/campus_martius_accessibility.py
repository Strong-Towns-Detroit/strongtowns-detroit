"""Travel-time reach from Campus Martius."""

import json
import sys
from pathlib import Path

import geopandas as gpd
from shapely.ops import unary_union

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
SOURCE_DIR = FORUM / "spirit-plaza-accessibility"
sys.path.insert(0, str(SOURCE_DIR))

from export_mode_assets import (  # noqa: E402
    COLORS,
    _project,
    build_graphic,
)
from strongtowns_graphics import (
    GraphicInput,
    graphic_definition,
    wide_map_with_legend_on_mobile,
)


@graphic_definition(
    "campus_martius_accessibility",
    inputs=(
        GraphicInput(
            "travel_times",
            "detroit.spirit-plaza.accessibility",
            "display_isochrones.geojson",
        ),
        GraphicInput("roads", "detroit.osm.road-context", "road_context.geojson"),
        GraphicInput("boundary", "detroit.osm.basemap.raw", "detroit_boundary.geojson"),
    ),
)
def build(context):
    spec = json.loads((SOURCE_DIR / "spec.json").read_text())
    data = gpd.read_file(context.input("travel_times")).to_crs("EPSG:4326")
    roads = gpd.read_file(context.input("roads")).to_crs("EPSG:4326")
    boundary = gpd.read_file(context.input("boundary")).to_crs("EPSG:4326")
    city = _project(unary_union(boundary.geometry))
    data.geometry = data.geometry.map(_project)
    roads.geometry = roads.geometry.map(_project)

    legend_items = [
        (f"{minutes} min", COLORS[minutes])
        for minutes in spec["threshold_minutes"]
    ]
    transit_subtitle = (
        "Median five- to 30-minute transit reach from Campus Martius · "
        "Wednesday noon–1 p.m."
    )
    driving_subtitle = "Five- to 30-minute driving times from Campus Martius"
    return {
        "public-transit": wide_map_with_legend_on_mobile(
            build_graphic(
                "public_transport",
                data,
                roads,
                city,
                spec,
                title="Transit is barely viable along the inner spokes",
                subtitle=transit_subtitle,
                sources=(
                    "Source: TravelTime API · Transit is the median of 13 departures, "
                    "noon–1 p.m.",
                ),
                description=(
                    f"{transit_subtitle}. Five through thirty minute travel bands."
                ),
            ),
            items=legend_items,
        ),
        "driving": wide_map_with_legend_on_mobile(
            build_graphic(
                "driving",
                data,
                roads,
                city,
                spec,
                title="A 15-minute city—by car",
                subtitle=driving_subtitle,
                sources=("Source: TravelTime API · Wednesday midday travel-time model",),
                description=(
                    f"{driving_subtitle}. Five through thirty minute travel bands."
                ),
            ),
            items=legend_items,
        ),
    }
