# Repository cleanup inventory

The cleanup script is dry-run by default:

```bash
python scripts/cleanup_regenerable_data.py
```

It uses explicit targets and refuses to delete the repository root or a
safety-guarded duplicate when the retained replacement is absent.

## Profiles

### `safe`

Expected reclaim: approximately **2.4 GB** in the current workspace.

- two reproducible Python virtual environments with dependency manifests;
- Jupyter checkpoints;
- Python/test caches;
- Base Units page caches, but only when their consolidated GeoJSON exists.

It preserves all source datasets, consolidated Base Units layers, parcel
inputs, current compliance GeoPackage, network caches, and forum exports.

```bash
python scripts/cleanup_regenerable_data.py --profile safe --apply
```

### `standard`

Expected reclaim: approximately **4.9 GB** including `safe`.

It additionally removes legacy or duplicate parcel-analysis tables, derived
Base Units analysis outputs, and street-simplification intermediates. It
also removes the legacy parcel-pipeline virtual environment; that environment
has no dedicated lockfile and is therefore deliberately excluded from `safe`.
retains:

- `pipelines/parcel-data/Parcels.geojson`;
- `pipelines/parcel-data/parcel-data.csv`;
- `pipelines/parcel-data/parcels_with_compliance.gpkg`;
- consolidated Base Units address, street, and building files;
- downloaded routing/network caches;
- finished forum HTML, SVG, and PNG assets.

```bash
python scripts/cleanup_regenerable_data.py --profile standard
python scripts/cleanup_regenerable_data.py --profile standard --apply
```

### `aggressive`

Adds routing/OSM caches and rendered forum outputs. These are reproducible but
can be slow or require network/API access to rebuild. Use only after copying
any assets needed for the forum.

```bash
python scripts/cleanup_regenerable_data.py --profile aggressive
```

## Recommended sequence

1. Run the `standard` dry run and inspect every path.
2. Apply `safe` if immediate low-risk space is needed.
3. Apply `standard` after confirming no legacy parcel export is needed for
   manual comparison.
4. Avoid `aggressive` until final exhibit assets are backed up.
