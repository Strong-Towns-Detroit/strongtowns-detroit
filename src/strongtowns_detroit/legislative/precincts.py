"""Fetch Detroit voting precinct shapes + 2024 results, clip to a district.

Sources:
- Shapes: City of Detroit ArcGIS FeatureServer
  ('Current_City_of_Detroit_Election_Precincts', 400 polygons)
- Results: OpenElections MI 2024 general election precinct CSV

Coverage gap: only Detroit precincts. Hamtramck, Highland Park, Grosse
Pointe Park precincts (~5-10 in HD-9) are not yet pulled — a future
enhancement would use a statewide MI voting-precincts layer.
"""

import re
from io import StringIO
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests

DETROIT_PRECINCTS_URL = (
    "https://services2.arcgis.com/qvkbeam7Wirps6zC/ArcGIS/rest/services/"
    "Current_City_of_Detroit_Election_Precincts/FeatureServer/0/query"
    "?where=1%3D1&outFields=*&outSR=4326&f=geojson"
)

OPENELECTIONS_2024_URL = (
    "https://raw.githubusercontent.com/openelections/openelections-data-mi/"
    "master/2024/20241105__mi__general__precinct.csv"
)

MI_EQUAL_AREA_CRS = 'EPSG:6497'

# Precinct rows we want to pivot into per-precinct columns. Keep it small
# for v1 — one race (President) gives D-margin and turnout, the dominant
# campaign-strategy signals.
RACES_OF_INTEREST = {
    'President': 'pres',
}

# Party normalization (OpenElections values vary).
PARTY_BUCKETS = {
    'DEM': 'dem', 'REP': 'rep',
    'LIB': 'other', 'GRN': 'other', 'CON': 'other', 'NPA': 'other',
    'TXC': 'other', 'WTP': 'other', 'WRI': 'other', 'JFP': 'other',
}


def fetch_detroit_precincts(cache_dir: str | Path = './cache') -> gpd.GeoDataFrame:
    """Fetch all Detroit precinct polygons from ArcGIS, cached as GeoPackage."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / 'detroit_precincts_2024.gpkg'

    if cache_file.exists():
        print(f"Loading precincts from cache: {cache_file}")
        return gpd.read_file(cache_file)

    print(f"Fetching Detroit precincts from ArcGIS...")
    gdf = gpd.read_file(DETROIT_PRECINCTS_URL)
    print(f"  {len(gdf)} precinct polygons")
    gdf.to_file(cache_file, driver='GPKG')
    return gdf


def fetch_2024_results(cache_dir: str | Path = './cache') -> pd.DataFrame:
    """Fetch OpenElections MI 2024 general precinct CSV, cached."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / 'openelections_mi_2024_general_precinct.csv'

    if cache_file.exists():
        print(f"Loading 2024 results from cache: {cache_file}")
        return pd.read_csv(cache_file, dtype={'precinct': str})

    print(f"Downloading 2024 MI precinct results from OpenElections...")
    resp = requests.get(OPENELECTIONS_2024_URL, timeout=60)
    resp.raise_for_status()
    cache_file.write_text(resp.text)
    return pd.read_csv(StringIO(resp.text), dtype={'precinct': str})


# Match "City of Detroit, Precinct 123" → 123
DETROIT_PRECINCT_RE = re.compile(r'City of Detroit,\s*Precinct\s+(\d+)', re.IGNORECASE)


def extract_detroit_precinct_number(precinct_str: str) -> Optional[int]:
    if not isinstance(precinct_str, str):
        return None
    m = DETROIT_PRECINCT_RE.match(precinct_str)
    return int(m.group(1)) if m else None


def pivot_results_to_precinct(results: pd.DataFrame) -> pd.DataFrame:
    """Reduce long-form results CSV to one row per Detroit precinct.

    Columns: precinct (int), pres_dem, pres_rep, pres_other, pres_total,
    pres_dem_pct, pres_rep_pct, pres_dem_margin, registered_voters.
    """
    df = results.copy()
    df['precinct_num'] = df['precinct'].apply(extract_detroit_precinct_number)
    df = df[df['precinct_num'].notna()].copy()
    df['precinct_num'] = df['precinct_num'].astype(int)

    rows = []
    for precinct_num, group in df.groupby('precinct_num'):
        row = {'precinct': precinct_num}

        # Registered voters (special row in OpenElections)
        rv = group[group['office'] == 'Registered Voters']['votes'].sum()
        row['registered_voters'] = int(rv) if rv else 0

        for office_name, prefix in RACES_OF_INTEREST.items():
            race = group[group['office'] == office_name]
            if race.empty:
                continue
            buckets = {'dem': 0, 'rep': 0, 'other': 0}
            for _, r in race.iterrows():
                bucket = PARTY_BUCKETS.get(str(r['party']).strip().upper(), 'other')
                buckets[bucket] += int(r['votes']) if pd.notna(r['votes']) else 0
            total = sum(buckets.values())
            row[f'{prefix}_dem']   = buckets['dem']
            row[f'{prefix}_rep']   = buckets['rep']
            row[f'{prefix}_other'] = buckets['other']
            row[f'{prefix}_total'] = total
            if total > 0:
                row[f'{prefix}_dem_pct'] = round(buckets['dem']  / total * 100, 1)
                row[f'{prefix}_rep_pct'] = round(buckets['rep']  / total * 100, 1)
                row[f'{prefix}_dem_margin'] = round((buckets['dem'] - buckets['rep']) / total * 100, 1)
            else:
                row[f'{prefix}_dem_pct'] = None
                row[f'{prefix}_rep_pct'] = None
                row[f'{prefix}_dem_margin'] = None

        # Turnout = pres_total / registered_voters * 100
        if row['registered_voters'] > 0 and row.get('pres_total', 0) > 0:
            row['turnout_pct'] = round(row['pres_total'] / row['registered_voters'] * 100, 1)
        else:
            row['turnout_pct'] = None

        rows.append(row)
    return pd.DataFrame(rows)


def clip_precincts_to_district(
    precincts: gpd.GeoDataFrame,
    district: gpd.GeoDataFrame,
    area_threshold: float = 0.3,
    exclude_precincts: Optional[set[int]] = None,
) -> gpd.GeoDataFrame:
    """Same area-fraction inclusion as `clip_tracts_to_district`."""
    if precincts.crs != district.crs:
        precincts = precincts.to_crs(district.crs)

    proj_p = precincts.to_crs(MI_EQUAL_AREA_CRS)
    proj_d = district.to_crs(MI_EQUAL_AREA_CRS)
    district_geom = proj_d.geometry.unary_union

    minx, miny, maxx, maxy = proj_d.total_bounds
    bounds = proj_p.geometry.bounds
    bbox_mask = ~(
        (bounds['maxx'] < minx) | (bounds['minx'] > maxx) |
        (bounds['maxy'] < miny) | (bounds['miny'] > maxy)
    )
    candidates = proj_p[bbox_mask].copy()

    tract_area = candidates.geometry.area
    inter_area = candidates.geometry.intersection(district_geom).area
    frac = (inter_area / tract_area).fillna(0)
    keep_mask = frac >= area_threshold
    keep = set(candidates.loc[keep_mask, 'Precinct'].astype(int))
    if exclude_precincts:
        keep -= set(exclude_precincts)

    out = precincts[precincts['Precinct'].astype(int).isin(keep)].copy()
    return out.reset_index(drop=True)


def fetch_district_precincts(
    district: gpd.GeoDataFrame,
    cache_dir: str | Path = './cache',
    area_threshold: float = 0.3,
    exclude_precincts: Optional[set[int]] = None,
) -> gpd.GeoDataFrame:
    """End-to-end: shapes + results clipped to a district, results joined."""
    precincts = fetch_detroit_precincts(cache_dir=cache_dir)
    in_district = clip_precincts_to_district(
        precincts, district, area_threshold, exclude_precincts,
    )
    in_district['Precinct'] = in_district['Precinct'].astype(int)

    results = fetch_2024_results(cache_dir=cache_dir)
    pivoted = pivot_results_to_precinct(results)

    merged = in_district.merge(pivoted, left_on='Precinct', right_on='precinct', how='left')
    # 'precinct' (lowercase) is redundant with 'Precinct' and collides on
    # case-insensitive GPKG field naming.
    if 'precinct' in merged.columns:
        merged = merged.drop(columns=['precinct'])
    return merged
