"""Fetch ACS data and boundary for a Michigan state house district.

Outputs:
    output/district_<N>_boundary.gpkg
    output/district_<N>_tracts.gpkg
    output/district_<N>_summary.csv

Usage:
    python pipelines/legislative-district/fetch_district.py --district 9
"""

import argparse
from pathlib import Path

from strongtowns_data.legislative.fetcher import fetch_district_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--district', type=int, default=9, help='State house district number')
    parser.add_argument('--state', default='26', help='State FIPS (default 26 = MI)')
    parser.add_argument('--year', type=int, default=2024, help='ACS 5-year endyear (2024 = 2020-2024)')
    parser.add_argument('--cache-dir', default='./cache', help='Cache directory')
    parser.add_argument('--output-dir', default='./output', help='Output directory')
    parser.add_argument(
        '--exclude', nargs='+', default=[],
        help='Tract GEOIDs to exclude from this district (manual override).',
    )
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    district, tracts, summary = fetch_district_data(
        district_number=args.district,
        state_fips=args.state,
        year=args.year,
        cache_dir=args.cache_dir,
        exclude_geoids=set(args.exclude) if args.exclude else None,
    )

    boundary_path = out / f"district_{args.district}_boundary.gpkg"
    tracts_path = out / f"district_{args.district}_tracts.gpkg"
    summary_path = out / f"district_{args.district}_summary.csv"

    district.to_file(boundary_path, driver='GPKG')
    tracts.to_file(tracts_path, driver='GPKG')
    summary.to_csv(summary_path, index=False)

    print(f"\nWrote:\n  {boundary_path}\n  {tracts_path}\n  {summary_path}")
    print(f"\nDistrict summary (HD-{args.district}):")
    print(summary.T.to_string(header=False))


if __name__ == '__main__':
    main()
