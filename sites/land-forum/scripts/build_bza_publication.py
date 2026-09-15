#!/usr/bin/env python3
"""Build the pinned BZA publication offline; no implicit acquisition."""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / 'projects/graphics')]
from atlas_inputs import resolve_inputs
from build_bza_data import build
from strongtowns_data import bza


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=HERE.parent / 'public/data')
    args = parser.parse_args()
    pin = json.loads((HERE.parent / 'bza-release.lock.json').read_text())
    manifest_path = args.release_directory / 'bza-manifest.json'
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != pin['manifest_sha256']:
        raise ValueError('Release manifest does not match the publication pin')
    dataset = bza.open(directory=args.release_directory)
    if dataset.manifest['version'] != pin['version']:
        raise ValueError('Unexpected BZA release')
    requirements = {
        'roads': ('detroit.base-units.streets.raw', 'raw.geojson'),
        'boundary': ('detroit.osm.basemap.raw', 'detroit_boundary.geojson'),
        'water': ('detroit.osm.basemap.raw', 'detroit_water.geojson'),
    }
    inputs, metadata = resolve_inputs(ROOT / 'strongtowns-data.lock.json', requirements=requirements)
    for name, filename in {'histories':'case_histories.csv', 'occurrences':'case_occurrences.csv', 'applications':'atlas_applications.csv', 'sites':'map_sites.gpkg'}.items():
        inputs[name] = args.release_directory / filename
    metadata['detroit.bza.release'] = {'snapshot_id': pin['version'], 'manifest_sha256': pin['manifest_sha256'], 'created_at': dataset.manifest['coverage_end']}
    inputs['source_links'] = args.release_directory / 'provenance/source-reconciliation.json'
    # The existing consumer creates case records and the immutable chart bundle.
    build(inputs, metadata, args.output, studio_only=True)
    latest = json.loads((args.output / 'bza-studio/latest.json').read_text())
    bundle = json.loads((args.output / f"bza-studio/{latest['bundle']}.json").read_text())
    spec = importlib.util.spec_from_file_location('bza_cases_map', ROOT / 'projects/graphics/src/graphics/bza_cases_map.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Context:
        def input(self, name): return inputs[name]
    graphic = module.build(Context(), include_scene=True)['bza-cases-map']
    scene = graphic.metadata['map_scene']
    mapped = {s['id'] for s in scene['symbols']}
    if (len(bundle['cases']), sum(len(c['hearings']) for c in bundle['cases']), len(mapped)) != (417,509,408):
        raise ValueError('BZA 1.1.0 totals differ from reviewed release')
    if mapped != {c['id'] for c in bundle['cases'] if c['mapped']}:
        raise ValueError('Scene and case locations disagree')
    payload = (json.dumps({'version':1,'bundle':latest['bundle'],'scene':scene}, sort_keys=True,separators=(',',':'))+'\n').encode()
    identifier = hashlib.sha256(payload).hexdigest()
    destination = args.output / 'bza-maps'
    destination.mkdir(parents=True,exist_ok=True)
    target = destination / f'{identifier}.json'
    if target.exists() and target.read_bytes() != payload: raise ValueError('Corrupt immutable map')
    target.write_bytes(payload)
    (destination/'latest.json').write_text(json.dumps({'version':1,'map':identifier})+'\n')
    print(f'Publication {identifier}: {len(mapped)} mapped cases; {len(payload):,} bytes')

if __name__ == '__main__': main()
