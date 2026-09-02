"""Add neighborhood names to district tracts.

Reads:
    output/district_<N>_tracts.gpkg
    --source PATH/URL  (default: Detroit Open Data 'Current City of Detroit
                        Neighborhoods' FeatureServer endpoint)
    --overrides PATH   (default: data/tract_name_overrides.json, optional)

Writes:
    output/district_<N>_tracts.gpkg (in place, with neighborhood_name +
                                     naming_source columns added)
    output/district_<N>_tract_names.csv

Usage:
    python pipelines/legislative-district/name_tracts.py --district 9
"""

import argparse
from pathlib import Path

import geopandas as gpd

from strongtowns_data.legislative.tract_naming import (
    load_overrides, name_tracts,
)


# Detroit's official neighborhood polygons via ArcGIS FeatureServer.
DEFAULT_NEIGHBORHOODS_URL = (
    "https://services2.arcgis.com/qvkbeam7Wirps6zC/ArcGIS/rest/services/"
    "Current_City_of_Detroit_Neighborhoods/FeatureServer/0/query"
    "?where=1%3D1&outFields=*&outSR=4326&f=geojson"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--district', type=int, default=9)
    parser.add_argument(
        '--source', default=DEFAULT_NEIGHBORHOODS_URL,
        help='URL or local path to neighborhood polygons GeoJSON.',
    )
    parser.add_argument(
        '--overrides', default='data/tract_name_overrides.json',
        help='JSON dict {GEOID: name} of manual overrides (optional).',
    )
    parser.add_argument('--input-dir', default='./output')
    parser.add_argument('--output-dir', default='./output')
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    tracts_path = in_dir / f"district_{args.district}_tracts.gpkg"
    print(f"Loading tracts from {tracts_path}...")
    tracts = gpd.read_file(tracts_path)

    print(f"Loading neighborhoods from {args.source[:80]}...")
    neighborhoods = gpd.read_file(args.source)
    print(f"  {len(neighborhoods):,} neighborhood polygons")

    overrides = load_overrides(args.overrides)
    if overrides:
        print(f"  {len(overrides)} manual overrides loaded")

    names = name_tracts(tracts, neighborhoods, overrides=overrides)
    sources = names['naming_source'].value_counts().to_dict()
    print(f"\nNamed {len(names)} tracts ({sources})")
    print(names[['GEOID', 'neighborhood_name', 'naming_source']].to_string(index=False))

    # Drop any pre-existing name columns so re-runs are idempotent.
    drop_cols = [c for c in ('neighborhood_name', 'naming_source') if c in tracts.columns]
    if drop_cols:
        tracts = tracts.drop(columns=drop_cols)

    tracts_with_names = tracts.merge(
        names[['GEOID', 'neighborhood_name', 'naming_source']],
        on='GEOID', how='left',
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tracts_with_names.to_file(out_dir / f"district_{args.district}_tracts.gpkg", driver='GPKG')
    names.to_csv(out_dir / f"district_{args.district}_tract_names.csv", index=False)
    print(f"\nUpdated {tracts_path}")
    print(f"Wrote   {out_dir / f'district_{args.district}_tract_names.csv'}")


if __name__ == '__main__':
    main()
