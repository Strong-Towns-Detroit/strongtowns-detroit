"""Assign human-readable neighborhood names to census tracts.

Strategy:
1. For each tract, compute its area-overlap with every neighborhood polygon.
   Pick the neighborhood with the largest overlap.
2. For tracts with NO overlap (e.g. Hamtramck, Highland Park, Grosse Pointe
   Park — outside Detroit's neighborhood index), fall back to the nearest
   neighborhood by centroid distance and prefix with "near " so the
   approximation is visible in the UI.
3. Manual overrides from a JSON file win over both auto methods.

The `naming_source` column carries 'overlap', 'nearest', or 'override' so
the UI can flag low-confidence names.
"""

import json
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd

MI_EQUAL_AREA_CRS = 'EPSG:6497'

# Possible name columns across different Detroit neighborhood sources.
NAME_CANDIDATES = [
    'nhood_name', 'NHOOD_NAME',
    'name', 'NAME', 'Name',
    'NEIGHBORHO',
]


def detect_name_col(gdf: gpd.GeoDataFrame) -> str:
    for c in NAME_CANDIDATES:
        if c in gdf.columns:
            return c
    raise ValueError(
        f"No recognized name column. Tried {NAME_CANDIDATES}, "
        f"have {list(gdf.columns)}"
    )


def load_overrides(path: Optional[str | Path]) -> dict[str, str]:
    if path is None:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def name_tracts(
    tracts: gpd.GeoDataFrame,
    neighborhoods: gpd.GeoDataFrame,
    overrides: Optional[dict[str, str]] = None,
    name_col: Optional[str] = None,
) -> pd.DataFrame:
    """Return DataFrame[GEOID, neighborhood_name, naming_source]."""
    if name_col is None:
        name_col = detect_name_col(neighborhoods)

    proj_t = tracts.to_crs(MI_EQUAL_AREA_CRS)
    proj_n = neighborhoods.to_crs(MI_EQUAL_AREA_CRS).reset_index(drop=True)
    n_sindex = proj_n.sindex
    overrides = overrides or {}
    results = []

    for _, tract in proj_t.iterrows():
        geoid = tract['GEOID']
        if geoid in overrides:
            results.append({
                'GEOID': geoid,
                'neighborhood_name': overrides[geoid],
                'naming_source': 'override',
            })
            continue

        tract_geom = tract.geometry
        candidates = list(n_sindex.intersection(tract_geom.bounds))
        best_overlap = 0.0
        best_name = None
        for ci in candidates:
            hood = proj_n.iloc[ci]
            try:
                overlap = tract_geom.intersection(hood.geometry).area
            except Exception:
                overlap = 0.0
            if overlap > best_overlap:
                best_overlap = overlap
                best_name = hood[name_col]

        if best_overlap > 0 and best_name is not None:
            results.append({
                'GEOID': geoid,
                'neighborhood_name': best_name,
                'naming_source': 'overlap',
            })
            continue

        # Fallback: nearest neighborhood by centroid distance.
        tract_centroid = tract_geom.centroid
        distances = proj_n.geometry.distance(tract_centroid)
        nearest_idx = int(distances.idxmin())
        nearest_name = proj_n.loc[nearest_idx, name_col]
        results.append({
            'GEOID': geoid,
            'neighborhood_name': f'near {nearest_name}',
            'naming_source': 'nearest',
        })

    return pd.DataFrame(results)
