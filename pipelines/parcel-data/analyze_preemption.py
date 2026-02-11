import pandas as pd
import numpy as np
import json

from strongtowns_detroit.parcels.preemption import is_vacant
from strongtowns_detroit.constants import (
    RESIDENTIAL_ZONES, TARGET_KEYS, DUPLEX_KEYS, MULTI_FAMILY_KEYS, ADU_KEYS,
)


def analyze_preemption():
    print("Loading data...")
    # Load the results from the previous step
    df = pd.read_csv('parcels_with_compliance.csv', low_memory=False)

    # Deduplicate by Parcel Number (One Parcel = One Record, ignore multi-polygon splits)
    # This prevents inflation of counts where geometry is split.
    print(f"Initial Rows: {len(df)}")
    df = df.drop_duplicates(subset=['parcel_number'])
    print(f"Unique Parcels: {len(df)}")

    # Load Specific Zoning Map
    with open('parcel_use_codes_to_zoning_districts_mapping.json', 'r') as f:
        zoning_map = json.load(f)

    target_keys = TARGET_KEYS

    # --- 1. Setup & categorization ---

    residential_zones = RESIDENTIAL_ZONES

    df['is_vacant'] = df['use_code_desc'].apply(is_vacant)
    df['is_residential_zone'] = df['zoning'].isin(residential_zones)
    
    # --- 2. Metric: Lot Size (Buildable Land) ---
    print("Analyzing Lot Size...")
    
    lot_stats = df.groupby('zoning')[[
        'violates_current_min_sqft', 
        'violates_proposed_min_sqft'
    ]].agg(['sum', 'count'])
    
    saved_mask = (df['violates_current_min_sqft']) & (~df['violates_proposed_min_sqft'])
    df['lot_size_saved_by_preemption'] = saved_mask
    
    lot_summary = df.groupby('zoning').agg(
        Total_Parcels=('parcel_number', 'count'),
        Violating_Current_Law=('violates_current_min_sqft', 'sum'),
        Violating_State_Cap=('violates_proposed_min_sqft', 'sum'),
        Legalized_By_State=('lot_size_saved_by_preemption', 'sum')
    )
    
    lot_summary_res = lot_summary[lot_summary.index.isin(residential_zones)]
    
    # --- 3. Metric: Dwelling Size ---
    print("Analyzing Dwelling Size...")
    occupied_res = df[(~df['is_vacant']) & (df['is_residential_zone'])].copy()
    
    dwelling_saved_mask = (occupied_res['violates_current_min_dwelling_assumption']) & (~occupied_res['violates_proposed_min_dwelling'])
    occupied_res['dwelling_saved'] = dwelling_saved_mask
    
    dwelling_stats = occupied_res['dwelling_saved'].sum()
    dwelling_violating_proposed = occupied_res['violates_proposed_min_dwelling'].sum()
    
    # --- 4. Metric: Use Code Legality with Specific Map ---
    print("Analyzing Use Code Legality...")
    
    # Logic: For each target key, find parcels with that use_code_desc.
    # Check if their current zoning is in the 'by_right' or 'by_right_subject_to_conditions' list of that key.
    # If not, it's non-conforming.
    
    use_violation_stats = []
    
    for key in target_keys:
        if key not in zoning_map:
            print(f"Warning: Key {key} not found in map.")
            continue
            
        allowed_districts = (
            zoning_map[key]['zoning_districts'].get('by_right', [])
        )
        
        # Filter parcels matching this description
        subset = df[df['use_code_desc'] == key].copy()
        total_count = len(subset)
        
        if total_count == 0:
            continue
            
        # Check Compliance
        # We handle NaN zoning as compliant or skip? 
        # Usually NaN zoning means we don't know, so exclude from violation count.
        subset_known = subset[subset['zoning'].notna()]
        
        # Non-conforming: Zoning NOT in allowed_districts
        violating = subset_known[~subset_known['zoning'].isin(allowed_districts)]
        violation_count = len(violating)
        
        use_violation_stats.append({
            'Use Type': key,
            'Total Existing': total_count,
            'Non-Conforming (Use Violation)': violation_count,
            'Percent Non-Conforming': (violation_count / total_count * 100) if total_count > 0 else 0
        })

    use_stats_df = pd.DataFrame(use_violation_stats)
    
    if use_stats_df.empty:
        print("No violations found or no matching data.")
        duplex_stats = pd.Series({'Non-Conforming (Use Violation)': 0, 'Total Existing': 0})
        multi_stats = pd.Series({'Non-Conforming (Use Violation)': 0, 'Total Existing': 0})
        adu_stats = pd.Series({'Non-Conforming (Use Violation)': 0, 'Total Existing': 0})
        use_table_md = "No data found."
    else:
        # Aggregate for Report "Missing Middle"
        duplex_stats = use_stats_df[use_stats_df['Use Type'].isin(DUPLEX_KEYS)].sum(numeric_only=True)
        multi_stats = use_stats_df[use_stats_df['Use Type'].isin(MULTI_FAMILY_KEYS)].sum(numeric_only=True)
        adu_stats = use_stats_df[use_stats_df['Use Type'].isin(ADU_KEYS)].sum(numeric_only=True)
        use_table_md = use_stats_df.to_markdown(index=False)

    # --- 5. Single Family Zoning Stat ---
    r1_count = len(df[df['zoning'] == 'R1'])
    total_res_count = len(df[df['is_residential_zone']])
    sf_zoning_pct = (r1_count / total_res_count * 100) if total_res_count > 0 else 0

    # --- 6. Report Generation ---
    report = f"""
# Detroit Preemption Impact Analysis

## 0. General Zoning Statistics
- **Percent of Residential Lots Zoned Single-Family (R1)**: {sf_zoning_pct:.1f}% ({r1_count:,} out of {total_res_count:,} residential lots)

## 1. Minimum Lot Size (1,500 sq ft Cap)
**Impact**: Thousands of small lots currently deemed "unbuildable" or "non-conforming" would be legalized.

- **Total Residential Parcels Legalized**: {lot_summary_res['Legalized_By_State'].sum():,}
- **Remaining Too Small (< 1,500 sq ft)**: {lot_summary_res['Violating_State_Cap'].sum():,}

### Breakdown by District (Residential)
{lot_summary_res.to_markdown()}

## 2. Minimum Dwelling Size (500 sq ft Cap)
*Assumption: Current effective minimum is ~1,000 sq ft.*
**Impact**: Existing small starter homes are protected, and new ones legalized.

- **Existing Small Homes Protected (500-1000 sq ft)**: {dwelling_stats:,}
- **Homes Smaller than State Cap (< 500 sq ft)**: {dwelling_violating_proposed:,}

## 3. Missing Middle Housing (Use Code Legality)
**Impact**: Duplexes and Multi-family units currently existing in restrictive zones (Non-conforming) would likely be legalized/permitted by right.
*Note: This analysis checks if the specific Use Code of the parcel is allowed By-Right in its current Zoning District (Conditionals excluded).*

### Summary
- **Duplex/Two-Family Non-Conforming**: {int(duplex_stats['Non-Conforming (Use Violation)']):,} (out of {int(duplex_stats['Total Existing']):,} existing)
- **Multi-Family Non-Conforming**: {int(multi_stats['Non-Conforming (Use Violation)']):,} (out of {int(multi_stats['Total Existing']):,} existing)
- **ADU (Carriage House) Non-Conforming**: {int(adu_stats['Non-Conforming (Use Violation)']):,} (out of {int(adu_stats['Total Existing']):,} existing)

### Detailed Breakdown by Use Type
{use_table_md}

"""
    print(report)
    
    with open('preemption_analysis_report.md', 'w') as f:
        f.write(report)
    
    # detailed csv for checking
    print("Saving detailed sample...")
    df.head(100).to_csv('analysis_sample.csv', index=False)

if __name__ == "__main__":
    analyze_preemption()
