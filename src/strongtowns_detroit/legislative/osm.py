"""Fetch OSM street and water features for a list of municipalities.

Used for state legislative district maps where the district crosses
multiple city boundaries (e.g. MI HD-9 spans Detroit, Hamtramck,
Highland Park, Grosse Pointe Park).
"""

from pathlib import Path

import geopandas as gpd
import osmnx as ox

# Highway types worth rendering on small choropleth panels.
ARTERIAL_HIGHWAYS = {
    'motorway', 'motorway_link',
    'trunk', 'trunk_link',
    'primary', 'primary_link',
    'secondary', 'secondary_link',
    'tertiary', 'tertiary_link',
}


def fetch_place_boundaries(places: list[str]) -> gpd.GeoDataFrame:
    """Geocode a list of place names to their administrative boundaries."""
    return ox.geocode_to_gdf(places)


def fetch_streets(places: list[str]) -> gpd.GeoDataFrame:
    """Fetch the drive-network for the union of the given places.

    Returns
    -------
    GeoDataFrame of edges with a 'highway' column.
    """
    graph = ox.graph_from_place(places, network_type='drive', simplify=True)
    edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
    edges = edges.reset_index(drop=True)

    # 'highway' may be a list when an edge has multiple OSM tags; flatten.
    if 'highway' in edges.columns:
        edges['highway'] = edges['highway'].apply(
            lambda v: v[0] if isinstance(v, list) and v else v
        )
    return edges


def filter_arterials(edges: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep only motorway/trunk/primary/secondary/tertiary edges."""
    if 'highway' not in edges.columns:
        return edges
    return edges[edges['highway'].isin(ARTERIAL_HIGHWAYS)].copy()


def fetch_water(places: list[str], drop_lakes: tuple[str, ...] = ('Lake St. Clair',)) -> gpd.GeoDataFrame:
    """Fetch water polygons inside the union of place boundaries."""
    bounds = fetch_place_boundaries(places)
    polygon = bounds.unary_union
    water = ox.features_from_polygon(polygon, tags={'natural': 'water'})
    water = water[water.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    if 'name' in water.columns and drop_lakes:
        water = water[~water['name'].isin(drop_lakes)]
    return water.reset_index(drop=True)


def save_layer(gdf: gpd.GeoDataFrame, path: str | Path) -> Path:
    """Write a GeoDataFrame to GeoPackage; coerce list-typed columns to strings."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    out = gdf.copy()
    for col in out.columns:
        if col == 'geometry':
            continue
        # Object columns containing lists/dicts break GPKG; stringify them.
        if out[col].dtype == object:
            sample = out[col].dropna().head(1)
            if len(sample) and isinstance(sample.iloc[0], (list, dict)):
                out[col] = out[col].astype(str)
    out.to_file(path, driver='GPKG')
    return path
