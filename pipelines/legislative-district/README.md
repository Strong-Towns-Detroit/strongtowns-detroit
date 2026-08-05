# Legislative District Analysis

Pull ACS 5-year demographic, income, and housing data for a Michigan state
house district and render a multi-panel choropleth map deck.

## Pipeline

1. **fetch_district.py** — Downloads the post-2022 MICRC district boundary
   from TIGER/Line, pulls tract-level ACS for Michigan (cached), clips
   tracts to the district by **area-fraction** (default ≥30% of tract area
   inside the district), and writes:
   - `output/district_<N>_boundary.gpkg`
   - `output/district_<N>_tracts.gpkg`
   - `output/district_<N>_summary.csv`

   Use `--exclude <GEOID …>` to manually drop specific tracts that the
   area threshold would otherwise include.

2. **fetch_district_streets.py** — Pulls OSM street network, water
   polygons, and city boundaries for the municipalities the district
   touches (default: Detroit, Hamtramck, Highland Park, Grosse Pointe Park).
   Writes `district_<N>_streets.gpkg`, `district_<N>_water.gpkg`,
   `district_<N>_cities.gpkg`.

3. **map_district.py** — Reads tracts + boundary + (optional) streets/water
   and renders a 12-panel choropleth (`output/district_<N>_panels.png`).

4. **make_locator_map.py** — Renders a stylized single-panel locator map
   (`output/district_<N>_locator.png`) suitable for a campaign website.

5. **fetch_precincts.py** — Pulls Detroit's voting precinct shapes from
   the City ArcGIS FeatureServer + 2024 general election results from
   OpenElections (joined by precinct number). Computes D-margin and
   election-day turnout per precinct. Clips to the district by area
   threshold (same 30% rule as tracts). Writes
   `output/district_<N>_precincts.gpkg`. Detroit-only for now —
   Hamtramck/Highland Park/Grosse Pointe Park precincts not yet covered.

6. **name_tracts.py** — Pulls Detroit's official Neighborhoods polygons
   from the City of Detroit ArcGIS FeatureServer, assigns each tract a
   neighborhood name by largest area-overlap, falls back to nearest
   neighborhood (prefixed "near …") for tracts outside Detroit's index.
   Manual overrides in `data/tract_name_overrides.json`. Updates the
   tracts gpkg in place and writes `district_<N>_tract_names.csv`.

7. **make_interactive_map.py** — Builds a self-contained interactive HTML
   explorer (`output/district_<N>_explorer.html`). Click tracts (or use
   the rectangle tool) to build a selection; aggregate stats recompute
   live. Switch the choropleth metric from a sidebar list. Tabs for
   Map, Distributions, Tracts table, and Precincts (2024 results). The
   Precincts tab is only included if `district_<N>_precincts.gpkg`
   exists. Single file — double-click to open.

## Usage

```bash
source .venv/bin/activate

# Canonical HD-9 build (Detroit east side + Milwaukee Junction +
# Southwest Downtown + Hamtramck/Highland Park/Grosse Pointe Park slivers).
# Two boundary tracts are manually excluded — see "HD-9 exclusions" below.
python pipelines/legislative-district/fetch_district.py         --district 9 \
    --exclude 26163984100 26163985300
python pipelines/legislative-district/fetch_district_streets.py --district 9
python pipelines/legislative-district/fetch_precincts.py        --district 9
python pipelines/legislative-district/name_tracts.py            --district 9
python pipelines/legislative-district/map_district.py           --district 9
python pipelines/legislative-district/make_locator_map.py       --district 9
python pipelines/legislative-district/make_interactive_map.py   --district 9
```

Requires `CENSUS_API_KEY` in `.env` (or environment).

### HD-9 exclusions

Two tracts cross the HD-9 boundary with area-fraction above the 30%
threshold but were judged to fit better with neighboring districts:

- `26163984100` (~38% of area inside HD-9)
- `26163985300` (~43% of area inside HD-9)

Pass them via `--exclude` on every fetch to keep the canonical 51-tract
HD-9 set. Without the flag you'll get 53 tracts.

## Notes

- **Tract assignment**: a tract is included if at least 30% of its area
  falls inside the district polygon (configurable via the
  `area_threshold` argument to `clip_tracts_to_district`). Centroid-only
  assignment was abandoned because it missed irregularly-shaped tracts
  (e.g. Milwaukee Junction near rail corridors).
- **Manual overrides** via `--exclude <GEOID …>` apply *after* the area
  threshold. See "HD-9 exclusions" above for the canonical HD-9 set.
- **District-level medians**: ACS medians don't sum across tracts, so
  reported medians are population-weighted means of tract medians
  (directional, not exact). Columns are suffixed `_pop_weighted`.
- **Aggregates over partial tracts**: for tracts only partially inside
  the district, we sum the *whole* tract's counts. This slightly
  over-counts boundary populations — fine for a campaign tool, would
  need area-weighted aggregation for precise statutory purposes.
- **Voting data**: not yet included. Future work — pull MI SOS precinct
  results or VEST shapefiles and join to the district boundary.

## Future extensions

- Area-weighted aggregation for boundary tracts (multiply each count by
  its `frac_inside` before summing).
- Block-group granularity for fine-grained turf maps.
- Precinct-level past election results.
- Side-by-side comparison panels (district vs. state vs. county).
