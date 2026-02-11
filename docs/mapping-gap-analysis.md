# Mapping Subpackage Gap Analysis

`src/strongtowns_detroit/mapping/` contains only an empty `__init__.py`. All geospatial
plotting logic remains in two scripts with no library code extracted.

---

## Source Scripts

### 1. `scripts/parcel-data/map_parcels.py` — Parcel Buildability Map

Single-panel choropleth showing buildable vs non-buildable parcels across Detroit.

**Extractable logic:**

| Function | What it does |
|---|---|
| Color-mapping parcels by `isBuildable` | `True` → navy (`#0C2340`), `False` → orange (`#FA4616`) |
| Special-case handling | Detroit Parks & Recreation parcels greyed out |
| Layer composition | Water (z=1) → Parcels (z=2) → Boundary outline (z=3) |
| Legend construction | `matplotlib.patches.Patch` legend for buildable/not/unknown |

**Hardcoded values:**
- `water_color = '#53A9D4'`
- `buildable_color = '#0C2340'`
- `not_buildable_color = '#FA4616'`
- Figure size `(20, 20)`, DPI 300
- Geography dir: `../housingDataAnalysis/street_simplification/output`

Already uses `geo.loader` for data loading — the remaining work is the plotting itself.

---

### 2. `scripts/housingDataAnalysis/src/detroit_maps_with_geography.py` — Housing Burden Maps

Two multi-panel figures with shared geographic context layers.

**Extractable logic:**

#### `add_geography_layers(ax, boundary, water, edges, gdf_analysis)`
Reusable function that adds water, streets, and boundary to any matplotlib axis:
- CRS-syncs all layers to the analysis GeoDataFrame
- Clips all layers to the analysis bounding box
- Consistent z-ordering: water (z=1) → analysis data (z=2) → streets (z=3) → boundary (z=4)
- Consistent styling: water `#c6e3f0`, streets `#666666` at 0.2lw, boundary `#2c3e50` dashed

This is the most reusable piece — it's called 7 times across the two figure builders.

#### `create_four_panel_map_with_geography(...)`
Four-panel housing cost burden choropleth:
1. Renter burden 30%+ (`pct_renters_30plus`)
2. Owner burden 30%+ (`pct_owners_30plus`)
3. All household burden 30%+ (`pct_burden_30plus_all`)
4. Severe burden 50%+ (`pct_burden_50plus_all`)

Uses `mapclassify` `UserDefined` scheme with bins `[20, 30, 40, 50, 60]` and `YlOrRd` colormap.

#### `create_three_panel_map_with_geography(...)`
Three-panel housing market health figure:
1. Housing shortage (price/income > 3) — red/gray binary
2. Renter accessibility crisis (>50% burdened) — blue/gray binary
3. Combined categories — red/blue/purple/gray

Uses manual color mappings per category.

**Hardcoded values:**
- `ALPHA_BLOCKGROUPS = 0.6`
- `BINS = [20, 30, 40, 50, 60]`
- Color palettes for shortage (`#b82f23`), accessibility (`#1d5782`), both (`#6d29ac`)
- Figure sizes: four-panel `(20, 18)`, three-panel `(26, 9)`

---

## What Should Move to the Package

### Tier 1 — High reuse, low coupling

**`add_geography_layers()`** is the clearest extraction target. It's a pure rendering
function with no data pipeline dependencies — give it an axis and GeoDataFrames, it
draws them. Currently called 7 times in one script, and `map_parcels.py` does the same
thing manually with slightly different styling.

A generalized version could accept styling parameters:

```python
def add_geography_layers(
    ax, boundary, water, edges, ref_gdf, *,
    water_color='#c6e3f0', water_alpha=0.7,
    street_color='#666666', street_lw=0.2, street_alpha=0.4,
    boundary_color='#2c3e50', boundary_lw=2, boundary_style='--',
    clip_to_bounds=True,
):
```

### Tier 2 — Moderate reuse, some coupling

**Color palette constants** — the project's visual identity:

```python
# Parcel buildability
BUILDABLE_COLOR = '#0C2340'
NOT_BUILDABLE_COLOR = '#FA4616'

# Housing burden
WATER_COLOR = '#c6e3f0'
SHORTAGE_COLOR = '#b82f23'
ACCESSIBILITY_COLOR = '#1d5782'
BOTH_ISSUES_COLOR = '#6d29ac'
NEUTRAL_COLOR = '#d9d9d9'
```

**Legend builder** — both scripts construct `Patch` legends manually. A helper would
reduce boilerplate:

```python
def make_patch_legend(ax, color_labels, *, loc='lower right', alpha=1.0):
    """Build a Patch legend from a {color: label} dict."""
```

### Tier 3 — Low reuse, high coupling

The figure-builder functions (`create_four_panel_map_with_geography`,
`create_three_panel_map_with_geography`, `map_parcels`) are tightly coupled to specific
data schemas (column names like `pct_renters_30plus`, `isBuildable`). These could be
moved but would primarily serve as reference implementations rather than general-purpose
utilities.

---

## Recommended Package Structure

```
src/strongtowns_detroit/mapping/
├── __init__.py
├── layers.py        # add_geography_layers(), make_patch_legend()
└── colors.py        # Color palette constants
```

The figure-building functions can stay in their scripts, calling into `mapping.layers`
for the geographic context rendering.

---

## Current Dependencies

Both scripts already depend on the package (`geo.loader`). Adding `mapping.layers`
would create a clean dependency chain:

```
geo.loader  →  load/prepare data
mapping.layers  →  render data onto axes
scripts  →  orchestrate: load → compute → render → save
```

No new external dependencies — everything uses `matplotlib` and `geopandas`, which are
already required.
