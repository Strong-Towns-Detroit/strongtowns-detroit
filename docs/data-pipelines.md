# Reproducible data pipelines

`strongtowns-data` builds validated data inputs for `strongtowns-graphics`.

```bash
uv sync --extra dev
uv run strongtowns-data list
uv run strongtowns-data graph
uv run strongtowns-data status
uv run strongtowns-data verify detroit.parcels.raw
uv run strongtowns-data build
```

`build` is offline and consumes promoted snapshots only. Acquisition is always
explicit; commands that write to a provider are dry-run without `--apply`:

```bash
uv run strongtowns-data fetch detroit-parcels-source
uv run strongtowns-data fetch detroit-parcels-source --apply
uv run strongtowns-data fetch traveltime-smoke-results --apply --allow-paid
```

## Contracts and snapshots

Each dataset has a versioned contract, immutable snapshots, and an atomic
`PROMOTED.json` pointer. Manifests bind artifacts to schemas, parent hashes,
producer commits, parameters, counts, CRS, sizes, and SHA-256 hashes.

Dirty-code runs may stage diagnostics with `--no-promote`, but cannot promote.
Legacy provenance stays explicitly null. `verify` checks artifacts, schemas,
counts, and parent chains recursively. Legacy import measures source rows or
files before registration and fails on a baseline mismatch.

Canonical tabular geography is GeoParquet. Raw PDFs, JSON, HTML, images, GTFS,
and graphs retain their original formats and receive format-specific checks.

## Adding a pipeline

1. Define its `DatasetContract` and `DataAsset`.
2. Write a builder that reads `PipelineContext` inputs and writes only to its
   assigned staging directories.
3. Return `BuildMetadata` for every output.
4. Register it with `@data_pipeline("stable-name")` through
   `strongtowns-data.toml` or the `strongtowns.data_pipelines` entry-point group.
5. Test valid fixtures, rejection paths, lineage, and corruption.

Commands accept registered identities, not arbitrary production input paths.

## Archive

Large immutable sources may be archived to private R2. Snapshot payloads under
`data/sources/` are ignored by Git; their manifests and promoted pointers are
versionable.

```bash
uv run strongtowns-data archive status --tier critical --tier source
uv run strongtowns-data archive push --tier critical --tier source
uv run strongtowns-data archive push --tier critical --tier source --apply
uv run strongtowns-data archive pull --tier critical --tier source --apply
```

See [DATA_ARCHIVE.md](../scripts/DATA_ARCHIVE.md) for recovery setup.

## Query catalog

The DuckDB catalog is a materialized, read-only mirror; it never writes back to
canonical data.

```bash
uv run strongtowns-data build detroit-query-catalog
uv run strongtowns-data catalog inspect detroit.query.catalog
uv run strongtowns-data catalog query detroit.query.catalog \
  --sql "SELECT count(*) FROM parcels"
uv run --extra notebooks marimo edit notebooks/data_catalog.py
```

Queries permit one `SELECT` with external access and automatic extension
installation disabled. See [nonprofit-data-access.md](nonprofit-data-access.md)
before adding remote publication.

## Routing review

```bash
uv run strongtowns-data review export
uv run strongtowns-data review import --no-promote
```

Imports reject stale parents, unknown or duplicate anchors, invalid decisions,
missing reviewers, and invalid timestamps.
