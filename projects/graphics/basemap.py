"""Shared geographic context for Detroit graphics."""

from functools import lru_cache
from pathlib import Path

import geopandas as gpd

from strongtowns_graphics import WebMercatorBasemap
from strongtowns_detroit.repositories import data_repository


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GEOGRAPHY = (
    data_repository() / "pipelines/housingDataAnalysis/street_simplification/output"
)
BOUNDARY = GEOGRAPHY / "detroit_boundary.gpkg"
WATER = GEOGRAPHY / "detroit_water.gpkg"
ROADS = (
    ROOT
    / "projects/detroit-land-use-forum/spirit-plaza-accessibility"
    / "output/road_context.geojson"
)


@lru_cache(maxsize=8)
def load_detroit_basemap(
    boundary_path: Path = BOUNDARY,
    roads_path: Path = ROADS,
    water_path: Path = WATER,
) -> WebMercatorBasemap:
    """Load the canonical silhouette, full OSM roads, and OSM water mask."""
    boundary = gpd.read_file(boundary_path).to_crs("EPSG:3857")
    roads = gpd.read_file(roads_path).to_crs("EPSG:3857")
    water = gpd.read_file(water_path).to_crs("EPSG:3857")
    water = water[water.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    land_geometry = boundary.geometry.iloc[0]
    water = gpd.clip(water, land_geometry)
    return WebMercatorBasemap(
        land_geometry=land_geometry,
        roads=roads,
        water=water,
    )
