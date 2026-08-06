"""Render a stylized locator map of the district for use on a campaign website.

Reads:
    output/district_<N>_boundary.gpkg
    output/district_<N>_cities.gpkg   (optional, from fetch_district_streets)
    output/district_<N>_streets.gpkg  (optional)
    output/district_<N>_water.gpkg    (optional)

Writes:
    output/district_<N>_locator.png

Usage:
    python pipelines/legislative-district/make_locator_map.py --district 9
"""

import argparse
from pathlib import Path

import geopandas as gpd

from strongtowns_detroit.legislative.maps import render_locator_map, save_figure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--district', type=int, default=9)
    parser.add_argument('--input-dir', default='./output')
    parser.add_argument('--output-dir', default='./output')
    parser.add_argument('--dpi', type=int, default=200)
    parser.add_argument('--district-color', default='#0C2340',
                        help='Fill color for the district (hex).')
    parser.add_argument('--title', default=None)
    parser.add_argument('--subtitle', default=None)
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    boundary = gpd.read_file(in_dir / f"district_{args.district}_boundary.gpkg")

    def _opt(name):
        path = in_dir / f"district_{args.district}_{name}.gpkg"
        return gpd.read_file(path) if path.exists() else None

    cities = _opt('cities')
    streets = _opt('streets')
    water = _opt('water')

    title = args.title or f"Michigan State House District {args.district}"
    subtitle = args.subtitle or "Detroit · Hamtramck · Highland Park · Grosse Pointe Park"

    fig = render_locator_map(
        boundary,
        cities=cities, streets=streets, water=water,
        title=title, subtitle=subtitle,
        district_color=args.district_color,
    )

    out_path = Path(args.output_dir) / f"district_{args.district}_locator.png"
    save_figure(fig, out_path, dpi=args.dpi)
    print(f"Wrote {out_path}")


if __name__ == '__main__':
    main()
