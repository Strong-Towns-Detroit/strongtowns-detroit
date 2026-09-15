"""Export pinned OSM layers for legislative maps without fetching or building data.

Acquire hd9-osm-{boundaries,water,streets}-source in strongtowns-data and update
strongtowns-data.lock.json there before running this consumer export.
"""

import argparse
from pathlib import Path

from strongtowns_data import DataBuildSystem, DataLock, DataRepository
from strongtowns_data.legislative.osm import save_layer
from strongtowns_data.osm.basemaps import read_map_layers
from strongtowns_detroit.repositories import data_repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--district', type=int, default=9)
    parser.add_argument('--output-dir', type=Path, default=Path('./output'))
    parser.add_argument('--lock', type=Path, default=PROJECT_ROOT / 'strongtowns-data.lock.json')
    parser.add_argument('--repository', type=Path, default=data_repository())
    parser.add_argument('--region', default='hd9', help='Registered OSM region in the data lock.')
    args = parser.parse_args(argv)
    lock = DataLock.load(args.lock)
    repository = DataRepository(DataBuildSystem.find(args.repository))
    directories = {
        kind: repository.resolve(lock.asset(f'{args.region}.osm.{kind}.raw'))[0]
        for kind in ('boundaries', 'water', 'streets')
    }
    layers = read_map_layers(**directories)
    for kind, frame in layers.items():
        path = args.output_dir / f'district_{args.district}_{kind}.gpkg'
        save_layer(frame, path)
        print(f'Exported {len(frame):,} pinned {kind} records -> {path}')


if __name__ == '__main__':
    main()
