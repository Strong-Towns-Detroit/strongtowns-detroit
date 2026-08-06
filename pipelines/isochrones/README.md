# Isochrones & accessibility toolkit

Reusable travel-time (isochrone) tools built on OSMnx 2.x. **Place-parameterized and
mode-parameterized (drive / walk / bike) — nothing is hardcoded to Detroit.** One shared
core module powers three CLIs.

Core module: [`src/strongtowns_detroit/geo/isochrones.py`](../../src/strongtowns_detroit/geo/isochrones.py)

## Two driving use cases

1. **Walkability / land-value accessibility** — score locations by travel time to amenities
   (grocery, transit, parks, schools, pharmacy, restaurants). Feeds a land-value model:
   proximity-in-travel-time is a core driver of what a location is worth.
2. **Warehouse siting** — given candidate sites and weighted destinations, rank sites by
   drive time. For a real startup search that may *not* be Detroit.

Both are just different callers of one primitive: **`nearest_time_to_any`** (many origins →
nearest of many destinations). App A and App B differ only in what plays "origin" vs
"destination" and how the times are aggregated.

## Environment

OSMnx lives in `pipelines/housingDataAnalysis/.venv`, **not** the repo-root `.venv`. Run
everything with that interpreter and `src` on the path:

```bash
PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python pipelines/isochrones/<cli>.py ...
```

## CLIs

### 1. `generate_isochrones.py` — reachability polygons

```bash
PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python \
  pipelines/isochrones/generate_isochrones.py \
  --point 42.3400 -83.0550 --dist 3500 --mode walk \
  --origins 42.3314,-83.0458 --minutes 5 10 15 \
  --output output/isochrones_campus_martius.gpkg \
  --map output/isochrones_campus_martius.png
```

Network region: either `--place "City, State, USA"` **or** `--point LAT LON --dist METRES`.
`--method smooth` is recommended for a clean, classic-looking polygon that remains close
to the network-following reach. `buffer` remains the default and honest street-footprint
baseline; `alpha` is a concave hull, and `convex` overstates reach (offered, never default).

### 2. `walkability_score.py` — amenity accessibility

```bash
PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python \
  pipelines/isochrones/walkability_score.py \
  --point 42.3400 -83.0550 --dist 3500 --mode walk \
  --points pipelines/isochrones/examples/detroit_coords.csv \
  --categories grocery transit park school pharmacy restaurant \
  --output output/walkability.gpkg --map output/walkability.png
```

Points from `.csv` (`--lat-col`/`--lon-col`) or `.gpkg`/`.geojson`. Emits `time_<cat>`
(minutes), `score_<cat>` (0–1 via exponential half-life decay), `walkability_score`
(0–100 weighted composite), and `weakest_category` so a location strong on average but
missing (say) grocery is visible, not hidden by the mean.

### 3. `warehouse_siting.py` — rank candidate sites

```bash
PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python \
  pipelines/isochrones/warehouse_siting.py \
  --place "Detroit, Michigan, USA" --mode drive \
  --sites pipelines/isochrones/examples/detroit_sites.csv \
  --destinations pipelines/isochrones/examples/detroit_destinations.csv \
  --id-col name --dest-weight-col volume \
  --threshold-min 30 --objective weighted_mean --top 3 \
  --output output/site_ranking.csv --map output/top_sites.png
```

The ranked table keeps **non-collapsible tradeoff metrics** — `max_time` (worst-case),
`weighted_mean_time` (volume-weighted typical), `pct_within_threshold` (coverage), `p90_time`,
`n_unreached`. `--objective` sets only the sort key; every column stays so a low-mean site
with a terrible worst case is not silently preferred. Sites with unreached destinations sort
to the bottom regardless of objective.

## Caching

Networks are cached as GraphML under `--cache-dir` (default `./cache`), keyed by
place-slug/point + mode. `--reuse-graphml` is an **opt-in, Detroit-only speed shortcut**
(default: not set): pass the repo's pre-downloaded Detroit **drive** graph
(`pipelines/housingDataAnalysis/street_simplification/detroit_street_network.graphml`) to
skip the download for the drive case. It is honored **only** when `--mode drive` **and** the
requested point/place actually falls inside that graph's node bounding box — a drive query
for a location outside Detroit (e.g. Columbus OH) **ignores** the reuse graph (with a
warning) and builds the correct network, so you never silently get the wrong city. Walk/bike
always download fresh topology (a drive graph cannot answer walk/bike routing).

## Correctness notes (baked into the core)

- **Directed drive graphs** have one-way streets: `time(A→B) ≠ time(B→A)`. `nearest_time_to_any`
  runs multi-source Dijkstra **from the destinations on the reversed graph**, so results are
  genuine origin→destination times, in one Dijkstra regardless of how many origins are scored.
- **Walk/bike speeds are forced uniform** (4.8 / 15 km/h) before computing travel times —
  OSM `maxspeed` tags are car limits and meaningless off the drive network.
- **Unreached nodes** (islands, beyond cutoff) come back as `+inf`: scores floor to 0,
  siting surfaces them as `n_unreached` rather than dropping/averaging them away.
- **Isochrone default = buffered union of reachable edges** (honest reach), not convex hull
  (which bridges gaps the network never crosses).

## Known limitations / upgrade paths

- **Transit-by-proximity** measures distance to the nearest stop, not schedule-aware transit
  time. Real upgrade: GTFS feeds (headways, transfers, wait time).
- **`jobs` has no OSM tag** — deliberately omitted. Use LEHD LODES WAC for jobs accessibility.
- **Nearest-node snapping** introduces up to ~one-block error (an amenity nearer than the snap
  distance can read 0; a point across a barrier can snap to the wrong side).
- Large place-wide `features_from_place` / `graph_from_place` calls can be slow; for big
  non-Detroit areas prefer `--point`/`--dist` bounding and let the GraphML cache do the rest.

## Example inputs

See `pipelines/isochrones/examples/` (`detroit_coords.csv`, `detroit_sites.csv`,
`detroit_destinations.csv`).
