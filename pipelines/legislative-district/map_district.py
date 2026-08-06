"""Render a multi-panel choropleth map deck for a state house district.

Reads outputs of fetch_district.py and writes:
    output/district_<N>_panels.png

Usage:
    python pipelines/legislative-district/map_district.py --district 9
"""

import argparse
from pathlib import Path

import geopandas as gpd

from strongtowns_detroit.legislative.maps import (
    render_district_panels,
    save_figure,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--district', type=int, default=9)
    parser.add_argument('--input-dir', default='./output')
    parser.add_argument('--output-dir', default='./output')
    parser.add_argument('--dpi', type=int, default=150)
    parser.add_argument(
        '--geography-dir',
        default='./pipelines/housingDataAnalysis/street_simplification/output',
        help='Directory with detroit_water.gpkg / detroit_network_basic.gpkg',
    )
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    boundary = gpd.read_file(in_dir / f"district_{args.district}_boundary.gpkg")
    tracts = gpd.read_file(in_dir / f"district_{args.district}_tracts.gpkg")

    streets_path = in_dir / f"district_{args.district}_streets.gpkg"
    water_path = in_dir / f"district_{args.district}_water.gpkg"
    streets = gpd.read_file(streets_path) if streets_path.exists() else None
    water = gpd.read_file(water_path) if water_path.exists() else None

    fig = render_district_panels(
        tracts, boundary,
        title=f"Michigan State House District {args.district} — ACS 5-year tract data",
        geography_dir=args.geography_dir,
        streets=streets,
        water=water,
    )

    out_path = Path(args.output_dir) / f"district_{args.district}_panels.png"
    save_figure(fig, out_path, dpi=args.dpi)
    print(f"Wrote {out_path}")


if __name__ == '__main__':
    main()
