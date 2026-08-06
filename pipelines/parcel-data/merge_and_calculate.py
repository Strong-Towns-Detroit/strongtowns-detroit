import geopandas as gpd
import pandas as pd
import json
import re

from strongtowns_detroit.parcels.compliance import check_compliance as _unified_check
from strongtowns_detroit.constants import PROPOSED_MIN_SQFT, PROPOSED_MIN_DWELLING_SQFT, CURRENT_MIN_DWELLING_ASSUMPTION


def check_compliance(row, zoning_restrictions):
    """Thin wrapper: delegates to unified compliance with merge_and_calculate settings."""
    return _unified_check(
        row, zoning_restrictions,
        district_col='zoning_district',
        area_cols=('total_square_footage', 'shape_area'),
    )


def _normalize_columns(df):
    """Normalize column names to snake_case and deduplicate.

    The Hub bulk-download CSV uses Title Case with spaces (e.g. 'Parcel ID'),
    while the FeatureServer GeoJSON uses snake_case (e.g. 'parcel_id').
    This ensures both sources use consistent snake_case names.
    """
    def to_snake(name):
        if name == name.lower() and ' ' not in name:
            return name
        name = name.replace('%', 'pct').replace('  ', ' ')
        name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
        name = re.sub(r'[\s\-]+', '_', name)
        return name.lower().strip('_')

    df.columns = [to_snake(c) for c in df.columns]

    # Drop exact duplicate columns (e.g. object_id and ObjectId both → object_id)
    df = df.loc[:, ~df.columns.duplicated()]
    return df


def main():
    print("Loading Parcels.geojson...")
    gdf = gpd.read_file("Parcels.geojson")
    gdf = _normalize_columns(gdf)

    # Ensure consistent join key — legacy files used 'parcel_number'
    if 'parcel_number' in gdf.columns and 'parcel_id' not in gdf.columns:
        gdf = gdf.rename(columns={'parcel_number': 'parcel_id'})

    # The GeoJSON already has all attribute fields plus geometry.
    # Only merge with the CSV if it contains columns the GeoJSON lacks
    # (e.g. the legacy parcel-data-cleaned.csv had a different schema).
    import os
    csv_path = "parcel-data.csv" if os.path.exists("parcel-data.csv") else "parcel-data-cleaned.csv"
    print(f"Loading {csv_path}...")
    csv = pd.read_csv(csv_path, low_memory=False)
    csv = _normalize_columns(csv)

    # Find columns in the CSV that are NOT already in the GeoJSON
    extra_csv_cols = [c for c in csv.columns if c not in gdf.columns and c != 'geometry']

    if extra_csv_cols:
        print(f"Merging {len(extra_csv_cols)} extra CSV columns: {extra_csv_cols}")
        # Ensure CSV has a join key
        if 'parcel_number' in csv.columns and 'parcel_id' not in csv.columns:
            csv = csv.rename(columns={'parcel_number': 'parcel_id'})
        merged = gdf.merge(csv[['parcel_id'] + extra_csv_cols], on='parcel_id', how='left')
    else:
        print("GeoJSON already contains all CSV columns — using GeoJSON directly.")
        merged = gdf

    print(f"{len(merged)} parcels, {merged['use_code_description'].notna().sum()} with Use Code Description.")

    # Load Restrictions
    with open('zoning_districts_to_lot_size_restrictions.json', 'r') as f:
        zoning_restrictions = json.load(f)

    print("Calculating compliance metrics...")

    compliance_metrics = merged.apply(check_compliance, axis=1, zoning_restrictions=zoning_restrictions)
    final_gdf = pd.concat([merged, compliance_metrics], axis=1)

    print("Saving outputs...")
    # Save CSV for Analysis Script (No geometry needed, simpler load)
    csv_out = 'parcels_with_compliance.csv'
    pd.DataFrame(final_gdf.drop(columns='geometry')).to_csv(csv_out, index=False)
    print(f"Saved {csv_out}")

    # Save GPKG for Map
    gpkg_out = 'parcels_with_compliance.gpkg'
    final_gdf.to_file(gpkg_out, driver='GPKG')
    print(f"Saved {gpkg_out}")

if __name__ == "__main__":
    main()
