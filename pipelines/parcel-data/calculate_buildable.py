import pandas as pd
import json
import logging

from strongtowns_detroit.parcels.compliance import check_compliance as _unified_check
from strongtowns_detroit.constants import PROPOSED_MIN_SQFT, PROPOSED_MIN_DWELLING_SQFT, CURRENT_MIN_DWELLING_ASSUMPTION

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def check_compliance(row, zoning_restrictions):
    """Thin wrapper: delegates to unified compliance with calculate_buildable settings."""
    return _unified_check(
        row, zoning_restrictions,
        district_col='zoning_district',
        area_cols=('shape_area',),
        width_col='frontage',
        include_buildable=True,
    )


def calculate_buildable():
    # Load the data — prefer the raw download, fall back to legacy cleaned file
    import os
    input_file = 'parcel-data.csv' if os.path.exists('parcel-data.csv') else 'parcel-data-cleaned.csv'
    print(f"Loading {input_file}...")

    # helper to handle mixed types if needed, though 'low_memory=False' usually suffices
    df = pd.read_csv(input_file, low_memory=False)

    with open('zoning_districts_to_lot_size_restrictions.json', 'r') as f:
        zoning_restrictions = json.load(f)

    try:
        print("Calculating compliance metrics...")
        compliance_metrics = df.apply(check_compliance, axis=1, zoning_restrictions=zoning_restrictions)
        df_out = pd.concat([df, compliance_metrics], axis=1)
        
        # Statistics
        print("\n--- Compliance Statistics ---")
        print(f"Total Parcels: {len(df_out):,}")
        print(f"Violating Current Min Sqft: {df_out['violates_current_min_sqft'].sum():,}")
        print(f"Violating Current Min Width: {df_out['violates_current_min_width'].sum():,}")
        print(f"Violating Proposed Min Sqft ({PROPOSED_MIN_SQFT}): {df_out['violates_proposed_min_sqft'].sum():,}")
        print(f"Violating Proposed Min Dwelling ({PROPOSED_MIN_DWELLING_SQFT}): {df_out['violates_proposed_min_dwelling'].sum():,}")
        
        csv_file = 'parcels_with_compliance.csv'
        print(f"Saving to {csv_file}...")
        df_out.to_csv(csv_file, index=False)
        print("Done.")

    except ValueError as e:
        print(f"Processing failed: {e}")
        raise

if __name__ == "__main__":
    calculate_buildable()
