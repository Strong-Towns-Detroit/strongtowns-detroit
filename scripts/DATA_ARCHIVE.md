# Data archive

The private Cloudflare R2 archive stores immutable source evidence that is too
large for Git. It is part of the `strongtowns-data` contract system: archive
membership comes from registered `DataAsset` values, not a second hard-coded
list in a script.

Git retains each source snapshot's `manifest.json` and `PROMOTED.json` pointer.
R2 retains the payload as well. Derived GeoParquet and provider request ledgers
are rebuilt from promoted parents and are not archived unless their asset
contract explicitly assigns an archive tier.

## Tiers

- `critical`: mutable, unavailable, or costly evidence such as the point-in-time
  Municode corpus, BZA minutes and Gemini extraction, and provider responses.
- `source`: dated public inputs such as parcels, Base Units, assessment reports,
  QCT geography, and the OSM basemap.
- `deliverable`: irreplaceable published output, when one is registered.
- `none`: reproducible derived data; never sent to the archive.

Inspect the live catalog rather than relying on size estimates in documentation:

```bash
uv run strongtowns-data archive status --tier critical --tier source
```

## One-time setup

1. Create a private R2 bucket named `strongtowns-detroit-data` in the Strong
   Towns Detroit Cloudflare account.
2. Create an Object Read & Write token scoped only to that bucket.
3. Put the values below in the Git-ignored `.env` or process environment:

   ```text
   R2_ACCOUNT_ID=...
   R2_ACCESS_KEY_ID=...
   R2_SECRET_ACCESS_KEY=...
   R2_BUCKET=strongtowns-detroit-data
   ```

4. Install the locked environment with archive support:

   ```bash
   uv sync --locked --extra archive
   ```

## Push and restore

Transfers are dry-run by default. `--apply` is required for network mutation:

```bash
uv run strongtowns-data archive push --tier critical --tier source
uv run strongtowns-data archive push --tier critical --tier source --apply
uv run strongtowns-data archive pull --tier critical --tier source --apply
```

Push calculates every local SHA-256 first and updates
`scripts/data_archive_manifest.json` atomically only after all uploads succeed.
Pull downloads through a temporary file, verifies size and SHA-256, and only
then replaces the local path. Credentials are never written to a manifest.

The old `python scripts/data_archive.py status|push|pull` spelling remains a
compatibility wrapper around the same library implementation. Its `recipes`
subcommand describes pre-contract legacy rebuilds only; new pipelines belong in
the registered DAG shown by `strongtowns-data graph`.

## Fresh-machine recovery

```bash
git clone <repo> strongtowns-detroit
cd strongtowns-detroit
uv sync --locked --extra archive --extra dev
uv run strongtowns-data archive pull --tier critical --tier source --apply
uv run strongtowns-data verify detroit.parcels.raw \
  detroit.base-units.addresses.raw \
  detroit.base-units.streets.raw \
  detroit.base-units.buildings.raw
uv run strongtowns-data build canonical-detroit-parcels \
  canonical-detroit-base-units-addresses \
  canonical-detroit-base-units-streets \
  canonical-detroit-base-units-buildings
uv run strongtowns-data build detroit-routing-anchors
```

Offline `build` never downloads missing inputs. Public, credentialed, and paid
acquisition each require an explicit `fetch`; paid acquisition additionally
requires `--allow-paid`.
