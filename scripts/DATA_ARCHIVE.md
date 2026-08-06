# Data archive

Durable storage for the repository data that git cannot hold and a build cannot
rebuild. Backed by a private Cloudflare R2 bucket.

This is the complement of [`CLEANUP_REGENERABLE_DATA.md`](CLEANUP_REGENERABLE_DATA.md):
that script deletes what is reproducible, this one preserves what is not.
Together they are the reason the working tree can be ~11 GB while the repository
stays at 37 MB.

## Why R2 rather than git

Two `base-units-geometry` GeoJSON files (251 MB and 192 MB) exceed GitHub's
100 MB per-file hard limit, and the full data footprint is about 1.8 GB. R2 was
chosen over Google Cloud Storage because egress is free — pulling a 615 MB
parcel file back down costs nothing — and because the Land Forum site already
runs as a Cloudflare Worker under the same account.

## Tiers

Run `python scripts/data_archive.py status --tier critical --tier source --tier deliverable`
for current sizes.

### `critical` — impossible to reproduce (~196 MB)

Archive this even if you archive nothing else.

| Asset | Why |
|---|---|
| `resources/municode` | Point-in-time Chapter 50 snapshot (`2025-10-09_job-429936`, Supplement 4). Municode is versioned and mutable; a later scrape returns a *different* ordinance, which would silently invalidate every source-span citation in the compiled rule set. |
| `pipelines/zoning/bza_dataset_gemini` | Vision-model extraction across ~800 BZA documents. Real Gemini API spend to regenerate. |
| `pipelines/zoning/bza_minutes` | Scraped BZA minutes PDFs. The city rotates its document listing, so older minutes disappear from the source. |

### `source` — re-downloadable, but dated (~1.2 GB)

Public data that upstream overwrites in place. Keeping a copy is what makes a
past analysis reproducible rather than merely re-runnable.

`Parcels.geojson`, `parcel-data.csv`, the consolidated Base Units layers, and
the HUD 2026 QCT designations.

### `deliverable` — rendered output (~428 MB)

`conference-canonical` and `conference-print`. Reproducible from the build
scripts *only while their inputs survive*, which is what the tiers above protect.

## One-time setup

1. **Create the bucket.** Cloudflare dashboard → R2 → Create bucket, named
   `strongtowns-detroit-data`, under the **Strong Towns Detroit** account rather
   than a personal one. Leave public access disabled.

2. **Create an API token.** R2 → Manage API tokens → Create token, permission
   **Object Read & Write**, scoped to that bucket only. Copy the Access Key ID
   and Secret Access Key — the secret is shown once.

3. **Record the credentials** in `.env` (already gitignored):

   ```
   R2_ACCOUNT_ID=...          # dashboard home, right sidebar
   R2_ACCESS_KEY_ID=...
   R2_SECRET_ACCESS_KEY=...
   R2_BUCKET=strongtowns-detroit-data
   ```

4. **Install the client:**

   ```bash
   pip install 'strongtowns-detroit[archive]'
   ```

## Usage

Every command that writes is dry-run by default; add `--apply` to act.
`--tier` is repeatable and defaults to `critical`.

```bash
python scripts/data_archive.py status --tier critical --tier source
python scripts/data_archive.py push                      # preview critical tier
python scripts/data_archive.py push --apply              # upload it
python scripts/data_archive.py pull --apply              # restore what is missing
```

`push` skips files whose SHA-256 already matches the manifest, so re-running it
is cheap. `pull` restores anything missing *or* altered locally, and fails loudly
on a checksum mismatch after download.

## Derived parcel data is deliberately not archived

The augmented parcel tables are large (`parcels_with_compliance.gpkg` alone is
653 MB) and all of them are rebuildable, so none are archived. "Rebuildable" is
only true while the inputs survive, so the rebuild chains are recorded rather
than assumed:

```bash
python scripts/data_archive.py recipes
```

That prints each derived artifact, the exact command that rebuilds it, and
whether every input is still present locally or safe in the archive. It reports
`NOT REBUILDABLE` if a chain has been broken by a cleanup.

The chains bottom out at the `source` tier, which is why `Parcels.geojson` and
`parcel-data.csv` are archived even though they are nominally re-downloadable.

### Two traps found when auditing these chains

**`parcel-data-cleaned.csv` is not reproducible.** No script writes it — it is a
legacy hand-cleaned artifact with a schema that differs from the current
`parcel-data.csv`. `merge_and_calculate.py` and `calculate_buildable.py` prefer
`parcel-data.csv` and fall back to it only when that file is absent. The
`standard` cleanup profile removes it, guarded on `parcel-data.csv` existing,
which is correct — but it is a one-way door. Anything still reading the cleaned
file directly must be migrated first.

**The street-simplification basemaps are cleanup targets.** `detroit_boundary.geojson`
and `detroit_water.geojson` are deleted by the `standard` profile as derived
exports, but the LIHTC map board reads them and re-deriving them requires an
OSMnx network pull. They are 2.4 MB combined, so they are now archived in the
`source` tier rather than left to chance.

## The manifest

`scripts/data_archive_manifest.json` records the path, size, and SHA-256 of every
archived object. It is committed to git deliberately: it is small, and it lets
anyone verify which snapshot of the data an analysis was run against without
needing bucket credentials.

Objects are keyed `archive/v1/<repo-relative-path>`, so the bucket layout mirrors
the repository and the `v1` prefix leaves room to re-cut the archive later
without destroying the current one.

## Restoring on a fresh machine

```bash
git clone <repo> && cd strongtowns-detroit
pip install -e '.[archive]'
cp .env.example .env    # fill in the R2 values
python scripts/data_archive.py pull --tier critical --tier source --apply
```
