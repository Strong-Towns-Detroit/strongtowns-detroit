"""Build a self-contained interactive HTML map for the district.

Reads:
    output/district_<N>_boundary.gpkg
    output/district_<N>_tracts.gpkg

Writes:
    output/district_<N>_explorer.html

Usage:
    python pipelines/legislative-district/make_interactive_map.py --district 9
"""

import argparse
from pathlib import Path

import geopandas as gpd

from strongtowns_detroit.legislative.interactive import build_interactive_html


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--district', type=int, default=9)
    parser.add_argument('--input-dir', default='./output')
    parser.add_argument('--output-dir', default='./output')
    parser.add_argument('--title', default=None)
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    boundary = gpd.read_file(in_dir / f"district_{args.district}_boundary.gpkg")
    tracts = gpd.read_file(in_dir / f"district_{args.district}_tracts.gpkg")

    precincts_path = in_dir / f"district_{args.district}_precincts.gpkg"
    precincts = gpd.read_file(precincts_path) if precincts_path.exists() else None
    if precincts is not None:
        print(f"Including {len(precincts)} precincts from {precincts_path}")
    else:
        print("No precincts.gpkg found — skipping Precincts tab")

    html = build_interactive_html(
        tracts, boundary,
        district_number=args.district,
        title=args.title,
        precincts=precincts,
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"district_{args.district}_explorer.html"
    out_path.write_text(html, encoding='utf-8')

    size_kb = out_path.stat().st_size / 1024
    print(f"Wrote {out_path} ({size_kb:,.0f} KB)")
    print(f"Open with: open {out_path}")


if __name__ == '__main__':
    main()
