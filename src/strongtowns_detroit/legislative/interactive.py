"""Build a self-contained interactive HTML map for a state house district.

The page bundles tract GeoJSON inline and uses Leaflet (loaded from CDN)
for rendering. All choropleth styling, selection state, and live aggregate
recomputation happens client-side in plain JS — see the embedded template
below.
"""

import json
from pathlib import Path
from typing import Optional

import geopandas as gpd

# Properties carried into the GeoJSON so the JS can recompute aggregates.
RAW_COUNT_COLS = [
    'total_population', 'land_area_km2',
    'race_total', 'nh_white', 'nh_black', 'nh_asian',
    'nh_two_or_more', 'hispanic',
    'poverty_universe', 'poverty_below',
    'edu_total_25plus', 'edu_bachelors_plus',
    'tenure_total', 'owner_occupied', 'renter_occupied',
    'housing_units_total', 'housing_units_vacant',
    'pop_16plus', 'in_labor_force', 'unemployed',
    'pob_total', 'foreign_born',
    'pop_total_for_age', 'pop_18_34', 'pop_65_plus',
    # 8 age-distribution bins for the popover histogram
    'age_0_17', 'age_18_24', 'age_25_34', 'age_35_44',
    'age_45_54', 'age_55_64', 'age_65_74', 'age_75_plus',
]

MEDIAN_COLS = [
    'median_household_income',
    'median_home_value',
    'median_gross_rent',
]

# (id, label, format) — what the user can color by.
METRICS = [
    ('total_population',        'Total population',         'count'),
    ('pop_density_per_km2',     'Population density (/km²)', 'count'),
    ('median_household_income', 'Median HH income',         'usd'),
    ('median_home_value',       'Median home value',        'usd'),
    ('median_gross_rent',       'Median gross rent',        'usd'),
    ('pct_poverty',             'Poverty rate',             'pct'),
    ('pct_nh_black',            '% non-Hispanic Black',     'pct'),
    ('pct_nh_white',            '% non-Hispanic White',     'pct'),
    ('pct_hispanic',            '% Hispanic / Latino',      'pct'),
    ('pct_bachelors_plus',      "% Bachelor's or higher",   'pct'),
    ('pct_18_34',               '% age 18–34',              'pct'),
    ('pct_65_plus',             '% age 65+',                'pct'),
    ('pct_renter',              '% renter-occupied',        'pct'),
    ('pct_unemployed',          'Unemployment rate',        'pct'),
    ('pct_vacant',              '% vacant housing',         'pct'),
    ('pct_foreign_born',        '% foreign-born',           'pct'),
]


EXTRA_COLS = ['neighborhood_name', 'naming_source']

# Columns we carry from the precincts gpkg into the inline GeoJSON payload.
PRECINCT_COLS = [
    'Precinct', 'precinct_location', 'precinct_name',
    'pres_dem', 'pres_rep', 'pres_other', 'pres_total',
    'pres_dem_pct', 'pres_rep_pct', 'pres_dem_margin',
    'registered_voters', 'turnout_pct',
]

# Metrics user can color the precinct map by. Diverging palette for margin,
# sequential for everything else.
PRECINCT_METRICS = [
    ('pres_dem_margin', '2024 Pres — D margin (pts)', 'pct',   'diverging'),
    ('turnout_pct',     'Election-day turnout (%)',   'pct',   'green'),
    ('pres_total',      '2024 Pres total votes',      'count', 'blue'),
    ('pres_dem',        '2024 Pres — D votes',        'count', 'blue'),
    ('pres_rep',        '2024 Pres — R votes',        'count', 'red'),
]


def _tracts_to_geojson(tracts: gpd.GeoDataFrame) -> dict:
    """Project to WGS84 and serialize tracts with the columns the JS needs."""
    g = tracts.to_crs(4326).copy()

    keep = ['GEOID']
    for col in RAW_COUNT_COLS + MEDIAN_COLS + EXTRA_COLS + [m[0] for m in METRICS]:
        if col in g.columns and col not in keep:
            keep.append(col)
    keep_set = set(keep)
    drop = [c for c in g.columns if c not in keep_set and c != 'geometry']
    g = g.drop(columns=drop)

    return json.loads(g.to_json())


def _boundary_to_geojson(boundary: gpd.GeoDataFrame) -> dict:
    return json.loads(boundary.to_crs(4326).to_json())


def _precincts_to_geojson(precincts: gpd.GeoDataFrame) -> dict:
    """Project to WGS84 and serialize precincts with relevant columns."""
    g = precincts.to_crs(4326).copy()
    keep = [c for c in PRECINCT_COLS if c in g.columns] + ['geometry']
    drop = [c for c in g.columns if c not in keep]
    g = g.drop(columns=drop)
    return json.loads(g.to_json())


def build_interactive_html(
    tracts: gpd.GeoDataFrame,
    district: gpd.GeoDataFrame,
    *,
    district_number: int | str = 9,
    title: Optional[str] = None,
    precincts: Optional[gpd.GeoDataFrame] = None,
) -> str:
    """Return the full HTML document as a string."""
    title = title or f'Michigan State House District {district_number} — Explorer'
    tracts_geojson = _tracts_to_geojson(tracts)
    boundary_geojson = _boundary_to_geojson(district)

    payload = {
        'title': title,
        'districtNumber': str(district_number),
        'metrics': [
            {'id': m[0], 'label': m[1], 'fmt': m[2]} for m in METRICS
        ],
        'tracts': tracts_geojson,
        'boundary': boundary_geojson,
    }

    if precincts is not None and len(precincts) > 0:
        payload['precincts'] = {
            'features': _precincts_to_geojson(precincts),
            'metrics': [
                {'id': m[0], 'label': m[1], 'fmt': m[2], 'palette': m[3]}
                for m in PRECINCT_METRICS
            ],
        }

    return _HTML_TEMPLATE.replace(
        '__PAYLOAD__',
        json.dumps(payload, default=_json_default),
    ).replace('__TITLE__', title)


def _json_default(o):
    # GeoJSON has already been converted via gdf.to_json(); this catches
    # any stray numpy scalars in metadata.
    try:
        return o.item()
    except AttributeError:
        return str(o)


# ── HTML / JS template ───────────────────────────────────────────────
# Single-file Leaflet app. CSS/JS inlined; data injected via __PAYLOAD__.
_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      crossorigin="">
<link rel="stylesheet"
      href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css"
      crossorigin="">
<style>
  :root { --sidebar-w: 320px; }
  html, body { margin: 0; padding: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  #app { display: flex; height: 100%; }
  #sidebar {
    width: var(--sidebar-w); flex-shrink: 0;
    background: #f7f7f4; border-right: 1px solid #d9d9d4;
    overflow-y: auto; padding: 16px 18px;
    box-sizing: border-box;
  }
  #main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .tabs {
    display: flex; background: #fff;
    border-bottom: 1px solid #d9d9d4;
    padding: 0 12px; flex-shrink: 0;
  }
  .tab {
    background: none; border: 0; cursor: pointer;
    padding: 10px 16px; font-size: 13px; color: #666;
    border-bottom: 2px solid transparent; margin-bottom: -1px;
    font-family: inherit;
  }
  .tab:hover { color: #1a1a1a; }
  .tab.active { color: #0c2340; border-bottom-color: #0c2340; font-weight: 600; }
  .view { flex: 1; overflow: auto; min-height: 0; }
  #map-view { display: flex; }
  #map { flex: 1; }
  #distributions-view {
    padding: 14px; display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px; align-content: start; background: #f7f7f4;
  }
  .dist-card {
    background: white; border: 1px solid #d9d9d4; border-radius: 5px;
    padding: 10px 12px 8px;
  }
  .dist-title {
    font-size: 13px; font-weight: 600; color: #1a1a1a;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .dist-stats { font-size: 11px; color: #777; margin: 2px 0 6px; }
  .dist-svg { width: 100%; height: 110px; display: block; }
  .dist-axis {
    display: flex; justify-content: space-between;
    font-size: 10px; color: #777; margin-top: 2px;
    font-variant-numeric: tabular-nums;
  }
  .dist-bar { cursor: pointer; }
  .dist-bar:hover .dist-bar-bg { fill: #b0b0b0; }
  .dist-bar.has-sel .dist-bar-fg { fill: #0c2340; }

  /* Tracts table */
  #table-view { padding: 0; background: #fff; }
  table.tracts {
    width: 100%; border-collapse: collapse;
    font-size: 12px; font-variant-numeric: tabular-nums;
  }
  table.tracts thead {
    position: sticky; top: 0; background: #f7f7f4;
    box-shadow: 0 1px 0 #d9d9d4; z-index: 2;
  }
  table.tracts th {
    padding: 9px 10px; text-align: right; font-weight: 600;
    color: #555; cursor: pointer; user-select: none;
    white-space: nowrap; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  table.tracts th:first-child { text-align: left; }
  table.tracts th:hover { color: #1a1a1a; background: #eee; }
  table.tracts th.sort-active { color: #0c2340; }
  table.tracts th .sort-arrow { color: #aaa; margin-left: 3px; font-size: 10px; }
  table.tracts th.sort-active .sort-arrow { color: #0c2340; }
  table.tracts td {
    padding: 6px 10px; text-align: right;
    border-bottom: 1px solid #f0efe8;
  }
  table.tracts td:first-child {
    text-align: left; color: #1a1a1a; font-size: 12px;
  }
  table.tracts .tract-name { font-weight: 600; line-height: 1.2; }
  table.tracts .tract-geoid {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 10px; color: #999; line-height: 1.2;
  }
  table.tracts tr { cursor: pointer; }
  table.tracts tr:hover { background: #f5f5f0; }
  table.tracts tr.selected { background: #e3eaf2; }
  table.tracts tr.selected td:first-child { color: #0c2340; font-weight: 600; }
  table.tracts tr.selected:hover { background: #d6e0eb; }

  /* Precincts tab */
  #precincts-view { display: flex; flex-direction: column; }
  #precincts-toolbar {
    background: #f7f7f4; border-bottom: 1px solid #d9d9d4;
    padding: 8px 14px; display: flex; align-items: center; gap: 10px;
    flex-shrink: 0; flex-wrap: wrap;
  }
  .prec-metric-label { font-size: 12px; color: #555; font-weight: 600; }
  #precincts-metric-select {
    padding: 5px 8px; font-size: 12px; border: 1px solid #d0d0c8;
    border-radius: 3px; background: white; font-family: inherit;
  }
  .prec-note {
    font-size: 11px; color: #888; margin-left: auto; max-width: 60%;
    text-align: right; line-height: 1.3;
  }
  #precincts-map { flex: 1; min-height: 0; }
  .leaflet-tooltip.precinct-tip {
    background: rgba(20,28,40,0.94); color: white;
    border: none; box-shadow: 0 1px 4px rgba(0,0,0,0.25);
    font-size: 12px; padding: 6px 9px; border-radius: 3px;
    line-height: 1.4;
  }
  .leaflet-tooltip.precinct-tip:before { display: none; }
  .leaflet-tooltip.precinct-tip .ptip-num { font-weight: 600; color: #fff; }
  .leaflet-tooltip.precinct-tip .ptip-meta { color: #aaa; font-size: 10px; }
  h1 { font-size: 16px; margin: 0 0 4px; color: #1a1a1a; }
  h2 { font-size: 12px; margin: 16px 0 6px; color: #555; text-transform: uppercase; letter-spacing: 0.06em; }
  .subtitle { font-size: 12px; color: #777; margin-bottom: 8px; }
  .metric-list { list-style: none; margin: 0; padding: 0; }
  .metric-list li { margin: 2px 0; }
  .metric-list label { font-size: 13px; cursor: pointer; display: flex; align-items: center; }
  .metric-list input { margin-right: 6px; }
  .stat-row { display: flex; justify-content: space-between; font-size: 13px; padding: 3px 0; border-bottom: 1px dashed #e3e3dd; }
  .stat-row .k { color: #555; }
  .stat-row .v { color: #111; font-variant-numeric: tabular-nums; font-weight: 600; }
  .selection-bar { background: #fff; border: 1px solid #d9d9d4; border-radius: 6px; padding: 10px; margin: 8px 0 12px; }
  .selection-bar .count { font-size: 14px; font-weight: 700; color: #0c2340; }
  .btn-row { display: flex; gap: 6px; margin-top: 8px; }
  button.b {
    background: #0c2340; color: white; border: 0; border-radius: 4px;
    font-size: 12px; padding: 6px 10px; cursor: pointer; flex: 1;
  }
  button.b.secondary { background: #777; }
  button.b:hover { opacity: 0.9; }
  .legend {
    background: #fff; padding: 6px 10px; border-radius: 4px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.4;
  }
  .legend .swatch { display: inline-block; width: 14px; height: 12px; margin-right: 6px; vertical-align: middle; border: 1px solid #aaa3; }
  .leaflet-interactive { cursor: pointer; outline: none; }
  .leaflet-interactive:focus { outline: none; }
  #agg-histogram { margin-top: 4px; }
  .hist-bar { fill: #0c2340; }

  /* Query builder */
  .collapsible-header { cursor: pointer; user-select: none; }
  .collapsible-header .caret {
    font-size: 11px; color: #999; margin-left: 6px;
    display: inline-block; transition: transform 0.15s;
  }
  .collapsible-header.collapsed .caret { transform: rotate(-90deg); }
  #filter-panel.collapsed { display: none; }
  .filter-row {
    display: grid;
    grid-template-columns: 1fr 46px 64px 20px;
    gap: 4px; margin-bottom: 4px; align-items: center;
  }
  .filter-row select, .filter-row input {
    font-size: 12px; padding: 4px 4px;
    border: 1px solid #d0d0c8; border-radius: 3px;
    background: white; min-width: 0; box-sizing: border-box;
  }
  .filter-row .filter-remove {
    background: none; border: 0; color: #aaa;
    font-size: 18px; line-height: 1; cursor: pointer; padding: 0;
  }
  .filter-row .filter-remove:hover { color: #b82f23; }
  #btn-add-filter {
    background: none; border: 1px dashed #aaa; color: #555;
    font-size: 12px; padding: 5px; width: 100%; border-radius: 4px;
    cursor: pointer; margin-top: 4px;
  }
  #btn-add-filter:hover { background: #eee; color: #1a1a1a; }
  .filter-result {
    font-size: 12px; color: #777; margin: 8px 0;
    padding: 5px 8px; background: #f0efe8; border-radius: 4px; text-align: center;
  }
  .filter-result.has-match { color: #0c2340; font-weight: 600; background: #e3eaf2; }
  .filter-result.no-match { color: #b82f23; background: #fbe6e3; }

  /* Hover tooltip on tracts */
  .leaflet-tooltip.tract-tip {
    background: rgba(20,28,40,0.94); color: white;
    border: none; box-shadow: 0 1px 4px rgba(0,0,0,0.25);
    font-size: 12px; padding: 5px 8px; border-radius: 3px;
    line-height: 1.35;
  }
  .leaflet-tooltip.tract-tip:before { display: none; }
  .leaflet-tooltip.tract-tip .tip-geoid {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 10px; color: #aaa;
  }

  /* Saved views */
  .saved-view {
    display: flex; gap: 4px; margin-bottom: 4px;
  }
  .saved-view .view-load {
    flex: 1; text-align: left;
    background: #fff; border: 1px solid #d9d9d4; border-radius: 3px;
    padding: 5px 8px; font-size: 12px; cursor: pointer;
    color: #1a1a1a; font-family: inherit;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .saved-view .view-load:hover { background: #e3eaf2; border-color: #0c2340; }
  .saved-view .view-delete {
    background: none; border: 0; color: #aaa;
    font-size: 16px; line-height: 1; cursor: pointer; padding: 0 4px;
  }
  .saved-view .view-delete:hover { color: #b82f23; }
  .saved-empty { font-size: 12px; color: #888; padding: 4px 0; font-style: italic; }
  .save-row { display: flex; gap: 4px; margin-top: 6px; }
  .save-row input {
    flex: 1; min-width: 0; padding: 5px 6px;
    border: 1px solid #d0d0c8; border-radius: 3px; font-size: 12px;
    font-family: inherit; box-sizing: border-box;
  }
  .hist-bin-label { font-size: 10px; fill: #555; }
  .hist-val-label { font-size: 10px; fill: #1a1a1a; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
<div id="app">
  <aside id="sidebar">
    <h1 id="title-el"></h1>
    <div class="subtitle" id="subtitle-el">ACS 2020–2024 · <b>click</b> a tract to select · <b>⌘-click</b> (Ctrl on Windows) to add or remove · <b>click empty area</b> to clear · rectangle tool for bulk-select</div>

    <h2>Color tracts by</h2>
    <ul class="metric-list" id="metric-list"></ul>

    <h2 class="collapsible-header" id="filter-toggle">Filter tracts <span class="caret">▾</span></h2>
    <div id="filter-panel">
      <div id="filter-rows"></div>
      <button id="btn-add-filter">+ add condition</button>
      <div class="filter-result" id="filter-result">Add a condition to filter tracts…</div>
      <div class="btn-row">
        <button class="b" id="btn-apply-filter">Apply to selection</button>
        <button class="b secondary" id="btn-clear-filter">Clear</button>
      </div>
    </div>

    <h2>Selection</h2>
    <div class="selection-bar">
      <div class="count" id="sel-count">No tracts selected — showing district totals</div>
      <div class="btn-row">
        <button class="b" id="btn-all">Select all</button>
        <button class="b secondary" id="btn-clear">Clear</button>
      </div>
    </div>

    <h2 id="agg-heading">District totals</h2>
    <div id="agg-stats"></div>
    <h2>Age distribution</h2>
    <div id="agg-histogram"></div>

    <h2>Saved views</h2>
    <div id="saved-views-list"></div>
    <div class="save-row">
      <input id="view-name-input" placeholder="Name this view…" maxlength="40">
      <button class="b" id="btn-save-view">Save</button>
    </div>
  </aside>
  <main id="main">
    <div class="tabs">
      <button class="tab active" data-tab="map">Map</button>
      <button class="tab" data-tab="distributions">Distributions</button>
      <button class="tab" data-tab="table">Tracts</button>
      <button class="tab" data-tab="precincts">Precincts</button>
    </div>
    <div id="map-view" class="view"><div id="map"></div></div>
    <div id="distributions-view" class="view" style="display:none"></div>
    <div id="table-view" class="view" style="display:none"></div>
    <div id="precincts-view" class="view" style="display:none">
      <div id="precincts-toolbar">
        <label class="prec-metric-label">Color by:</label>
        <select id="precincts-metric-select"></select>
        <span class="prec-note">2024 Pres results · Detroit precincts only · turnout = election-day votes ÷ registered (excludes absentee CBs)</span>
      </div>
      <div id="precincts-map"></div>
    </div>
  </main>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
<script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js" crossorigin=""></script>
<script>
const PAYLOAD = __PAYLOAD__;

document.getElementById('title-el').textContent = PAYLOAD.title;

// ── Color scales (sequential, 5 quintile bins) ────────────────────
const PALETTES = {
  default: ['#fef0d9','#fdcc8a','#fc8d59','#e34a33','#b30000'],
  blue:    ['#eff3ff','#bdd7e7','#6baed6','#3182bd','#08519c'],
  green:   ['#edf8e9','#bae4b3','#74c476','#31a354','#006d2c'],
  purple:  ['#f2f0f7','#cbc9e2','#9e9ac8','#756bb1','#54278f'],
};

// Map metric id → palette.
const METRIC_PALETTES = {
  total_population:        'blue',
  pop_density_per_km2:     'purple',
  median_household_income: 'green',
  median_home_value:       'green',
  median_gross_rent:       'green',
  pct_poverty:             'default',
  pct_nh_black:            'purple',
  pct_nh_white:            'blue',
  pct_hispanic:            'default',
  pct_bachelors_plus:      'green',
  pct_18_34:               'blue',
  pct_65_plus:             'purple',
  pct_renter:              'default',
  pct_unemployed:          'default',
  pct_vacant:              'default',
  pct_foreign_born:        'green',
};

function quantileBreaks(values, n) {
  const v = values.filter(x => x !== null && x !== undefined && !Number.isNaN(x))
                  .slice().sort((a,b) => a-b);
  if (v.length === 0) return [0, 0, 0, 0];
  const breaks = [];
  for (let i = 1; i < n; i++) {
    breaks.push(v[Math.floor(v.length * i / n)]);
  }
  return breaks;
}

// Pre-compute breaks per metric.
const METRIC_BREAKS = {};
PAYLOAD.metrics.forEach(m => {
  const vals = PAYLOAD.tracts.features.map(f => f.properties[m.id]);
  METRIC_BREAKS[m.id] = quantileBreaks(vals, 5);
});

function colorFor(value, metricId) {
  const palette = PALETTES[METRIC_PALETTES[metricId] || 'default'];
  if (value === null || value === undefined || Number.isNaN(value)) return '#dddddd';
  const breaks = METRIC_BREAKS[metricId];
  for (let i = 0; i < breaks.length; i++) {
    if (value <= breaks[i]) return palette[i];
  }
  return palette[palette.length - 1];
}

// Desaturate a hex color to a gray of equivalent perceptual luminance,
// then compress into a light-gray band so dimmed tracts retain their
// choropleth ordering without competing visually with selected ones.
function toGray(hex) {
  if (!hex || hex[0] !== '#' || hex.length !== 7) return '#dddddd';
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  // Rec. 601 luminance — perceptually weighted.
  const lum = 0.299 * r + 0.587 * g + 0.114 * b;
  // Compress 0..255 → 180..230 (lower lum stays slightly darker = higher metric value).
  const v = Math.round(180 + (lum / 255) * 50);
  const h = v.toString(16).padStart(2, '0');
  return `#${h}${h}${h}`;
}

function fmt(value, kind) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (kind === 'usd') return '$' + Math.round(value).toLocaleString();
  if (kind === 'pct') return value.toFixed(1) + '%';
  if (kind === 'count') return Math.round(value).toLocaleString();
  return value.toString();
}

// ── State ─────────────────────────────────────────────────────────
const state = {
  metric: 'total_population',
  selection: new Set(),
  layerByGeoid: new Map(),
  activeTab: 'map',
  filterRows: [],
  tableSort: { col: 'GEOID', dir: 'asc' },
};

// ── Persistence (URL hash + localStorage) ─────────────────────────
const STATE_KEY = 'hd-explorer-state-' + PAYLOAD.districtNumber;
const VIEWS_KEY = 'hd-explorer-views-' + PAYLOAD.districtNumber;

function serializeState() {
  return {
    t: state.activeTab,
    m: state.metric,
    s: Array.from(state.selection),
    f: state.filterRows,
    ts: state.tableSort,
  };
}

function applyState(s) {
  if (!s || typeof s !== 'object') return;
  if (typeof s.t === 'string') state.activeTab = s.t;
  if (typeof s.m === 'string') state.metric = s.m;
  if (Array.isArray(s.s)) state.selection = new Set(s.s);
  if (Array.isArray(s.f)) state.filterRows = s.f;
  if (s.ts && typeof s.ts === 'object') state.tableSort = s.ts;
}

let _persistDebounce = null;
function persistState() {
  const payload = serializeState();
  const json = JSON.stringify(payload);
  // localStorage immediately
  try { localStorage.setItem(STATE_KEY, json); } catch (e) {}
  // URL hash debounced (avoids history spam during typing)
  clearTimeout(_persistDebounce);
  _persistDebounce = setTimeout(() => {
    try {
      const hash = '#' + encodeURIComponent(json);
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', hash);
      } else {
        window.location.hash = hash;
      }
    } catch (e) {}
  }, 200);
}

function restoreState() {
  let s = null;
  // 1. URL hash wins (so shared links override prior local state)
  if (window.location.hash && window.location.hash.length > 1) {
    try { s = JSON.parse(decodeURIComponent(window.location.hash.slice(1))); }
    catch (e) {}
  }
  // 2. Fall back to localStorage
  if (!s) {
    try {
      const raw = localStorage.getItem(STATE_KEY);
      if (raw) s = JSON.parse(raw);
    } catch (e) {}
  }
  applyState(s);
}

restoreState();

// ── Map ───────────────────────────────────────────────────────────
const map = L.map('map');

L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OSM &copy; CARTO',
  maxZoom: 19,
}).addTo(map);

// District boundary.
const boundaryLayer = L.geoJSON(PAYLOAD.boundary, {
  style: { color: '#0c2340', weight: 3, fill: false, dashArray: '6 4' },
}).addTo(map);
map.fitBounds(boundaryLayer.getBounds(), { padding: [10, 10] });

// Tract layer.
// Spotlight model: when there's a selection, unselected tracts fade to gray
// so the selected ones pop by contrast — no heavy border needed. When the
// selection is empty (default), everything renders at full color.
// Avoids the shared-edge stroke-weight inconsistency the heavy-outline
// approach had.
function tractStyle(feature) {
  const value = feature.properties[state.metric];
  const hasSelection = state.selection.size > 0;
  const selected = state.selection.has(feature.properties.GEOID);
  const dimmed = hasSelection && !selected;

  if (dimmed) {
    // Desaturate the metric color → gray of equivalent luminance, so the
    // choropleth pattern stays visible (dappling) without color competing
    // with the selection.
    return {
      fillColor: toGray(colorFor(value, state.metric)),
      fillOpacity: 0.85,
      color: '#ffffff',
      weight: 0.4,
      opacity: 0.8,
      dashArray: null,
    };
  }
  return {
    fillColor: colorFor(value, state.metric),
    fillOpacity: 0.85,
    color: '#ffffff',
    weight: 0.6,
    opacity: 1,
    dashArray: null,
  };
}

// ── Age histogram (selection-aggregated) ─────────────────────────
const AGE_BINS = [
  ['0–17',  'age_0_17'],
  ['18–24', 'age_18_24'],
  ['25–34', 'age_25_34'],
  ['35–44', 'age_35_44'],
  ['45–54', 'age_45_54'],
  ['55–64', 'age_55_64'],
  ['65–74', 'age_65_74'],
  ['75+',   'age_75_plus'],
];

function ageHistogramSvgFromFeatures(features) {
  const bins = AGE_BINS.map(([label, key]) => {
    let sum = 0;
    features.forEach(f => { sum += (+f.properties[key]) || 0; });
    return [label, sum];
  });
  const max = Math.max(...bins.map(b => b[1]), 1);
  const W = 280, rowH = 16, gap = 3, labelW = 44;
  const innerW = W - labelW - 56;
  const H = bins.length * (rowH + gap);
  const rows = bins.map(([label, v], i) => {
    const y = i * (rowH + gap);
    const w = (v / max) * innerW;
    return (
      `<text class="hist-bin-label" x="0" y="${y + rowH * 0.7}" text-anchor="start">${label}</text>` +
      `<rect class="hist-bar" x="${labelW}" y="${y + 2}" width="${w.toFixed(1)}" height="${rowH - 4}" rx="2"></rect>` +
      `<text class="hist-val-label" x="${W - 2}" y="${y + rowH * 0.7}" text-anchor="end">${v.toLocaleString()}</text>`
    );
  });
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${rows.join('')}</svg>`;
}


// ── Click handler ────────────────────────────────────────────────
// Tick-flag so the map.on('click') below knows a feature handled this click
// and shouldn't treat it as an empty-space click.
let clickHitFeature = false;

function onTractClick(e) {
  clickHitFeature = true;
  L.DomEvent.stopPropagation(e);
  const ev = e.originalEvent;
  const geoid = e.target.feature.properties.GEOID;
  const additive = ev && (ev.metaKey || ev.ctrlKey);
  if (additive) {
    if (state.selection.has(geoid)) state.selection.delete(geoid);
    else state.selection.add(geoid);
  } else {
    state.selection.clear();
    state.selection.add(geoid);
  }
  recolorAll();
  refreshAggregates();
}

// Click on empty map space → clear selection (mirrors detroit-neighbors).
map.on('click', () => {
  if (clickHitFeature) { clickHitFeature = false; return; }
  if (state.selection.size === 0) return;
  state.selection.clear();
  drawnItems.clearLayers();
  recolorAll();
  refreshAggregates();
});

// ── Hover feedback ───────────────────────────────────────────────
// Spotlight model: hover lifts a subtle navy outline so the user knows
// the tract is interactive, regardless of selected/dimmed state. No
// bringToFront() — shifting SVG z-order on every mousemove was eating
// clicks near tract edges.
function onTractMouseover(e) {
  e.target.setStyle({ color: '#0c2340', weight: 1.5, opacity: 1, dashArray: null });
}
function onTractMouseout(e) {
  e.target.setStyle(tractStyle(e.target.feature));
}

const tractLayer = L.geoJSON(PAYLOAD.tracts, {
  style: tractStyle,
  onEachFeature: (feature, layer) => {
    state.layerByGeoid.set(feature.properties.GEOID, layer);
    layer.on('click', onTractClick);
    layer.on('mouseover', onTractMouseover);
    layer.on('mouseout', onTractMouseout);
  },
}).addTo(map);

// Bring boundary to top after tracts.
boundaryLayer.bringToFront();

// ── Rectangle (box) select via leaflet-draw ──────────────────────
const drawnItems = new L.FeatureGroup().addTo(map);
const drawControl = new L.Control.Draw({
  draw: {
    polyline: false, polygon: false, circle: false, marker: false, circlemarker: false,
    rectangle: { shapeOptions: { color: '#0c2340', weight: 2, dashArray: '4 4' } },
  },
  edit: { featureGroup: drawnItems, edit: false, remove: true },
});
map.addControl(drawControl);

map.on(L.Draw.Event.CREATED, (e) => {
  const bounds = e.layer.getBounds();
  drawnItems.addLayer(e.layer);
  // Add tracts whose centroid is inside the rectangle.
  PAYLOAD.tracts.features.forEach(f => {
    const c = featureCentroid(f);
    if (c && bounds.contains([c.lat, c.lng])) {
      state.selection.add(f.properties.GEOID);
    }
  });
  recolorAll();
  refreshAggregates();
});

function featureCentroid(feature) {
  const g = feature.geometry;
  if (!g) return null;
  let pts = [];
  function walk(coords, depth) {
    if (depth === 0) pts.push(coords);
    else coords.forEach(c => walk(c, depth - 1));
  }
  if (g.type === 'Polygon')      walk(g.coordinates, 2);
  else if (g.type === 'MultiPolygon') walk(g.coordinates, 3);
  if (pts.length === 0) return null;
  const sx = pts.reduce((a,p) => a + p[0], 0) / pts.length;
  const sy = pts.reduce((a,p) => a + p[1], 0) / pts.length;
  return { lat: sy, lng: sx };
}

// ── Sidebar: metric picker ───────────────────────────────────────
const metricListEl = document.getElementById('metric-list');
PAYLOAD.metrics.forEach(m => {
  const li = document.createElement('li');
  li.innerHTML =
    `<label><input type="radio" name="metric" value="${m.id}" ${m.id===state.metric?'checked':''}>${m.label}</label>`;
  metricListEl.appendChild(li);
});
metricListEl.addEventListener('change', (e) => {
  if (e.target.name === 'metric') {
    state.metric = e.target.value;
    recolorAll();
    refreshTooltips();
    refreshLegend();
    if (state.activeTab === 'distributions') refreshDistributions();
    persistState();
  }
});

// ── Buttons ──────────────────────────────────────────────────────
document.getElementById('btn-all').addEventListener('click', () => {
  PAYLOAD.tracts.features.forEach(f => state.selection.add(f.properties.GEOID));
  recolorAll(); refreshAggregates();
});
document.getElementById('btn-clear').addEventListener('click', () => {
  state.selection.clear();
  drawnItems.clearLayers();
  recolorAll(); refreshAggregates();
});

function recolorAll() {
  state.layerByGeoid.forEach((layer, geoid) => {
    layer.setStyle(tractStyle(layer.feature));
  });
}

// ── Aggregate panel ──────────────────────────────────────────────
const RAW = ['total_population','land_area_km2','race_total','nh_white','nh_black','nh_asian',
  'nh_two_or_more','hispanic','poverty_universe','poverty_below','edu_total_25plus',
  'edu_bachelors_plus','tenure_total','owner_occupied','renter_occupied','housing_units_total',
  'housing_units_vacant','pop_16plus','in_labor_force','unemployed','pob_total','foreign_born',
  'pop_total_for_age','pop_18_34','pop_65_plus'];

function aggregate(features) {
  const sums = {};
  RAW.forEach(c => sums[c] = 0);
  features.forEach(f => {
    RAW.forEach(c => {
      const v = f.properties[c];
      if (typeof v === 'number' && !Number.isNaN(v)) sums[c] += v;
    });
  });
  // Population-weighted means for medians.
  const wmean = (col) => {
    let num = 0, den = 0;
    features.forEach(f => {
      const v = f.properties[col]; const w = f.properties.total_population || 0;
      if (typeof v === 'number' && !Number.isNaN(v) && w > 0) { num += v*w; den += w; }
    });
    return den > 0 ? num/den : null;
  };
  const pct = (n, d) => sums[d] > 0 ? sums[n] / sums[d] * 100 : null;

  return {
    'Population':              { v: sums.total_population, fmt: 'count' },
    'Land area (km²)':         { v: sums.land_area_km2, fmt: 'count' },
    'Density (per km²)':       { v: sums.land_area_km2 > 0 ? sums.total_population / sums.land_area_km2 : null, fmt: 'count' },
    '% non-Hispanic Black':    { v: pct('nh_black','race_total'), fmt: 'pct' },
    '% non-Hispanic White':    { v: pct('nh_white','race_total'), fmt: 'pct' },
    '% Hispanic / Latino':     { v: pct('hispanic','race_total'), fmt: 'pct' },
    'Poverty rate':            { v: pct('poverty_below','poverty_universe'), fmt: 'pct' },
    "% Bachelor's or higher":  { v: pct('edu_bachelors_plus','edu_total_25plus'), fmt: 'pct' },
    '% age 18–34':             { v: pct('pop_18_34','pop_total_for_age'), fmt: 'pct' },
    '% age 65+':               { v: pct('pop_65_plus','pop_total_for_age'), fmt: 'pct' },
    '% renter-occupied':       { v: pct('renter_occupied','tenure_total'), fmt: 'pct' },
    '% vacant housing':        { v: pct('housing_units_vacant','housing_units_total'), fmt: 'pct' },
    'Unemployment rate':       { v: pct('unemployed','in_labor_force'), fmt: 'pct' },
    '% foreign-born':          { v: pct('foreign_born','pob_total'), fmt: 'pct' },
    'Median HH income (pop-wt)': { v: wmean('median_household_income'), fmt: 'usd' },
    'Median home value (pop-wt)':  { v: wmean('median_home_value'), fmt: 'usd' },
    'Median gross rent (pop-wt)':  { v: wmean('median_gross_rent'), fmt: 'usd' },
  };
}

function refreshAggregates() {
  const features = PAYLOAD.tracts.features;
  const selected = features.filter(f => state.selection.has(f.properties.GEOID));
  const subset = selected.length > 0 ? selected : features;

  document.getElementById('sel-count').textContent =
    selected.length === 0
      ? 'No tracts selected — showing district totals'
      : selected.length === 1
        ? tractDisplayName(selected[0].properties)
        : `${selected.length} tracts selected`;
  document.getElementById('agg-heading').textContent =
    selected.length === 0 ? 'District totals' : 'Selection totals';

  const stats = aggregate(subset);
  const rows = Object.entries(stats).map(([k, o]) =>
    `<div class="stat-row"><span class="k">${k}</span><span class="v">${fmt(o.v, o.fmt)}</span></div>`
  );
  document.getElementById('agg-stats').innerHTML = rows.join('');
  document.getElementById('agg-histogram').innerHTML = ageHistogramSvgFromFeatures(subset);
  if (state.activeTab === 'distributions') refreshDistributions();
  if (state.activeTab === 'table') renderTable();
  persistState();
}

// ── Legend ───────────────────────────────────────────────────────
const legend = L.control({ position: 'bottomright' });
legend.onAdd = () => {
  const div = L.DomUtil.create('div', 'legend');
  div.id = 'legend';
  return div;
};
legend.addTo(map);

function refreshLegend() {
  const m = PAYLOAD.metrics.find(m => m.id === state.metric);
  const palette = PALETTES[METRIC_PALETTES[state.metric] || 'default'];
  const breaks = METRIC_BREAKS[state.metric];
  const labels = [];
  labels.push(`<b>${m.label}</b>`);
  const lo = [-Infinity, ...breaks];
  const hi = [...breaks, Infinity];
  for (let i = 0; i < palette.length; i++) {
    const a = lo[i], b = hi[i];
    let range;
    if (i === 0) range = `≤ ${fmt(b, m.fmt)}`;
    else if (i === palette.length - 1) range = `> ${fmt(a, m.fmt)}`;
    else range = `${fmt(a, m.fmt)} – ${fmt(b, m.fmt)}`;
    labels.push(`<div><span class="swatch" style="background:${palette[i]}"></span>${range}</div>`);
  }
  document.getElementById('legend').innerHTML = labels.join('');
}

// ── Query builder (filter) ───────────────────────────────────────
const QUERY_COLS = [
  { id: 'total_population',        label: 'Total population',     fmt: 'count' },
  { id: 'pop_density_per_km2',     label: 'Pop density (/km²)',   fmt: 'count' },
  { id: 'median_household_income', label: 'Median HH income',     fmt: 'usd' },
  { id: 'median_home_value',       label: 'Median home value',    fmt: 'usd' },
  { id: 'median_gross_rent',       label: 'Median gross rent',    fmt: 'usd' },
  { id: 'pct_poverty',             label: 'Poverty rate (%)',     fmt: 'pct' },
  { id: 'pct_nh_black',            label: '% non-Hisp. Black',    fmt: 'pct' },
  { id: 'pct_nh_white',            label: '% non-Hisp. White',    fmt: 'pct' },
  { id: 'pct_hispanic',            label: '% Hispanic/Latino',    fmt: 'pct' },
  { id: 'pct_bachelors_plus',      label: "% Bachelor's+",        fmt: 'pct' },
  { id: 'pct_18_34',               label: '% age 18–34',          fmt: 'pct' },
  { id: 'pct_65_plus',             label: '% age 65+',            fmt: 'pct' },
  { id: 'pct_renter',              label: '% renter-occupied',    fmt: 'pct' },
  { id: 'pct_unemployed',          label: 'Unemployment (%)',     fmt: 'pct' },
  { id: 'pct_vacant',              label: '% vacant housing',     fmt: 'pct' },
  { id: 'pct_foreign_born',        label: '% foreign-born',       fmt: 'pct' },
];

const OPERATORS = [
  { id: 'gt',  label: '>',  test: (a, b) => a >  b },
  { id: 'gte', label: '≥',  test: (a, b) => a >= b },
  { id: 'lt',  label: '<',  test: (a, b) => a <  b },
  { id: 'lte', label: '≤',  test: (a, b) => a <= b },
  { id: 'eq',  label: '=',  test: (a, b) => Math.abs(a - b) < 1e-9 },
  { id: 'ne',  label: '≠',  test: (a, b) => Math.abs(a - b) >= 1e-9 },
];

state.filterRows = [];

function renderFilterRows() {
  const container = document.getElementById('filter-rows');
  container.innerHTML = state.filterRows.map((row, i) => {
    const colOpts = QUERY_COLS.map(c =>
      `<option value="${c.id}" ${c.id===row.colId?'selected':''}>${c.label}</option>`
    ).join('');
    const opOpts = OPERATORS.map(o =>
      `<option value="${o.id}" ${o.id===row.opId?'selected':''}>${o.label}</option>`
    ).join('');
    const val = row.value == null ? '' : row.value;
    return (
      `<div class="filter-row" data-i="${i}">` +
        `<select class="filter-col">${colOpts}</select>` +
        `<select class="filter-op">${opOpts}</select>` +
        `<input class="filter-val" type="number" value="${val}" placeholder="value" step="any">` +
        `<button class="filter-remove" title="Remove condition">×</button>` +
      `</div>`
    );
  }).join('');
}

function evaluateFilter() {
  // Returns Set<GEOID> of matching tracts. Conditions with empty value are ignored.
  const opMap = Object.fromEntries(OPERATORS.map(o => [o.id, o.test]));
  const active = state.filterRows.filter(r =>
    r.value !== '' && r.value !== null && r.value !== undefined && !Number.isNaN(+r.value)
  );
  if (active.length === 0) return null;
  const matches = new Set();
  PAYLOAD.tracts.features.forEach(f => {
    const ok = active.every(r => {
      const v = +f.properties[r.colId];
      const test = opMap[r.opId];
      return !Number.isNaN(v) && test(v, +r.value);
    });
    if (ok) matches.add(f.properties.GEOID);
  });
  return matches;
}

function refreshFilterResult() {
  const result = document.getElementById('filter-result');
  if (state.filterRows.length === 0) {
    result.textContent = 'Add a condition to filter tracts…';
    result.className = 'filter-result';
    return;
  }
  const matches = evaluateFilter();
  if (matches === null) {
    result.textContent = 'Enter a value to see matches';
    result.className = 'filter-result';
  } else if (matches.size === 0) {
    result.textContent = 'No tracts match this filter';
    result.className = 'filter-result no-match';
  } else {
    result.textContent =
      `${matches.size} of ${PAYLOAD.tracts.features.length} tracts match`;
    result.className = 'filter-result has-match';
  }
}

document.getElementById('btn-add-filter').addEventListener('click', () => {
  state.filterRows.push({ colId: 'pct_poverty', opId: 'gt', value: '' });
  renderFilterRows();
  refreshFilterResult();
  persistState();
});

document.getElementById('filter-rows').addEventListener('input', (e) => {
  const rowEl = e.target.closest('.filter-row');
  if (!rowEl) return;
  const i = +rowEl.dataset.i;
  if (e.target.classList.contains('filter-col')) state.filterRows[i].colId = e.target.value;
  if (e.target.classList.contains('filter-op'))  state.filterRows[i].opId  = e.target.value;
  if (e.target.classList.contains('filter-val')) state.filterRows[i].value = e.target.value;
  refreshFilterResult();
  persistState();
});

document.getElementById('filter-rows').addEventListener('click', (e) => {
  if (!e.target.classList.contains('filter-remove')) return;
  const i = +e.target.closest('.filter-row').dataset.i;
  state.filterRows.splice(i, 1);
  renderFilterRows();
  refreshFilterResult();
  persistState();
});

document.getElementById('btn-apply-filter').addEventListener('click', () => {
  const matches = evaluateFilter();
  if (matches === null || matches.size === 0) return;
  state.selection = new Set(matches);
  drawnItems.clearLayers();
  recolorAll();
  refreshAggregates();
});

document.getElementById('btn-clear-filter').addEventListener('click', () => {
  state.filterRows = [];
  renderFilterRows();
  refreshFilterResult();
  persistState();
});

document.getElementById('filter-toggle').addEventListener('click', () => {
  document.getElementById('filter-toggle').classList.toggle('collapsed');
  document.getElementById('filter-panel').classList.toggle('collapsed');
});

// ── Distributions tab ────────────────────────────────────────────
const DIST_BINS = 10;
state.activeTab = 'map';

function computeBins(values, n) {
  const valid = values.filter(v => typeof v === 'number' && !Number.isNaN(v));
  if (valid.length === 0) return null;
  const min = Math.min(...valid);
  const max = Math.max(...valid);
  if (min === max) return null;
  const width = (max - min) / n;
  const bins = Array.from({length: n}, (_, i) => ({
    lo: min + i * width,
    hi: min + (i + 1) * width,
    count: 0,
    selectedCount: 0,
    geoids: [],
  }));
  return { min, max, width, bins, valid };
}

function distributionCardHtml(metric) {
  const features = PAYLOAD.tracts.features;
  const values = features.map(f => +f.properties[metric.id]);
  const bd = computeBins(values, DIST_BINS);
  if (!bd) {
    return `<div class="dist-card"><div class="dist-title">${metric.label}</div>` +
           `<div class="dist-stats">no variation across tracts</div></div>`;
  }
  // Bin every tract
  features.forEach(f => {
    const v = +f.properties[metric.id];
    if (Number.isNaN(v)) return;
    let i = Math.floor((v - bd.min) / bd.width);
    if (i === DIST_BINS) i = DIST_BINS - 1;
    if (i < 0 || i >= DIST_BINS) return;
    const bin = bd.bins[i];
    bin.count++;
    bin.geoids.push(f.properties.GEOID);
    if (state.selection.has(f.properties.GEOID)) bin.selectedCount++;
  });

  const sorted = bd.valid.slice().sort((a, b) => a - b);
  const mean = bd.valid.reduce((a, b) => a + b, 0) / bd.valid.length;
  const median = sorted[Math.floor(sorted.length / 2)];

  const W = 280, H = 110, padL = 4, padR = 4, padT = 4, padB = 14;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;
  const barW = chartW / DIST_BINS;
  const maxCount = Math.max(...bd.bins.map(b => b.count), 1);

  const bars = bd.bins.map((b, i) => {
    const x = padL + i * barW;
    const fullH = (b.count / maxCount) * chartH;
    const selH = (b.selectedCount / maxCount) * chartH;
    const y = padT + chartH - fullH;
    const ySel = padT + chartH - selH;
    const range = `${fmt(b.lo, metric.fmt)}–${fmt(b.hi, metric.fmt)}`;
    const tip = `${range}: ${b.count} tract${b.count===1?'':'s'}` +
                (b.selectedCount > 0 ? ` (${b.selectedCount} selected)` : '');
    return (
      `<g class="dist-bar${b.selectedCount > 0 ? ' has-sel' : ''}" ` +
        `data-bin="${i}" data-geoids="${b.geoids.join(',')}">` +
        `<title>${tip}</title>` +
        `<rect class="dist-bar-bg" x="${x+0.5}" y="${y}" width="${barW-1}" height="${fullH}" fill="#cccccc"></rect>` +
        (selH > 0 ? `<rect class="dist-bar-fg" x="${x+0.5}" y="${ySel}" width="${barW-1}" height="${selH}"></rect>` : '') +
        `<rect x="${x}" y="${padT}" width="${barW}" height="${chartH}" fill="transparent"></rect>` +
      `</g>`
    );
  }).join('');

  return (
    `<div class="dist-card" data-metric="${metric.id}">` +
      `<div class="dist-title">${metric.label}</div>` +
      `<div class="dist-stats">mean ${fmt(mean, metric.fmt)} · median ${fmt(median, metric.fmt)} · n=${bd.valid.length}</div>` +
      `<svg class="dist-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">` +
        bars +
        `<line x1="${padL}" y1="${padT+chartH+0.5}" x2="${W-padR}" y2="${padT+chartH+0.5}" stroke="#aaa" stroke-width="0.5"></line>` +
      `</svg>` +
      `<div class="dist-axis">` +
        `<span>${fmt(bd.min, metric.fmt)}</span>` +
        `<span>${fmt(bd.max, metric.fmt)}</span>` +
      `</div>` +
    `</div>`
  );
}

function refreshDistributions() {
  if (state.activeTab !== 'distributions') return;
  document.getElementById('distributions-view').innerHTML =
    PAYLOAD.metrics.map(distributionCardHtml).join('');
}

document.getElementById('distributions-view').addEventListener('click', (e) => {
  const bar = e.target.closest('.dist-bar');
  if (!bar) return;
  const geoids = (bar.dataset.geoids || '').split(',').filter(Boolean);
  if (geoids.length === 0) return;
  const additive = e.metaKey || e.ctrlKey;
  if (additive) {
    geoids.forEach(g => {
      if (state.selection.has(g)) state.selection.delete(g);
      else state.selection.add(g);
    });
  } else {
    state.selection.clear();
    geoids.forEach(g => state.selection.add(g));
  }
  recolorAll();
  refreshAggregates();
  refreshDistributions();
});

// ── Tracts table ─────────────────────────────────────────────────
const TABLE_COLS = [
  { id: 'neighborhood_name',       label: 'Tract',     fmt: 'name'  },
  { id: 'total_population',        label: 'Pop',       fmt: 'count' },
  { id: 'pop_density_per_km2',     label: 'Density',   fmt: 'count' },
  { id: 'median_household_income', label: 'HH Inc',    fmt: 'usd'   },
  { id: 'pct_poverty',             label: 'Pov %',     fmt: 'pct'   },
  { id: 'pct_nh_black',            label: '% Blk',     fmt: 'pct'   },
  { id: 'pct_nh_white',            label: '% Wht',     fmt: 'pct'   },
  { id: 'pct_renter',              label: '% Rent',    fmt: 'pct'   },
  { id: 'pct_bachelors_plus',      label: "% Bach+",   fmt: 'pct'   },
  { id: 'pct_unemployed',          label: 'Unemp %',   fmt: 'pct'   },
];

function tractDisplayName(props) {
  return props.neighborhood_name || `Tract ${props.GEOID}`;
}

function fmtTable(props, col) {
  if (col.fmt === 'name') {
    const name = tractDisplayName(props);
    return `<div class="tract-name">${name}</div>` +
           `<div class="tract-geoid">${props.GEOID}</div>`;
  }
  return fmt(props[col.id], col.fmt);
}

function sortedTracts() {
  const col = state.tableSort.col;
  const dir = state.tableSort.dir === 'desc' ? -1 : 1;
  const features = PAYLOAD.tracts.features.slice();
  features.sort((a, b) => {
    let av = a.properties[col], bv = b.properties[col];
    if (col === 'neighborhood_name') {
      av = av || `zzz_${a.properties.GEOID}`;  // unnamed sort to bottom
      bv = bv || `zzz_${b.properties.GEOID}`;
    }
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
    return String(av).localeCompare(String(bv)) * dir;
  });
  return features;
}

function renderTable() {
  if (state.activeTab !== 'table') return;
  const sortCol = state.tableSort.col;
  const sortArrow = state.tableSort.dir === 'desc' ? '▼' : '▲';
  const headers = TABLE_COLS.map(c => {
    const active = c.id === sortCol;
    return (
      `<th data-col="${c.id}" class="${active ? 'sort-active' : ''}">` +
        `${c.label}` +
        `<span class="sort-arrow">${active ? sortArrow : '↕'}</span>` +
      `</th>`
    );
  }).join('');
  const rows = sortedTracts().map(f => {
    const sel = state.selection.has(f.properties.GEOID) ? ' selected' : '';
    const cells = TABLE_COLS.map(c => `<td>${fmtTable(f.properties, c)}</td>`).join('');
    return `<tr class="${sel.trim()}" data-geoid="${f.properties.GEOID}">${cells}</tr>`;
  }).join('');
  document.getElementById('table-view').innerHTML =
    `<table class="tracts">` +
      `<thead><tr>${headers}</tr></thead>` +
      `<tbody>${rows}</tbody>` +
    `</table>`;
}

document.getElementById('table-view').addEventListener('click', (e) => {
  const th = e.target.closest('th');
  if (th && th.dataset.col) {
    const col = th.dataset.col;
    if (state.tableSort.col === col) {
      state.tableSort.dir = state.tableSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
      state.tableSort = { col, dir: col === 'GEOID' ? 'asc' : 'desc' };
    }
    renderTable();
    persistState();
    return;
  }
  const tr = e.target.closest('tr[data-geoid]');
  if (!tr) return;
  const geoid = tr.dataset.geoid;
  const additive = e.metaKey || e.ctrlKey;
  if (additive) {
    if (state.selection.has(geoid)) state.selection.delete(geoid);
    else state.selection.add(geoid);
  } else {
    state.selection.clear();
    state.selection.add(geoid);
  }
  recolorAll();
  refreshAggregates();
});

// ── Precincts tab (separate Leaflet map) ─────────────────────────
const PRECINCT_PALETTES = {
  // Diverging red→white→blue, anchored at 0.
  diverging: ['#b30000', '#e34a33', '#fdcc8a', '#fef0d9', '#deebf7', '#9ecae1', '#3182bd', '#08519c'],
  blue:  ['#eff3ff','#bdd7e7','#6baed6','#3182bd','#08519c'],
  red:   ['#fef0d9','#fdcc8a','#fc8d59','#e34a33','#b30000'],
  green: ['#edf8e9','#bae4b3','#74c476','#31a354','#006d2c'],
};

let precinctsMap = null;
let precinctLayer = null;
let precinctsInitialized = false;
state.precinctMetric = (PAYLOAD.precincts && PAYLOAD.precincts.metrics[0])
  ? PAYLOAD.precincts.metrics[0].id : null;

function precinctMetricBreaks(metricId, palette) {
  const vals = PAYLOAD.precincts.features.features
    .map(f => f.properties[metricId])
    .filter(v => typeof v === 'number' && !Number.isNaN(v));
  if (vals.length === 0) return null;
  vals.sort((a, b) => a - b);
  if (palette === 'diverging') {
    // Anchored at 0; bins span -100..+100. Use fixed breaks for D-margin readability.
    return [-50, -20, -5, 0, 5, 20, 50];
  }
  const n = PRECINCT_PALETTES[palette].length;
  const breaks = [];
  for (let i = 1; i < n; i++) breaks.push(vals[Math.floor(vals.length * i / n)]);
  return breaks;
}

function precinctColor(value, metric) {
  const palette = PRECINCT_PALETTES[metric.palette] || PRECINCT_PALETTES.blue;
  if (value === null || value === undefined || Number.isNaN(value)) return '#dddddd';
  const breaks = precinctMetricBreaks(metric.id, metric.palette);
  if (!breaks) return '#dddddd';
  for (let i = 0; i < breaks.length; i++) {
    if (value <= breaks[i]) return palette[i];
  }
  return palette[palette.length - 1];
}

function precinctStyle(feature) {
  const metric = PAYLOAD.precincts.metrics.find(m => m.id === state.precinctMetric);
  const v = feature.properties[metric.id];
  return {
    fillColor: precinctColor(v, metric),
    fillOpacity: 0.78,
    color: '#ffffff', weight: 0.6, opacity: 1,
  };
}

function precinctTooltipHtml(props) {
  const metric = PAYLOAD.precincts.metrics.find(m => m.id === state.precinctMetric);
  const v = props[metric.id];
  return (
    `<span class="ptip-num">Precinct ${props.Precinct}</span>` +
    (props.precinct_name ? `<br><span class="ptip-meta">${props.precinct_name}</span>` : '') +
    `<br>${metric.label}: ${fmt(v, metric.fmt)}` +
    `<br>D ${fmt(props.pres_dem, 'count')} · R ${fmt(props.pres_rep, 'count')} · Other ${fmt(props.pres_other, 'count')}` +
    `<br>Reg voters: ${fmt(props.registered_voters, 'count')}`
  );
}

function initPrecinctsMap() {
  if (precinctsInitialized || !PAYLOAD.precincts) return;
  precinctsMap = L.map('precincts-map');
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OSM &copy; CARTO',
    maxZoom: 19,
  }).addTo(precinctsMap);

  // District boundary on top
  L.geoJSON(PAYLOAD.boundary, {
    style: { color: '#0c2340', weight: 3, fill: false, dashArray: '6 4' },
  }).addTo(precinctsMap).bringToFront();

  precinctLayer = L.geoJSON(PAYLOAD.precincts.features, {
    style: precinctStyle,
    onEachFeature: (feature, layer) => {
      layer.bindTooltip(precinctTooltipHtml(feature.properties), {
        sticky: true, className: 'precinct-tip', direction: 'top', offset: [0, -6],
      });
    },
  }).addTo(precinctsMap);

  // Fit to precincts (which are clipped to district)
  precinctsMap.fitBounds(precinctLayer.getBounds(), { padding: [10, 10] });

  // Populate metric select
  const sel = document.getElementById('precincts-metric-select');
  sel.innerHTML = PAYLOAD.precincts.metrics.map(m =>
    `<option value="${m.id}" ${m.id === state.precinctMetric ? 'selected' : ''}>${m.label}</option>`
  ).join('');
  sel.addEventListener('change', () => {
    state.precinctMetric = sel.value;
    recolorPrecincts();
  });
  precinctsInitialized = true;
}

function recolorPrecincts() {
  if (!precinctLayer) return;
  precinctLayer.eachLayer(layer => {
    layer.setStyle(precinctStyle(layer.feature));
    layer.setTooltipContent(precinctTooltipHtml(layer.feature.properties));
  });
}

// Hide the Precincts tab if no payload provided.
if (!PAYLOAD.precincts) {
  document.querySelector('.tab[data-tab="precincts"]').style.display = 'none';
}

// ── Tab switching ────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => setTab(btn.dataset.tab));
});

function setTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll('.tab').forEach(el =>
    el.classList.toggle('active', el.dataset.tab === tab)
  );
  document.getElementById('map-view').style.display = tab === 'map' ? 'flex' : 'none';
  document.getElementById('distributions-view').style.display = tab === 'distributions' ? 'grid' : 'none';
  document.getElementById('table-view').style.display = tab === 'table' ? 'block' : 'none';
  document.getElementById('precincts-view').style.display = tab === 'precincts' ? 'flex' : 'none';
  if (tab === 'distributions') refreshDistributions();
  if (tab === 'table') renderTable();
  if (tab === 'map') setTimeout(() => map.invalidateSize(), 50);
  if (tab === 'precincts') {
    initPrecinctsMap();
    setTimeout(() => precinctsMap && precinctsMap.invalidateSize(), 50);
  }
  persistState();
}

// ── Saved views ──────────────────────────────────────────────────
function loadSavedViews() {
  try { return JSON.parse(localStorage.getItem(VIEWS_KEY) || '[]'); }
  catch (e) { return []; }
}
function persistSavedViews(views) {
  try { localStorage.setItem(VIEWS_KEY, JSON.stringify(views)); }
  catch (e) {}
}

function renderSavedViews() {
  const views = loadSavedViews();
  const container = document.getElementById('saved-views-list');
  if (views.length === 0) {
    container.innerHTML = '<div class="saved-empty">No saved views yet</div>';
    return;
  }
  container.innerHTML = views.map((v, i) => {
    const name = (v.name || 'Untitled').replace(/[<>"&]/g, '');
    return (
      `<div class="saved-view">` +
        `<button class="view-load" data-i="${i}" title="${name}">${name}</button>` +
        `<button class="view-delete" data-i="${i}" title="Delete">×</button>` +
      `</div>`
    );
  }).join('');
}

function applySavedView(s) {
  applyState(s);
  // Re-sync UI controls to the restored state.
  document.querySelectorAll('.metric-list input').forEach(r => {
    r.checked = (r.value === state.metric);
  });
  if (typeof drawnItems !== 'undefined') drawnItems.clearLayers();
  renderFilterRows();
  refreshFilterResult();
  setTab(state.activeTab);    // also persists
  recolorAll();
  refreshTooltips();
  refreshLegend();
  refreshAggregates();        // also persists, and refreshes distributions
}

document.getElementById('btn-save-view').addEventListener('click', () => {
  const input = document.getElementById('view-name-input');
  const name = (input.value || '').trim();
  if (!name) return;
  const views = loadSavedViews();
  views.push({ name, state: serializeState(), createdAt: Date.now() });
  persistSavedViews(views);
  input.value = '';
  renderSavedViews();
});

document.getElementById('view-name-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('btn-save-view').click();
});

document.getElementById('saved-views-list').addEventListener('click', (e) => {
  if (e.target.classList.contains('view-load')) {
    const i = +e.target.dataset.i;
    const views = loadSavedViews();
    if (!views[i]) return;
    applySavedView(views[i].state);
  } else if (e.target.classList.contains('view-delete')) {
    const i = +e.target.dataset.i;
    const views = loadSavedViews();
    views.splice(i, 1);
    persistSavedViews(views);
    renderSavedViews();
  }
});

// ── Hover tooltip ────────────────────────────────────────────────
function tractTooltipHtml(props) {
  const m = PAYLOAD.metrics.find(x => x.id === state.metric);
  const v = props[m.id];
  const name = props.neighborhood_name
    ? `<b>${props.neighborhood_name}</b><br><span class="tip-geoid">Tract ${props.GEOID}</span>`
    : `<b>Tract ${props.GEOID}</b>`;
  return name + `<br>${m.label}: ${fmt(v, m.fmt)}` +
         `<br>Population: ${fmt(props.total_population, 'count')}`;
}

function refreshTooltips() {
  state.layerByGeoid.forEach((layer) => {
    if (layer.getTooltip()) {
      layer.setTooltipContent(tractTooltipHtml(layer.feature.properties));
    }
  });
}

state.layerByGeoid.forEach((layer) => {
  layer.bindTooltip(tractTooltipHtml(layer.feature.properties), {
    sticky: true, className: 'tract-tip', direction: 'top', offset: [0, -6],
  });
});

// ── Boot ─────────────────────────────────────────────────────────
// Sync UI to restored state.
document.querySelectorAll('.metric-list input').forEach(r => {
  r.checked = (r.value === state.metric);
});
setTab(state.activeTab);
renderFilterRows();
refreshFilterResult();
refreshAggregates();
refreshLegend();
renderSavedViews();
</script>
</body>
</html>
"""
