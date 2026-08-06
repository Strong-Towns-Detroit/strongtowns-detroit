#!/usr/bin/env python3
"""
Analyze HPMS data for road overcapacity in Detroit.

This script loads downloaded HPMS GeoJSON data and computes
volume-to-capacity (V/C) ratios to identify overbuilt roads.

Usage:
    python3 analyze_overcapacity.py hpms_metro_detroit_2022.geojson

Requirements:
    pip install geopandas pandas
"""
import sys
import os
import json

try:
    import geopandas as gpd
    import pandas as pd
except ImportError:
    print("Required packages: pip install geopandas pandas")
    sys.exit(1)

# ── Per-Lane Hourly Capacity by Functional Class ─────────────────────────────
# Based on Highway Capacity Manual (HCM) general guidelines.
# These are approximate service flow rates at LOS C/D threshold.

CAPACITY_PER_LANE_PER_HOUR = {
    1: 2200,  # Interstate
    2: 2000,  # Principal Arterial - Other Freeways/Expressways
    3: 1800,  # Principal Arterial - Other
    4: 1600,  # Minor Arterial
    5: 1400,  # Major Collector
    6: 1200,  # Minor Collector
    7: 1000,  # Local
}

FUNCTIONAL_CLASS_NAMES = {
    1: "Interstate",
    2: "Freeways/Expressways",
    3: "Principal Arterial",
    4: "Minor Arterial",
    5: "Major Collector",
    6: "Minor Collector",
    7: "Local",
}

# Default K-factor (peak hour proportion of AADT) if not in data
DEFAULT_K_FACTOR = 0.09  # ~9% is typical urban default

# Default directional factor
DEFAULT_DIR_FACTOR = 0.55  # 55/45 split is typical


def load_data(filepath):
    """Load HPMS GeoJSON into a GeoDataFrame."""
    print(f"Loading {filepath}...")
    gdf = gpd.read_file(filepath)
    print(f"  Loaded {len(gdf)} road segments")
    print(f"  Columns: {list(gdf.columns)}")
    return gdf


def find_field(gdf, candidates):
    """Find the first matching column name from a list of candidates."""
    for c in candidates:
        for col in gdf.columns:
            if col.upper() == c.upper():
                return col
    return None


def compute_vc_ratios(gdf):
    """Compute volume-to-capacity ratios for each road segment."""

    # Find relevant fields (HPMS field names can vary by year/source)
    aadt_field = find_field(gdf, ["AADT", "AADT_VN", "AADT_TOTAL", "ADT"])
    lanes_field = find_field(gdf, [
        "THROUGH_LANES", "THROUGH_LNS", "THRU_LANES",
        "NUM_LANES", "LANES", "LANE_COUNT",
    ])
    fsystem_field = find_field(gdf, [
        "F_SYSTEM", "FUNC_SYS", "FUNCTIONAL_SYSTEM",
        "FUNC_CLASS", "FUNCTIONAL_CLASS",
    ])
    k_factor_field = find_field(gdf, ["K_FACTOR", "KFACTOR", "K_FAC"])
    dir_factor_field = find_field(gdf, ["DIR_FACTOR", "D_FACTOR", "DFACTOR"])
    length_field = find_field(gdf, [
        "SECTION_LENGTH", "SEC_LENGTH", "LENGTH",
        "SECTION_LEN", "SHAPE_LENGTH",
    ])

    print()
    print("Field mapping:")
    print(f"  AADT: {aadt_field}")
    print(f"  Through Lanes: {lanes_field}")
    print(f"  Functional System: {fsystem_field}")
    print(f"  K-Factor: {k_factor_field}")
    print(f"  Dir Factor: {dir_factor_field}")
    print(f"  Section Length: {length_field}")

    if not aadt_field or not lanes_field:
        print()
        print("ERROR: Cannot find AADT or lane count fields.")
        print("Available columns:", list(gdf.columns))
        sys.exit(1)

    # Create working copy with standardized names
    df = gdf.copy()
    df["_aadt"] = pd.to_numeric(df[aadt_field], errors="coerce")
    df["_lanes"] = pd.to_numeric(df[lanes_field], errors="coerce")

    if fsystem_field:
        df["_fsystem"] = pd.to_numeric(df[fsystem_field], errors="coerce")
    else:
        df["_fsystem"] = 4  # Default to minor arterial

    if k_factor_field:
        df["_k_factor"] = pd.to_numeric(df[k_factor_field], errors="coerce").fillna(DEFAULT_K_FACTOR)
    else:
        df["_k_factor"] = DEFAULT_K_FACTOR

    if dir_factor_field:
        df["_dir_factor"] = pd.to_numeric(df[dir_factor_field], errors="coerce").fillna(DEFAULT_DIR_FACTOR)
    else:
        df["_dir_factor"] = DEFAULT_DIR_FACTOR

    if length_field:
        df["_length"] = pd.to_numeric(df[length_field], errors="coerce")
    else:
        df["_length"] = 0

    # Filter out segments without usable data
    valid = df["_aadt"].notna() & (df["_aadt"] > 0) & df["_lanes"].notna() & (df["_lanes"] > 0)
    df_valid = df[valid].copy()
    print(f"\n  Valid segments (with AADT and lane data): {len(df_valid)} of {len(df)}")

    # Compute capacity per direction
    # Capacity = lanes_per_direction * capacity_per_lane_per_hour
    # Daily capacity (rough) = hourly_capacity / K_factor
    # Directional AADT = AADT * dir_factor

    df_valid["_capacity_per_lane_hr"] = df_valid["_fsystem"].map(CAPACITY_PER_LANE_PER_HOUR).fillna(1600)

    # For two-way roads, lanes per direction = total lanes / 2
    # For one-way roads, all lanes are in one direction
    # Without FACILITY_TYPE, assume two-way
    facility_field = find_field(df_valid, ["FACILITY_TYPE", "FAC_TYPE"])
    if facility_field:
        # Facility type: 1=one-way, 2=two-way
        df_valid["_lanes_per_dir"] = df_valid.apply(
            lambda r: r["_lanes"] if r.get(facility_field) == 1 else r["_lanes"] / 2,
            axis=1,
        )
    else:
        df_valid["_lanes_per_dir"] = df_valid["_lanes"] / 2

    # Directional peak hour volume
    df_valid["_peak_hr_vol"] = df_valid["_aadt"] * df_valid["_k_factor"] * df_valid["_dir_factor"]

    # Directional peak hour capacity
    df_valid["_peak_hr_cap"] = df_valid["_lanes_per_dir"] * df_valid["_capacity_per_lane_hr"]

    # V/C ratio
    df_valid["vc_ratio"] = df_valid["_peak_hr_vol"] / df_valid["_peak_hr_cap"]

    # Classify
    def classify_vc(vc):
        if vc < 0.3:
            return "Severely Overcapacity"
        elif vc < 0.5:
            return "Overcapacity"
        elif vc < 0.7:
            return "Moderately Utilized"
        elif vc < 0.85:
            return "Well Utilized"
        elif vc <= 1.0:
            return "Near Capacity"
        else:
            return "Congested"

    df_valid["vc_category"] = df_valid["vc_ratio"].apply(classify_vc)

    # Excess lanes estimate
    # Needed lanes (per direction) = peak_hr_vol / capacity_per_lane_hr (rounded up)
    import math
    df_valid["_needed_lanes_dir"] = df_valid.apply(
        lambda r: max(1, math.ceil(r["_peak_hr_vol"] / r["_capacity_per_lane_hr"])),
        axis=1,
    )
    df_valid["_needed_lanes_total"] = df_valid["_needed_lanes_dir"] * 2
    df_valid["excess_lanes"] = (df_valid["_lanes"] - df_valid["_needed_lanes_total"]).clip(lower=0)

    if length_field:
        df_valid["excess_lane_miles"] = df_valid["excess_lanes"] * df_valid["_length"]

    return df_valid


def print_summary(df):
    """Print summary statistics of overcapacity analysis."""
    print()
    print("=" * 70)
    print("OVERCAPACITY ANALYSIS SUMMARY")
    print("=" * 70)

    # Overall V/C distribution
    print("\nV/C Ratio Distribution:")
    print("-" * 50)
    cats = df["vc_category"].value_counts()
    total = len(df)
    for cat in [
        "Severely Overcapacity", "Overcapacity", "Moderately Utilized",
        "Well Utilized", "Near Capacity", "Congested",
    ]:
        count = cats.get(cat, 0)
        pct = count / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {cat:25s}: {count:6d} ({pct:5.1f}%) {bar}")

    # By functional class
    print("\nV/C Ratio by Functional Class:")
    print("-" * 70)
    for fsys in sorted(df["_fsystem"].dropna().unique()):
        fsys_int = int(fsys)
        name = FUNCTIONAL_CLASS_NAMES.get(fsys_int, f"Unknown ({fsys_int})")
        subset = df[df["_fsystem"] == fsys]
        if len(subset) == 0:
            continue
        mean_vc = subset["vc_ratio"].mean()
        median_vc = subset["vc_ratio"].median()
        overcap = len(subset[subset["vc_ratio"] < 0.5])
        pct_overcap = overcap / len(subset) * 100
        print(f"  {name:30s}: n={len(subset):5d}  mean V/C={mean_vc:.3f}  "
              f"median={median_vc:.3f}  overcap={pct_overcap:.0f}%")

    # Excess lanes summary
    if "excess_lane_miles" in df.columns and df["_length"].sum() > 0:
        total_lane_miles = (df["_lanes"] * df["_length"]).sum()
        excess_lane_miles = df["excess_lane_miles"].sum()
        print(f"\nTotal lane-miles analyzed: {total_lane_miles:,.1f}")
        print(f"Excess lane-miles (could be removed): {excess_lane_miles:,.1f}")
        print(f"Percentage excess: {excess_lane_miles / total_lane_miles * 100:.1f}%")

    # Top overcapacity segments
    print("\nTop 20 Most Overcapacity Segments (lowest V/C ratio with 4+ lanes):")
    print("-" * 70)
    wide_roads = df[(df["_lanes"] >= 4) & (df["vc_ratio"] < 0.5)].sort_values("vc_ratio")
    for _, row in wide_roads.head(20).iterrows():
        route_field = None
        for f in ["ROUTE_NAME", "ROUTE_ID", "ROUTE_NUMBER", "ROUTE_NUMB", "ROAD_NAME"]:
            if f in row.index and pd.notna(row.get(f)):
                route_field = f
                break
        route = row[route_field] if route_field else "Unknown"
        fsys_name = FUNCTIONAL_CLASS_NAMES.get(int(row["_fsystem"]), "?")
        print(f"  {route:30s}  Lanes={int(row['_lanes']):2d}  "
              f"AADT={int(row['_aadt']):7,d}  V/C={row['vc_ratio']:.3f}  "
              f"({fsys_name})")

    # Summary statistics
    print(f"\nOverall Statistics:")
    print(f"  Mean V/C ratio: {df['vc_ratio'].mean():.3f}")
    print(f"  Median V/C ratio: {df['vc_ratio'].median():.3f}")
    print(f"  Segments with V/C < 0.3: {len(df[df['vc_ratio'] < 0.3]):,d} "
          f"({len(df[df['vc_ratio'] < 0.3]) / len(df) * 100:.1f}%)")
    print(f"  Segments with V/C < 0.5: {len(df[df['vc_ratio'] < 0.5]):,d} "
          f"({len(df[df['vc_ratio'] < 0.5]) / len(df) * 100:.1f}%)")


def main():
    if len(sys.argv) < 2:
        # Look for any GeoJSON in the hpms directory
        hpms_dir = os.path.expanduser("~/strongtowns-detroit/data/traffic-volumes/hpms")
        geojsons = [f for f in os.listdir(hpms_dir) if f.endswith(".geojson")]
        if geojsons:
            filepath = os.path.join(hpms_dir, geojsons[0])
            print(f"Using: {filepath}")
        else:
            print("Usage: python3 analyze_overcapacity.py <hpms_data.geojson>")
            print(f"\nNo GeoJSON files found in {hpms_dir}")
            print("Run download_hpms.py first to download data.")
            sys.exit(1)
    else:
        filepath = sys.argv[1]

    gdf = load_data(filepath)
    result = compute_vc_ratios(gdf)
    print_summary(result)

    # Save results
    output_csv = filepath.replace(".geojson", "_overcapacity.csv")
    cols_to_save = [c for c in result.columns if not c.startswith("_") and c != "geometry"]
    result[cols_to_save].to_csv(output_csv, index=False)
    print(f"\nResults saved to: {output_csv}")


if __name__ == "__main__":
    main()
