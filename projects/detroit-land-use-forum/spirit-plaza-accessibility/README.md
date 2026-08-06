# Campus Martius multimodal accessibility

This is the reproducible analysis package for the first Detroit Land Use Forum
exhibit. It compares where a person can reach from Campus Martius in 15, 30, 45,
and 60 minutes by walking, scheduled public transit, and driving.

The frozen analytical contract is in [`spec.json`](spec.json). Do not quietly
change the date, direction, aggregation, origin, or transit definition between
modes. `feeds.json` is an input manifest, not yet a claim that every feed URL has
been resolved.

Archive and inspect the feeds with:

```bash
python projects/detroit-land-use-forum/spirit-plaza-accessibility/fetch_inputs.py
```

Add `--include-osm` only when ready for the much larger statewide Geofabrik
download. The resulting `input-report.json` records hashes and tests whether the
study date falls inside each schedule's broad calendar envelope. QLINE currently
requires special attention: its published URL responds, but the latest schedule
indexed by Transitland ends in 2025.

## Fast production path: TravelTime

Create a TravelTime trial/application, copy `.env.example` to the gitignored
repository-root `.env`, and replace the TravelTime placeholders. The runner loads
that file automatically; explicit shell environment variables take precedence.

```bash
cp .env.example .env
# Edit .env:
# TRAVELTIME_APP_ID=...
# TRAVELTIME_API_KEY=...

PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python \
  projects/detroit-land-use-forum/spirit-plaza-accessibility/traveltime_isochrones.py

PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python \
  projects/detroit-land-use-forum/spirit-plaza-accessibility/render_map.py \
  projects/detroit-land-use-forum/spirit-plaza-accessibility/output/traveltime_isochrones.geojson
```

The API runner caches each raw response. Walking and driving use the noon
departure. Transit requests all 13 exact departures from noon through 1 p.m. and
retains cells reached in at least seven. This is a median reachability surface;
TravelTime's `range` option is deliberately not used because it returns an
optimistic union.

The renderer clips the display to the union of Detroit's 2026 City Council
districts while leaving the raw routing results untouched. It produces standalone
HTML with inline GeoJSON and plain SVG—no map tiles, JavaScript library, or
network connection is required. Open it in a browser and print at 17×11 inches.
It uses the Strong Towns palette and the brand-guide-safe Georgia/Arial
typography preset.

Prepare the lightweight road reference layer once from the cached Detroit graph:

```bash
PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python \
  projects/detroit-land-use-forum/spirit-plaza-accessibility/prepare_road_context.py
```

The screen layout stacks large maps vertically. Print CSS places each mode on
its own 17×11 landscape sheet. Coordinates are projected with Web Mercator
rather than drawn directly in longitude/latitude, preventing Detroit from being
stretched east–west.

For sharing systems that block JavaScript in HTML attachments, export one
script-free asset per mode:

```bash
PYTHONPATH=src:projects/detroit-land-use-forum/spirit-plaza-accessibility \
  pipelines/housingDataAnalysis/.venv/bin/python \
  projects/detroit-land-use-forum/spirit-plaza-accessibility/export_mode_assets.py
```

This writes individual walking, public-transit, and driving files as
self-contained `.html`, static `.svg`, and 2800-pixel-wide `.png` files under
`output/share/`. Use `--png-width` to request a different raster size.

## Primary reproducible model

The defensible primary model remains R5:

1. Archive a regional OpenStreetMap `.osm.pbf`.
2. Resolve and archive all four current GTFS feeds listed in `feeds.json`.
3. Record download timestamps and SHA-256 hashes.
4. Confirm service is defined for 2026-07-29.
5. Use a 250 m Detroit-area destination grid and R5 `TravelTimeMatrix`.
6. Run walking, transit+walking, and driving for every five-minute departure.
7. Take the median travel time at each grid point, polygonize the four bands,
   and clip only the finished display to Detroit.

The runner implements those steps:

```bash
python -m pip install r5py

PYTHONPATH=projects/detroit-land-use-forum/spirit-plaza-accessibility \
  python projects/detroit-land-use-forum/spirit-plaza-accessibility/r5_isochrones.py \
  --pbf projects/detroit-land-use-forum/spirit-plaza-accessibility/inputs/michigan-latest.osm.pbf \
  --gtfs projects/detroit-land-use-forum/spirit-plaza-accessibility/inputs/*.zip \
  --boundary path/to/detroit-city-boundary.geojson
```

R5 is not currently installed in the project environment and the regional PBF
has not been archived, so the package does not pretend that this result already
exists. TravelTime supplies the time-critical challenger; R5 is the independently
reproducible edition.

## Validation

Google Routes is reserved for a small destination audit. Store only the
comparison table needed for review, subject to Google's current terms; do not
build or publish a sampled Google surface. Choose destinations before seeing
the results, cover all parts of Detroit, and report absolute error by mode
rather than selectively showing good matches.
