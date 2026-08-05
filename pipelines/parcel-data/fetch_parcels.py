"""Fetch Detroit parcel data (GeoJSON + CSV) from the city's open data portal."""

import argparse
import logging
from pathlib import Path

from strongtowns_detroit.parcels.fetcher import fetch_geojson, fetch_csv, query_to_geojson

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    parser = argparse.ArgumentParser(description="Download Detroit parcel data")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to save files (default: current directory)",
    )
    parser.add_argument(
        "--geojson-only", action="store_true", help="Only download GeoJSON"
    )
    parser.add_argument(
        "--csv-only", action="store_true", help="Only download CSV"
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="SQL WHERE clause for filtered FeatureServer query, "
        "e.g. \"zoning_district='R1'\"",
    )
    args = parser.parse_args()

    if args.query:
        dest = args.output_dir / "Parcels_filtered.geojson"
        print(f"Running filtered query: {args.query}")
        query_to_geojson(dest, where=args.query)
        print(f"Done → {dest}")
        return

    if not args.csv_only:
        geojson_path = args.output_dir / "Parcels.geojson"
        print(f"Fetching GeoJSON → {geojson_path}")
        fetch_geojson(geojson_path)

    if not args.geojson_only:
        csv_path = args.output_dir / "parcel-data.csv"
        print(f"Fetching CSV → {csv_path}")
        fetch_csv(csv_path)

    print("Done.")


if __name__ == "__main__":
    main()
