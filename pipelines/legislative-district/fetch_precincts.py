"""Fetch Detroit precincts + 2024 results, clip to a district.

Reads:
    output/district_<N>_boundary.gpkg

Writes:
    output/district_<N>_precincts.gpkg

Usage:
    python pipelines/legislative-district/fetch_precincts.py --district 9
"""

import argparse
from pathlib import Path

import geopandas as gpd

from strongtowns_detroit.legislative.precincts import fetch_district_precincts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--district', type=int, default=9)
    parser.add_argument('--cache-dir', default='./cache')
    parser.add_argument('--input-dir', default='./output')
    parser.add_argument('--output-dir', default='./output')
    parser.add_argument(
        '--exclude', nargs='+', type=int, default=[],
        help='Precinct numbers to exclude.',
    )
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    boundary = gpd.read_file(in_dir / f"district_{args.district}_boundary.gpkg")

    precincts = fetch_district_precincts(
        district=boundary,
        cache_dir=args.cache_dir,
        exclude_precincts=set(args.exclude) if args.exclude else None,
    )

    print(f"\n{len(precincts)} precincts in HD-{args.district}")
    matched = precincts['pres_total'].notna().sum()
    print(f"{matched}/{len(precincts)} have 2024 President results joined")

    if 'pres_dem_margin' in precincts.columns:
        margin = precincts['pres_dem_margin'].dropna()
        if len(margin):
            print(f"\n2024 President — D-margin range across precincts:")
            print(f"  median: {margin.median():.1f} pts")
            print(f"  mean:   {margin.mean():.1f} pts")
            print(f"  min:    {margin.min():.1f} pts")
            print(f"  max:    {margin.max():.1f} pts")
        turnout = precincts['turnout_pct'].dropna()
        if len(turnout):
            print(f"\nTurnout: median {turnout.median():.1f}%, "
                  f"range {turnout.min():.1f}% – {turnout.max():.1f}%")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"district_{args.district}_precincts.gpkg"
    precincts.to_file(out_path, driver='GPKG')
    print(f"\nWrote {out_path}")


if __name__ == '__main__':
    main()
