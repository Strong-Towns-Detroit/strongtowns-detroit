import geopandas as gpd
import pandas as pd
import json

from strongtowns_detroit.parcels.compliance import check_compliance as _unified_check
from strongtowns_detroit.constants import PROPOSED_MIN_SQFT, PROPOSED_MIN_DWELLING_SQFT, CURRENT_MIN_DWELLING_ASSUMPTION


def check_compliance(row, zoning_restrictions):
    """Thin wrapper: delegates to unified compliance with merge_and_calculate settings."""
    return _unified_check(
        row, zoning_restrictions,
        district_col='zoning',
        area_cols=('total_square_footage_csv', 'total_square_footage_geo',
                   'total_square_footage', 'shape_area', 'Shape__Area'),
    )


def main():
    print("Loading Parcels.geojson...")
    gdf = gpd.read_file("Parcels.geojson")

    print("Loading parcel-data-cleaned.csv...")
    csv = pd.read_csv("parcel-data-cleaned.csv", low_memory=False)

    print("Merging data on parcel_number/parcel_id...")
    # Select columns from CSV to join
    cols_to_use = [
        'parcel_id',
        'use_code',
        'use_code_description',
        'zoning_district',
        'total_floor_area',
        'frontage',
        'shape_area'
    ]

    # Standardize join key
    # GeoJSON has 'parcel_number', CSV has 'parcel_id'
    csv = csv.rename(columns={'parcel_id': 'parcel_number'})

    # Merge. Left on GDF to keep geometry.
    merged = gdf.merge(csv, on='parcel_number', how='left', suffixes=('_geo', '_csv'))

    print(f"Matched {merged['use_code_description'].notna().sum()} records with Use Code Description.")

    # Resolve conflicts / standardized names for Analysis Script
    merged['use_code_desc'] = merged['use_code_description'].fillna(merged.get('use_code_desc', ''))
    merged['zoning'] = merged['zoning_district'].fillna(merged.get('zoning', ''))

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
