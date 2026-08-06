"""Fetch tract-level ACS data and clip it to a state legislative district."""

from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import pytidycensus as tc

from strongtowns_detroit.legislative.acs import AGE_BINS, all_variables
from strongtowns_detroit.legislative.boundary import (
    MI_STATE_FIPS,
    get_district,
)

# Census API caps each request at 50 variables.
ACS_VAR_LIMIT = 50

# Equal-area projection for Michigan; gives accurate sq-meter areas.
MI_EQUAL_AREA_CRS = 'EPSG:6497'  # NAD83(2011) / Michigan South (m)


def _chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def fetch_state_tracts(
    state_fips: str = MI_STATE_FIPS,
    year: int = 2024,
    cache_dir: str | Path = './cache',
) -> gpd.GeoDataFrame:
    """Pull tract-level ACS 5-year data for the entire state, with geometry.

    Variables are split into <=50-item chunks (the Census API limit) and
    re-merged on GEOID. Result is cached as parquet.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"tracts_{state_fips}_{year}_acs5.parquet"

    if cache_file.exists():
        print(f"Loading tracts from cache: {cache_file}")
        return gpd.read_parquet(cache_file)

    var_map = all_variables()
    var_codes = list(var_map.keys())
    print(f"Fetching {len(var_codes)} ACS variables for state {state_fips} (year {year})...")

    chunks = _chunk(var_codes, ACS_VAR_LIMIT)
    base: Optional[gpd.GeoDataFrame] = None
    for i, chunk in enumerate(chunks, 1):
        print(f"  chunk {i}/{len(chunks)} ({len(chunk)} vars)")
        gdf = tc.get_acs(
            geography='tract',
            variables=chunk,
            year=year,
            survey='acs5',
            state=state_fips,
            geometry=(i == 1),  # geometry only needed once
            output='wide',
        )
        if i == 1:
            base = gdf
        else:
            non_geom_cols = [c for c in gdf.columns if c != 'geometry']
            base = base.merge(
                gdf[non_geom_cols].drop(columns=['NAME'], errors='ignore'),
                on='GEOID', how='left',
            )

    base = base.rename(columns=var_map)

    try:
        base.to_parquet(cache_file)
        print(f"Cached to {cache_file}")
    except Exception as e:
        print(f"Warning: could not cache tracts ({e})")

    return base


def clip_tracts_to_district(
    tracts: gpd.GeoDataFrame,
    district: gpd.GeoDataFrame,
    area_threshold: float = 0.3,
    exclude_geoids: Optional[set[str]] = None,
) -> gpd.GeoDataFrame:
    """Return tracts whose intersection with the district covers at least
    ``area_threshold`` of the tract's total area.

    Centroid-based assignment misses tracts with irregular geometry whose
    centroid happens to fall outside the district (e.g. L-shaped tracts
    next to rail yards or industrial corridors). Area-fraction inclusion
    captures these while still excluding boundary slivers.

    Default threshold 0.3 = "tract is at least 30% inside the district."
    Aggregates over the resulting tracts slightly over-count for partial
    tracts (we sum the whole tract's counts, not the inside-only fraction);
    that's the right tradeoff for a coarse campaign tool.
    """
    if tracts.crs != district.crs:
        tracts = tracts.to_crs(district.crs)

    proj_t = tracts.to_crs(MI_EQUAL_AREA_CRS)
    proj_d = district.to_crs(MI_EQUAL_AREA_CRS)
    district_geom = proj_d.geometry.unary_union

    # Cheap bbox pre-filter so we only run intersection() on candidates
    minx, miny, maxx, maxy = proj_d.total_bounds
    bounds = proj_t.geometry.bounds
    bbox_mask = ~(
        (bounds['maxx'] < minx) | (bounds['minx'] > maxx) |
        (bounds['maxy'] < miny) | (bounds['miny'] > maxy)
    )
    candidates = proj_t[bbox_mask].copy()

    tract_area = candidates.geometry.area
    inter_area = candidates.geometry.intersection(district_geom).area
    frac = (inter_area / tract_area).fillna(0)

    keep_geoids = set(candidates.loc[frac >= area_threshold, 'GEOID'])
    if exclude_geoids:
        keep_geoids -= set(exclude_geoids)
    return tracts[tracts['GEOID'].isin(keep_geoids)].copy().reset_index(drop=True)


def compute_metrics(tracts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add derived per-tract metrics: density, shares, rates.

    Modifies a copy. Areas are computed in MI_EQUAL_AREA_CRS for accuracy.
    """
    df = tracts.copy()

    # Land area in km² from projected geometry.
    proj = df.to_crs(MI_EQUAL_AREA_CRS)
    df['land_area_km2'] = proj.geometry.area / 1_000_000.0
    df['pop_density_per_km2'] = (
        df['total_population'] / df['land_area_km2']
    ).replace([np.inf, -np.inf], np.nan)

    # Race shares (% of total).
    race_total = df['race_total'].replace(0, np.nan)
    for col in ['nh_white', 'nh_black', 'nh_asian', 'nh_two_or_more', 'hispanic']:
        df[f'pct_{col}'] = (df[col] / race_total * 100).round(1)

    # Poverty rate.
    df['pct_poverty'] = (
        df['poverty_below'] / df['poverty_universe'].replace(0, np.nan) * 100
    ).round(1)

    # Education: % bachelor's or higher among 25+.
    edu_total = df['edu_total_25plus'].replace(0, np.nan)
    df['edu_bachelors_plus'] = (
        df['edu_bachelors'] + df['edu_masters']
        + df['edu_professional'] + df['edu_doctorate']
    )
    df['pct_bachelors_plus'] = (df['edu_bachelors_plus'] / edu_total * 100).round(1)

    # Tenure shares.
    tenure_total = df['tenure_total'].replace(0, np.nan)
    df['pct_renter'] = (df['renter_occupied'] / tenure_total * 100).round(1)
    df['pct_owner'] = (df['owner_occupied'] / tenure_total * 100).round(1)

    # Vacancy rate.
    df['pct_vacant'] = (
        df['housing_units_vacant'] / df['housing_units_total'].replace(0, np.nan) * 100
    ).round(1)

    # Unemployment rate (of labor force).
    df['pct_unemployed'] = (
        df['unemployed'] / df['in_labor_force'].replace(0, np.nan) * 100
    ).round(1)

    # Foreign-born share.
    df['pct_foreign_born'] = (
        df['foreign_born'] / df['pob_total'].replace(0, np.nan) * 100
    ).round(1)

    # Age aggregates: sum each bin across male + female brackets.
    for bin_name, brackets in AGE_BINS:
        cols = [f'{sex}_{b}' for sex in ('male', 'female') for b in brackets]
        present = [c for c in cols if c in df.columns]
        df[bin_name] = df[present].sum(axis=1) if present else 0

    # Convenience aggregates kept from prior schema.
    df['pop_18_34'] = df['age_18_24'] + df['age_25_34']
    df['pop_65_plus'] = df['age_65_74'] + df['age_75_plus']
    pop_age = df['pop_total_for_age'].replace(0, np.nan)
    df['pct_18_34'] = (df['pop_18_34'] / pop_age * 100).round(1)
    df['pct_65_plus'] = (df['pop_65_plus'] / pop_age * 100).round(1)

    return df


def summarize_district(tracts_in_district: gpd.GeoDataFrame) -> pd.DataFrame:
    """One-row DataFrame of district-level totals and shares.

    Counts are summed across tracts; rates are recomputed against the
    summed denominators (so we don't average tract-level percents, which
    would be population-weighted incorrectly).
    """
    sums = {
        col: tracts_in_district[col].sum(skipna=True)
        for col in [
            'total_population', 'land_area_km2',
            'race_total', 'nh_white', 'nh_black', 'nh_asian',
            'nh_two_or_more', 'hispanic',
            'poverty_universe', 'poverty_below',
            'edu_total_25plus', 'edu_bachelors_plus',
            'tenure_total', 'owner_occupied', 'renter_occupied',
            'housing_units_total', 'housing_units_vacant',
            'pop_16plus', 'in_labor_force', 'unemployed',
            'pob_total', 'foreign_born',
            'pop_total_for_age', 'pop_18_34', 'pop_65_plus',
        ]
    }

    def pct(num_key, den_key):
        d = sums[den_key]
        return round(sums[num_key] / d * 100, 1) if d else np.nan

    # Median income & home value: tract-level medians don't sum, so we
    # report a population-weighted mean of medians as a directional figure.
    weights = tracts_in_district['total_population'].fillna(0)
    def weighted_mean(col):
        vals = tracts_in_district[col]
        mask = vals.notna() & (weights > 0)
        if not mask.any():
            return np.nan
        return float(np.average(vals[mask], weights=weights[mask]))

    row = {
        'total_population': sums['total_population'],
        'land_area_km2': round(sums['land_area_km2'], 2),
        'pop_density_per_km2': round(
            sums['total_population'] / sums['land_area_km2'], 1
        ) if sums['land_area_km2'] else np.nan,
        'pct_nh_white': pct('nh_white', 'race_total'),
        'pct_nh_black': pct('nh_black', 'race_total'),
        'pct_nh_asian': pct('nh_asian', 'race_total'),
        'pct_hispanic': pct('hispanic', 'race_total'),
        'pct_18_34': pct('pop_18_34', 'pop_total_for_age'),
        'pct_65_plus': pct('pop_65_plus', 'pop_total_for_age'),
        'pct_poverty': pct('poverty_below', 'poverty_universe'),
        'pct_bachelors_plus': pct('edu_bachelors_plus', 'edu_total_25plus'),
        'pct_renter': pct('renter_occupied', 'tenure_total'),
        'pct_owner': pct('owner_occupied', 'tenure_total'),
        'pct_vacant': pct('housing_units_vacant', 'housing_units_total'),
        'pct_unemployed': pct('unemployed', 'in_labor_force'),
        'pct_foreign_born': pct('foreign_born', 'pob_total'),
        'median_household_income_pop_weighted': round(
            weighted_mean('median_household_income'), 0
        ),
        'median_home_value_pop_weighted': round(
            weighted_mean('median_home_value'), 0
        ),
        'median_gross_rent_pop_weighted': round(
            weighted_mean('median_gross_rent'), 0
        ),
        'tract_count': len(tracts_in_district),
    }
    return pd.DataFrame([row])


def fetch_district_data(
    district_number: int | str,
    state_fips: str = MI_STATE_FIPS,
    year: int = 2024,
    cache_dir: str | Path = './cache',
    api_key: Optional[str] = None,
    exclude_geoids: Optional[set[str]] = None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, pd.DataFrame]:
    """End-to-end: boundary + tract data + metrics + district summary.

    Returns
    -------
    district : GeoDataFrame
        One-row boundary.
    tracts : GeoDataFrame
        Per-tract data with derived metrics.
    summary : DataFrame
        One-row district-level totals/shares.
    """
    if api_key is None:
        from strongtowns_detroit.config import get_census_api_key
        api_key = get_census_api_key()
    tc.set_census_api_key(api_key)

    district = get_district(district_number, state_fips, cache_dir=cache_dir)
    state_tracts = fetch_state_tracts(state_fips, year, cache_dir=cache_dir)
    in_district = clip_tracts_to_district(state_tracts, district, exclude_geoids=exclude_geoids)
    with_metrics = compute_metrics(in_district)
    summary = summarize_district(with_metrics)
    return district, with_metrics, summary
