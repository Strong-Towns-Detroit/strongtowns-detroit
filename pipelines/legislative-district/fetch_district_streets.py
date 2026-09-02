"""Fetch OSM streets, water, and city boundaries for HD-9-area municipalities.

Outputs:
    output/district_<N>_streets.gpkg
    output/district_<N>_water.gpkg
    output/district_<N>_cities.gpkg

Usage:
    python pipelines/legislative-district/fetch_district_streets.py --district 9
"""

import argparse
from pathlib import Path

from strongtowns_data.legislative.osm import (
    fetch_place_boundaries, fetch_streets, fetch_water, save_layer,
)


# Cities that intersect or fully contain MI HD-9.
DEFAULT_PLACES = [
    "Detroit, Michigan, USA",
    "Hamtramck, Michigan, USA",
    "Highland Park, Michigan, USA",
    "Grosse Pointe Park, Michigan, USA",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--district', type=int, default=9)
    parser.add_argument('--output-dir', default='./output')
    parser.add_argument(
        '--places', nargs='+', default=DEFAULT_PLACES,
        help='Municipalities to fetch (full OSM names).',
    )
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Fetching boundaries for {len(args.places)} places...")
    cities = fetch_place_boundaries(args.places)
    save_layer(cities, out / f"district_{args.district}_cities.gpkg")

    print("Fetching street network...")
    streets = fetch_streets(args.places)
    print(f"  {len(streets):,} street edges")
    save_layer(streets, out / f"district_{args.district}_streets.gpkg")

    print("Fetching water features...")
    water = fetch_water(args.places)
    print(f"  {len(water):,} water polygons")
    save_layer(water, out / f"district_{args.district}_water.gpkg")

    print("\nDone.")


if __name__ == '__main__':
    main()
