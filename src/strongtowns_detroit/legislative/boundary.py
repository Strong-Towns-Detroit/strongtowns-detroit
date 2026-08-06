"""Fetch state legislative district (lower chamber) boundaries from TIGER/Line.

Defaults to Michigan, vintage 2024 (which carries the post-2022 MICRC maps).
Geopandas reads the zipped shapefile directly from the Census URL — caller
just supplies a state FIPS code and a district number.
"""

from pathlib import Path
from typing import Optional

import geopandas as gpd

# Michigan = 26
MI_STATE_FIPS = '26'

TIGER_SLDL_URL = (
    "https://www2.census.gov/geo/tiger/TIGER{vintage}/SLDL/"
    "tl_{vintage}_{state_fips}_sldl.zip"
)


def load_state_house_districts(
    state_fips: str = MI_STATE_FIPS,
    vintage: int = 2024,
    cache_dir: Optional[str | Path] = None,
) -> gpd.GeoDataFrame:
    """Load every state house (lower-chamber) district for a state.

    Parameters
    ----------
    state_fips : str
        Two-digit state FIPS code (default '26' = Michigan).
    vintage : int
        TIGER/Line year. 2024 reflects MI's post-2022 MICRC maps.
    cache_dir : str or Path, optional
        If given, cache the unzipped shapefile contents as a GeoPackage
        in this directory to skip re-downloads.

    Returns
    -------
    GeoDataFrame indexed by row, with columns including SLDLST (district
    number, zero-padded), GEOID, NAMELSAD, geometry.
    """
    cache_path: Optional[Path] = None
    if cache_dir is not None:
        cache_path = Path(cache_dir) / f"sldl_{state_fips}_{vintage}.gpkg"
        if cache_path.exists():
            return gpd.read_file(cache_path)

    url = TIGER_SLDL_URL.format(vintage=vintage, state_fips=state_fips)
    gdf = gpd.read_file(url)

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(cache_path, driver='GPKG')

    return gdf


def get_district(
    district_number: int | str,
    state_fips: str = MI_STATE_FIPS,
    vintage: int = 2024,
    cache_dir: Optional[str | Path] = None,
) -> gpd.GeoDataFrame:
    """Return a single state house district as a one-row GeoDataFrame.

    Parameters
    ----------
    district_number : int or str
        District number. Accepts 9, '9', or '009'; normalized to 3-digit.
    """
    code = f"{int(district_number):03d}"
    all_districts = load_state_house_districts(state_fips, vintage, cache_dir)
    match = all_districts[all_districts['SLDLST'] == code]
    if len(match) == 0:
        raise ValueError(
            f"District {code} not found in state {state_fips} (vintage {vintage}). "
            f"Available SLDLST values: {sorted(all_districts['SLDLST'].unique())[:10]}..."
        )
    return match.reset_index(drop=True)
