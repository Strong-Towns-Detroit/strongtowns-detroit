"""Detroit Census data fetching and housing burden metrics."""

import geopandas as gpd
import pandas as pd
import pytidycensus as tc
import numpy as np
from pathlib import Path
from typing import Optional


class DetroitCensusFetcher:
    """Fetches ACS data for Detroit at the tract level and aggregates to ZCTAs."""

    def __init__(self, api_key: Optional[str] = None, cache_dir: str = './cache'):
        if api_key is None:
            from strongtowns_detroit.config import get_census_api_key
            api_key = get_census_api_key()
        tc.set_census_api_key(api_key)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.renter_vars = {
            'B25070_001E': 'total_renters',
            'B25070_007E': 'renters_30_35pct',
            'B25070_008E': 'renters_35_40pct',
            'B25070_009E': 'renters_40_50pct',
            'B25070_010E': 'renters_50plus_pct',
        }
        self.owner_vars = {
            'B25091_001E': 'total_owners',
            'B25091_008E': 'owners_mtg_30_35pct',
            'B25091_009E': 'owners_mtg_35_40pct',
            'B25091_010E': 'owners_mtg_40_50pct',
            'B25091_011E': 'owners_mtg_50plus_pct',
            'B25091_019E': 'owners_nomtg_30_35pct',
            'B25091_020E': 'owners_nomtg_35_40pct',
            'B25091_021E': 'owners_nomtg_40_50pct',
            'B25091_022E': 'owners_nomtg_50plus_pct',
        }
        self.economic_vars = {
            'B19013_001E': 'median_household_income',
            'B25077_001E': 'median_home_value',
        }
        self.col_map = {**self.renter_vars, **self.owner_vars, **self.economic_vars}
        self.all_vars = list(self.renter_vars.keys()) + list(self.owner_vars.keys()) + list(self.economic_vars.keys())

    def fetch_and_aggregate(self, geojson_path: str, merge_col: str = 'zipcode') -> gpd.GeoDataFrame:
        """Load GeoJSON, fetch tract data, aggregate to target geography, calculate metrics."""
        print(f"Loading boundaries from {geojson_path}...")
        target_geo = gpd.read_file(geojson_path)

        cache_file = self.cache_dir / 'michigan_tracts_2023_acs5.parquet'

        if cache_file.exists():
            print(f"Loading Census Tract data from cache: {cache_file}")
            tract_data = gpd.read_parquet(cache_file)
        else:
            print("Fetching Census Tract data from API...")
            tract_data = tc.get_acs(
                geography='tract',
                variables=self.all_vars,
                year=2023,
                survey='acs5',
                state='MI',
                geometry=True,
            )
            tract_data = tract_data.rename(columns=self.col_map)

            print(f"Saving Census Tract data to cache: {cache_file}")
            try:
                tract_data.to_parquet(cache_file)
            except ImportError:
                print("Warning: pyarrow or fastparquet not installed. Skipping cache save.")
            except Exception as e:
                print(f"Warning: Could not save to cache: {e}")

        if tract_data.crs != target_geo.crs:
            tract_data = tract_data.to_crs(target_geo.crs)

        print(f"Aggregating to target geography using {merge_col}...")
        tract_centroids = tract_data.copy()
        tract_centroids['geometry'] = tract_centroids.geometry.centroid

        tracts_in_geo = gpd.sjoin(tract_centroids, target_geo, how='inner', predicate='within')

        count_cols = list(self.col_map.values())
        if merge_col not in tracts_in_geo.columns:
            raise ValueError(
                f"Merge column '{merge_col}' not found in joined data. "
                f"Available columns: {tracts_in_geo.columns.tolist()}"
            )

        geo_agg = tracts_in_geo.groupby(merge_col)[count_cols].sum().reset_index()

        final_gdf = target_geo.merge(geo_agg, on=merge_col, how='left')
        final_gdf = final_gdf.dropna(subset=['total_renters'])

        self._calculate_metrics(final_gdf)

        return final_gdf

    def _calculate_metrics(self, df: pd.DataFrame):
        """Calculate housing burden metrics in place."""
        # Renter Burden
        df['renters_burden_30plus'] = (
            df['renters_30_35pct'] + df['renters_35_40pct']
            + df['renters_40_50pct'] + df['renters_50plus_pct']
        )
        df['pct_renters_30plus'] = (df['renters_burden_30plus'] / df['total_renters'] * 100).round(1)

        # Owner Burden
        df['owners_burden_30plus'] = (
            df['owners_mtg_30_35pct'] + df['owners_mtg_35_40pct']
            + df['owners_mtg_40_50pct'] + df['owners_mtg_50plus_pct']
            + df['owners_nomtg_30_35pct'] + df['owners_nomtg_35_40pct']
            + df['owners_nomtg_40_50pct'] + df['owners_nomtg_50plus_pct']
        )
        df['pct_owners_30plus'] = (df['owners_burden_30plus'] / df['total_owners'] * 100).round(1)

        # Combined Burden
        df['total_households'] = df['total_renters'] + df['total_owners']
        df['burden_30plus_all'] = df['renters_burden_30plus'] + df['owners_burden_30plus']
        df['pct_burden_30plus_all'] = (df['burden_30plus_all'] / df['total_households'] * 100).round(1)

        # Severe Burden (50%+)
        df['renters_burden_50plus'] = df['renters_50plus_pct']
        df['owners_burden_50plus'] = df['owners_mtg_50plus_pct'] + df['owners_nomtg_50plus_pct']
        df['burden_50plus_all'] = df['renters_burden_50plus'] + df['owners_burden_50plus']
        df['pct_burden_50plus_all'] = (df['burden_50plus_all'] / df['total_households'] * 100).round(1)

        # Housing Shortage (Price to Income Ratio > 3)
        if 'median_home_value' in df.columns and 'median_household_income' in df.columns:
            df['price_income_ratio'] = df['median_home_value'] / df['median_household_income']
            df['housing_shortage'] = df['price_income_ratio'] > 3
        else:
            df['housing_shortage'] = False

        df['renter_accessibility_crisis'] = df['pct_renters_30plus'] > 50

        def categorize(row):
            if row['housing_shortage'] and row['renter_accessibility_crisis']:
                return 'Both Issues'
            elif row['housing_shortage']:
                return 'Shortage Only'
            elif row['renter_accessibility_crisis']:
                return 'Accessibility Only'
            else:
                return 'Neither'

        df['housing_category'] = df.apply(categorize, axis=1)
