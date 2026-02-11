"""Geography data loading and CRS synchronization utilities."""

import geopandas as gpd
from pathlib import Path
from shapely.geometry import box


def load_geography(geography_dir, *, load_streets=False):
    """Load boundary, water (and optionally streets) from gpkg files.

    Parameters
    ----------
    geography_dir : str or Path
        Directory containing detroit_boundary.gpkg, detroit_water.gpkg,
        and optionally detroit_network_basic.gpkg.
    load_streets : bool
        If True, also load the street network edges layer.

    Returns
    -------
    boundary : GeoDataFrame or None
    water : GeoDataFrame or None
    edges : GeoDataFrame or None
        Only returned if load_streets=True, otherwise None.
    """
    geography_dir = Path(geography_dir)

    boundary_path = geography_dir / 'detroit_boundary.gpkg'
    boundary = gpd.read_file(boundary_path) if boundary_path.exists() else None

    water_path = geography_dir / 'detroit_water.gpkg'
    water = gpd.read_file(water_path) if water_path.exists() else None

    edges = None
    if load_streets:
        network_path = geography_dir / 'detroit_network_basic.gpkg'
        if network_path.exists():
            edges = gpd.read_file(network_path, layer='edges')

    return boundary, water, edges


def prepare_water(water, ref_gdf, *, filter_lake=True):
    """CRS-sync water to a reference GeoDataFrame, optionally filter Lake St. Clair and clip.

    Parameters
    ----------
    water : GeoDataFrame
        Water features.
    ref_gdf : GeoDataFrame
        Reference GeoDataFrame whose CRS and bounds are used.
    filter_lake : bool
        If True, remove Lake St. Clair polygons.

    Returns
    -------
    GeoDataFrame
        Prepared water features.
    """
    if water is None or len(water) == 0:
        return water

    water = sync_crs(water, target_crs=ref_gdf.crs)

    if filter_lake:
        if 'name' in water.columns:
            water = water[water['name'] != 'Lake St. Clair']
        elif 'name_en' in water.columns:
            water = water[water['name_en'] != 'Lake St. Clair']

    # Clip to reference bounds
    bbox = box(*ref_gdf.total_bounds)
    bbox_gdf = gpd.GeoDataFrame({'geometry': [bbox]}, crs=ref_gdf.crs)
    water = water.clip(bbox_gdf)

    return water


def sync_crs(*gdfs, target_crs=None):
    """Reproject GeoDataFrames to a common CRS.

    If a single GeoDataFrame is passed, reproject it to target_crs.
    If multiple are passed, reproject all to target_crs (or the first GDF's CRS
    if target_crs is None).

    Returns a single GeoDataFrame if one was passed, otherwise a tuple.
    """
    if not gdfs:
        return ()

    if target_crs is None:
        target_crs = gdfs[0].crs

    result = []
    for gdf in gdfs:
        if gdf is not None and gdf.crs != target_crs:
            result.append(gdf.to_crs(target_crs))
        else:
            result.append(gdf)

    if len(result) == 1:
        return result[0]
    return tuple(result)
