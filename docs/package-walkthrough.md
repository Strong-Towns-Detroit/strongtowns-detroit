# `strongtowns_detroit` Package Walkthrough

This document walks through the `strongtowns_detroit` Python package — what it does,
how it's organized, and how each module connects to the data analysis pipeline.

---

## Why a Package?

The Detroit zoning/housing analysis started as three independent script directories
(`pipelines/parcel-data/`, `pipelines/housingDataAnalysis/`, `pipelines/zoning/`), each
with their own copies of constants, helper functions, and loading logic.

The `strongtowns_detroit` package extracts the **reusable logic** from those 20+
scripts into one importable library. The original scripts still exist — they're now
thin wrappers that call into the package with their specific configuration.

Benefits:
- **Single source of truth** — constants like `PROPOSED_MIN_SQFT = 1500` are defined
  once in `constants.py`, not duplicated across files
- **Testability** — pure functions can be unit-tested without running the full pipeline
- **Composability** — modules can be imported and combined in new ways (notebooks,
  new scripts, etc.)

---

## Package Layout

```
src/strongtowns_detroit/
├── __init__.py              # Package root
├── constants.py             # Zoning thresholds, residential zones, use-code groups
├── config.py                # .env-based API key loading, JSON config reader
├── parcels/                 # Parcel zoning analysis
│   ├── compliance.py        # Unified check_compliance() function
│   ├── preemption.py        # is_vacant() vacancy detector
│   ├── docx_parser.py       # Word document table expander (merged cells)
│   ├── zoning_json.py       # CSV-to-JSON zoning use table parser
│   └── semantic_mapper.py   # SBERT-based use code ↔ zoning use matcher
├── census/                  # Census data
│   └── fetcher.py           # DetroitCensusFetcher (ACS tract → ZCTA aggregation)
├── bza/                     # Board of Zoning Appeals
│   ├── scraper.py           # Download BZA minutes PDFs from detroitmi.gov
│   ├── renamer.py           # Normalize PDF filenames to YYYY-MM-DD format
│   └── parser.py            # Extract structured case data from OCR'd text
├── geo/                     # Geographic data utilities
│   ├── loader.py            # Load boundary/water/streets GeoPackages
│   └── streets.py           # Compare original vs simplified street networks
├── mapping/                 # Detroit map rendering
│   ├── colors.py            # Color palettes, z-order, display constants
│   └── layers.py            # add_geography_layers(), make_patch_legend()
└── zoning/                  # Zoning ordinance parser
    ├── models.py            # UsePermission, DimensionalStandard, ZoningDefinition, SectionNode
    ├── table_parser.py      # XML-level table expansion (merged cells)
    ├── document.py          # Section hierarchy parser
    ├── use_tables.py        # Type A: use permission matrices
    ├── dimensional.py       # Type B: dimensional standards
    ├── definitions.py       # Type C: definition lookups
    └── ordinance.py         # Orchestrator + JSON/CSV export
```

---

## Module-by-Module Walkthrough

### `constants.py` — The Numbers That Drive the Analysis

```python
PROPOSED_MIN_SQFT = 1500                  # Michigan preemption bill's proposed minimum lot size
PROPOSED_MIN_DWELLING_SQFT = 500          # Proposed minimum dwelling size
CURRENT_MIN_DWELLING_ASSUMPTION = 1000    # Assumed current minimum dwelling size

RESIDENTIAL_ZONES = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'SD1', 'SD2']
```

These thresholds come from Michigan's proposed zoning preemption legislation. The
analysis asks: *"If the state imposed these minimums, how many Detroit parcels would
suddenly be non-compliant?"*

The use-code key groups (`TARGET_KEYS`, `DUPLEX_KEYS`, `MULTI_FAMILY_KEYS`,
`ADU_KEYS`) classify parcel use descriptions into housing categories for the
preemption impact report.

**Used by:** `parcels/compliance.py`, `analyze_preemption.py`

---

### `config.py` — Configuration Without Hardcoded Secrets

```python
def get_census_api_key() -> str:
    """Load Census API key from .env file or environment."""
```

Loads `CENSUS_API_KEY` from a `.env` file at the project root via `python-dotenv`.
This replaces what were previously hardcoded API keys scattered across Census scripts.

`load_json_config(path)` is a small utility for loading the JSON config files that
the parcel pipeline depends on (zoning restrictions, use code mappings, etc.).

**Used by:** `census/fetcher.py`, `verify_vars.py`

---

### `parcels/compliance.py` — The Heart of the Parcel Analysis

This is the most interesting module architecturally. The original codebase had **two
different `check_compliance()` functions** that did similar things with subtle
differences:

| Aspect | `calculate_buildable.py` | `merge_and_calculate.py` |
|---|---|---|
| District column | `zoning_district` | `zoning` |
| Area column | `shape_area` (one column) | `total_square_footage_csv` → fallback chain of 5 columns |
| Width check | Yes (`frontage`) | No |
| Buildable flag | Yes (`is_buildable_current_zoning`) | No |

The unified version resolves this with **keyword-only parameters**:

```python
def check_compliance(
    row,
    zoning_restrictions,
    *,                              # Everything below is keyword-only
    district_col='zoning_district',
    area_cols=('shape_area',),      # Tuple — tried in order, first non-NaN wins
    floor_area_col='total_floor_area',
    width_col=None,                 # None = skip width checks entirely
    include_buildable=False,        # True = add is_buildable_current_zoning
):
```

Each original script becomes a one-line wrapper that passes its specific config:

```python
# calculate_buildable.py — uses shape_area + frontage, wants buildable flag
_unified_check(row, zoning_restrictions,
    district_col='zoning_district',
    area_cols=('shape_area',),
    width_col='frontage',
    include_buildable=True)

# merge_and_calculate.py — uses area fallback chain, no width, no buildable
_unified_check(row, zoning_restrictions,
    district_col='zoning',
    area_cols=('total_square_footage_csv', 'total_square_footage_geo',
               'total_square_footage', 'shape_area', 'Shape__Area'))
```

The `area_cols` tuple implements a **priority fallback chain**: it tries each column
in order and uses the first value that's non-NaN and non-zero. This matters because
Detroit parcel data has multiple area fields with different provenance and reliability.

**Used by:** `calculate_buildable.py`, `merge_and_calculate.py`

---

### `parcels/preemption.py` — Vacancy Detection

```python
def is_vacant(desc):
    """Determine if a parcel use-code description indicates vacancy."""
    if pd.isna(desc):
        return True
    d = desc.upper()
    return 'VACANT' in d or 'NO BLDG' in d or 'IMPROVED NO BLDG' in d
```

Simple but critical — this function classifies whether a parcel is vacant based on
its use-code description text. NaN descriptions are treated as vacant. The preemption
analysis uses this to separate "existing buildings that would become non-conforming"
from "empty lots where new construction would be affected."

**Used by:** `analyze_preemption.py`

---

### `parcels/docx_parser.py` — Extracting Tables from Word Documents

Detroit's official zoning use regulations are published as a Word document with
complex merged-cell tables. This module handles the gnarly work of expanding those
tables into clean 2D grids.

- **`get_cell_spans(cell)`** — reads the raw XML of a `python-docx` cell to determine
  its horizontal (`gridSpan`) and vertical (`vMerge`) merge extents
- **`expand_table(table)`** — walks a Word table row-by-row, tracking merge starts
  and continuations, to produce a flat `list[list[str]]` grid

The vertical merge tracking is the tricky part: `vMerge` with `val="restart"` marks
the start of a merged region, `vMerge` without a value marks continuation cells. The
algorithm walks upward from continuations to find the original merge-start cell.

**Used by:** `extract_tables_from_docx.py`

---

### `parcels/zoning_json.py` — Building the Zoning Permission Database

```python
def parse_zoning_csv(csv_file):
    """Parse Detroit zoning use table CSV into structured JSON."""
```

Takes the CSV output from `extract_tables_from_docx.py` and builds a structured dict
of zoning permissions. For each land use, it records which zoning districts allow it:
- `R` = by-right
- `C` = conditional use permit required
- `C/R` or `R/C` = mixed (by-right with conditions)

The output is `detroit_zoning.json`, the core lookup table for determining what you
can build where.

**Used by:** `build_use_code.py`

---

### `parcels/semantic_mapper.py` — AI-Powered Use Code Matching

The city's parcel database uses its own use-code descriptions (e.g., "SINGLE FAMILY",
"APT-FLAT GARDEN TYPE") that don't directly match the zoning ordinance's specific
land use names. This module bridges that gap using SBERT (Sentence-BERT) embeddings.

The `ZoningMapper` class:
1. Loads a sentence-transformer model (`all-MiniLM-L6-v2`)
2. Encodes both the parcel use codes and the zoning-specific uses into embedding vectors
3. Computes cosine similarity via dot product
4. Classifies matches as high (≥0.75), medium (≥0.60), or low confidence

High-confidence matches are auto-accepted into the final mapping. This enables the
pipeline to determine, for a given parcel, whether its current use would be legal
in its zoning district — a key input to the preemption analysis.

**Used by:** `zoning_use_mapper.py`

---

### `census/fetcher.py` — Housing Burden Metrics from the Census

`DetroitCensusFetcher` pulls American Community Survey (ACS) data at the census tract
level and aggregates it up to ZIP Code Tabulation Areas (ZCTAs).

Key metrics calculated:
- **Housing cost burden** — % of renters/owners spending >30% of income on housing
- **Severe burden** — % spending >50% on housing
- **Price-to-income ratio** — median home value ÷ median household income
- **Housing categories** — "Both Issues", "Shortage Only", "Accessibility Only", "Neither"

The 30% threshold is the standard HUD definition of housing affordability.

The constructor accepts an optional `api_key`. If omitted, it lazy-loads from `.env`
via `config.get_census_api_key()`:

```python
def __init__(self, api_key: Optional[str] = None, cache_dir: str = './cache'):
    if api_key is None:
        from strongtowns_detroit.config import get_census_api_key
        api_key = get_census_api_key()
```

The lazy import avoids hard-coupling the Census module to dotenv when a key is
provided directly (useful in tests).

**Used by:** `detroit_census_fetcher.py`, `run_detroit_analysis.py`

---

### `bza/scraper.py` — Downloading BZA Meeting Minutes

Scrapes PDF files of Board of Zoning Appeals meeting minutes from
`detroitmi.gov/documents`. It:
1. Paginates through the document listing filtered to "BZA Meeting Minutes"
2. Follows each document link to find the PDF download URL
3. Downloads with rate limiting (1-2 second delays) and duplicate detection
4. Validates that downloaded content is actually a PDF (`%PDF` magic bytes)

**Used by:** `scrape_bza_minutes.py`

---

### `bza/renamer.py` — Normalizing PDF Filenames

BZA minutes PDFs come with inconsistent filenames like
`January_14__2020_BZA_Minutes.pdf` or `01142020_bza.pdf`. This module extracts dates
from filenames using multiple regex patterns and normalizes them to
`YYYY-MM-DD_bza_minutes.pdf`.

`parse_date()` tries four patterns in order:
1. Month word + DD + YYYY (e.g., "January_14__2020")
2. MM-DD-YYYY or MM_DD_YYYY
3. 8-digit MMDDYYYY
4. 7-digit (ambiguous — tries both M-DD-YYYY and MM-D-YYYY)

**Used by:** `rename_bza_minutes.py`

---

### `bza/parser.py` — Extracting Structured Data from OCR'd Minutes

Takes raw OCR text from BZA meeting minutes and extracts structured case records using
regex patterns. Each case includes:

| Field | Example |
|---|---|
| `case_number` | `2024-01` |
| `petitioner` | `John Doe` |
| `location` | `1234 Woodward Ave` |
| `proposal` | `To construct a two-family dwelling...` |
| `decision` | `GRANTED` |
| `affirmative_votes` | `Smith, Jones, Williams` |

The parser splits text on `CASE NO.:` boundaries, then applies field-specific regexes
within each case block. Decision detection walks backward through lines looking for
GRANTED/DENIED/APPROVED keywords.

**Used by:** `create_bza_dataset_from_minutes.py`

---

### `geo/loader.py` — Geography Data Loading

Three scripts were independently loading the same GeoPackage files (boundary, water,
streets). This module consolidates that into:

- **`load_geography(dir, *, load_streets=False)`** — loads `.gpkg` files from a
  directory, returning `(boundary, water, edges)` with `None` for missing files
- **`prepare_water(water, ref_gdf, *, filter_lake=True)`** — CRS-syncs water features
  to a reference GeoDataFrame, optionally removes Lake St. Clair, and clips to bounds
- **`sync_crs(*gdfs, target_crs=None)`** — reprojects one or more GeoDataFrames to a
  common CRS. Returns a single GDF if one was passed, a tuple if multiple were passed

Lake St. Clair filtering matters because the Great Lakes water polygon dominates the
map extent if included.

**Used by:** `map_parcels.py`, `detroit_maps_with_geography.py`

---

### `geo/streets.py` — Street Network Comparison

```python
def compare_networks(G_original, G_simplified, title="Network Comparison"):
```

Compares original vs simplified OSMnx street networks, printing node/edge counts and
reduction percentages. The street simplification pipeline reduces Detroit's road
network from ~90K nodes to ~10K while preserving topology, and this function reports
how much was simplified.

**Used by:** `osmnx_detroit_simplification_enhanced.py`

---

### `mapping/colors.py` — Detroit's Visual Identity

Library-agnostic color constants (plain hex strings, no matplotlib import) so any
plotting library can use them:

```python
from strongtowns_detroit.mapping.colors import BUILDABLE, NOT_BUILDABLE, SHORTAGE

# Works with matplotlib, folium, plotly, deck.gl, etc.
```

Organized by domain:

| Group | Constants |
|---|---|
| Geographic layers | `WATER_FILL`, `WATER_EDGE`, `WATER_PARCEL`, `STREET`, `BOUNDARY` |
| Parcel buildability | `BUILDABLE` (navy), `NOT_BUILDABLE` (orange) |
| Housing burden | `SHORTAGE` (red), `ACCESSIBILITY_CRISIS` (blue), `BOTH_ISSUES` (purple), `NEUTRAL` (gray) |
| Category lookups | `HOUSING_CATEGORY_COLORS`, `SHORTAGE_COLORS`, `ACCESSIBILITY_COLORS` |
| Choropleth defaults | `BURDEN_CMAP`, `BURDEN_BINS`, `ALPHA_BLOCKGROUPS` |
| Layer stacking | `Z_WATER=1`, `Z_DATA=2`, `Z_STREETS=3`, `Z_BOUNDARY=4` |

**Used by:** `mapping/layers.py`, `map_parcels.py`, `detroit_maps_with_geography.py`

---

### `mapping/layers.py` — Geographic Context Rendering (matplotlib)

Two functions for composing Detroit maps:

**`add_geography_layers(ax, boundary, water, edges, ref_gdf, **kwargs)`** draws
water, streets, and the municipal boundary onto a matplotlib axis. All layers are
CRS-synced to `ref_gdf` and optionally clipped to its bounding box. Called 7 times
across the two map scripts.

Every visual property can be overridden via keyword arguments, but the defaults give
you Detroit styling for free:

```python
add_geography_layers(ax, boundary, water, edges, my_data)  # Detroit defaults
add_geography_layers(ax, boundary, water, edges, my_data,
    water_color='#ff0000', street_lw=0.5)  # custom
```

**`make_patch_legend(ax, color_label_pairs, **kwargs)`** builds a matplotlib Patch
legend from `(hex_color, label)` pairs, replacing the 14 manual `Patch()` calls that
were scattered across the scripts.

**Used by:** `map_parcels.py`, `detroit_maps_with_geography.py`

---

### `zoning/models.py` — Structured Data Models

Four dataclasses represent the parsed zoning ordinance data:

- **`UsePermission`** — one cell from a use-permission matrix (use + district + permission code)
- **`DimensionalStandard`** — one row from a dimensional-standards table (district + standard + value as string)
- **`ZoningDefinition`** — one term/definition pair from a lookup table
- **`SectionNode`** — a node in the document hierarchy (Article → Division → Section) with content paragraphs and attached tables

Values are kept as strings because units vary (sq ft, ft, %, stories). Downstream consumers can convert as needed.

---

### `zoning/table_parser.py` — XML-Level Table Expansion

The heart of the zoning parser. Article XIII tables crash `python-docx`'s `row.cells`
with `ValueError: no tc element at grid_offset` because of complex merged cells. This
module bypasses python-docx entirely — it opens the .docx as a ZIP, reads
`word/document.xml`, and uses lxml XPath to find `<w:tbl>` elements.

`expand_table_xml(tbl)` handles:
- `<w:gridSpan>` — horizontal cell merges
- `<w:vMerge>` — vertical cell merges (start vs continuation)
- Nested paragraphs within cells

`classify_table(grid)` uses heuristics to identify the three table types:
- **use_matrix** — 20+ columns, header contains district codes (R1, R2, etc.)
- **dimensional** — fewer columns, header contains "Standard"/"Minimum"/"Maximum" keywords
- **lookup** — exactly 2 columns

**Used by:** `zoning/use_tables.py`, `zoning/dimensional.py`, `zoning/definitions.py`, `zoning/document.py`

---

### `zoning/document.py` — Section Hierarchy Parser

Parses the paragraph-level structure of a .docx into a tree of `SectionNode`s using
paragraph style names:
- Heading 3 → Article level
- Heading 4 → Division level
- Heading 5 → Section level

Tables are attached to the most recent section node. `walk_sections()` provides
depth-first traversal, and `find_sections()` filters by section number regex.

**Used by:** `zoning/ordinance.py`

---

### `zoning/use_tables.py`, `zoning/dimensional.py`, `zoning/definitions.py` — Type-Specific Extractors

Each module handles one table format:
- **use_tables.py** — Type A matrices: first column = use names, header = district codes, cells = permission codes (R/C/C|R/—)
- **dimensional.py** — Type B standards: districts as rows, standard names as columns, with spanning-row detection for category headers
- **definitions.py** — Type C lookups: 2-column term/definition pairs with header detection

---

### `zoning/ordinance.py` — Orchestrator

Ties all parsers together:

```python
data = parse_ordinance(Path("resources/"))
# data['use_permissions']        → list[UsePermission]
# data['dimensional_standards']  → list[DimensionalStandard]
# data['definitions']            → list[ZoningDefinition]
# data['sections']               → list[SectionNode]

export_to_json(data, Path("output/"))  # 4 JSON files
export_to_csv(data, Path("output/"))   # 3 CSV files
```

**Used by:** `pipelines/zoning-parser/parse_ordinance.py`

---

## How Scripts Became Thin Wrappers

The migration pattern is consistent across all 20+ scripts. Here's the anatomy:

**Before** (logic + I/O mixed together):
```python
# calculate_buildable.py (before)
PROPOSED_MIN_SQFT = 1500           # Duplicated constant
PROPOSED_MIN_DWELLING_SQFT = 500   # Duplicated constant

def check_compliance(row, zoning_restrictions):
    # 50 lines of compliance logic...

if __name__ == "__main__":
    df = pd.read_csv(...)
    df.apply(check_compliance, ...)
    df.to_csv(...)
```

**After** (thin wrapper → library):
```python
# calculate_buildable.py (after)
from strongtowns_detroit.parcels.compliance import check_compliance as _unified_check
from strongtowns_detroit.constants import PROPOSED_MIN_SQFT, PROPOSED_MIN_DWELLING_SQFT

def check_compliance(row, zoning_restrictions):
    """Thin wrapper: delegates to unified compliance with calculate_buildable settings."""
    return _unified_check(row, zoning_restrictions,
        district_col='zoning_district',
        area_cols=('shape_area',),
        width_col='frontage',
        include_buildable=True)

if __name__ == "__main__":
    df = pd.read_csv(...)         # I/O stays in the script
    df.apply(check_compliance, ...)
    df.to_csv(...)
```

The simplest cases are pure re-exports:
```python
# detroit_census_fetcher.py (after)
"""Thin re-export — the real implementation lives in strongtowns_detroit.census.fetcher."""
from strongtowns_detroit.census.fetcher import DetroitCensusFetcher
```

---

## Running the Data Pipeline

The scripts are still the entry points. Run them from their directories as before:

```bash
# Parcel analysis pipeline (from pipelines/parcel-data/)
python extract_tables_from_docx.py     # Word doc → CSV
python build_use_code.py               # CSV → detroit_zoning.json
python zoning_use_mapper.py            # SBERT matching → use mappings
python merge_and_calculate.py          # Parcels + zoning → compliance CSV + GPKG
python analyze_preemption.py           # Compliance → preemption report

# Census analysis (from pipelines/housingDataAnalysis/)
python src/pipelines/run_detroit_analysis.py   # Needs CENSUS_API_KEY in .env

# BZA extraction (from pipelines/zoning/)
python scrape_bza_minutes.py           # Download PDFs
python rename_bza_minutes.py           # Normalize filenames
python create_bza_dataset_from_minutes.py --engine tesseract
```

---

## Testing

```bash
# From the project root
.venv/bin/python -m pytest tests/ -v --tb=short
```

236 tests, ~1 second. Heavy dependencies (pytidycensus, osmnx,
sentence-transformers, pytesseract) are mocked in `tests/conftest.py` so tests run
without installing them.

---

## Configuration

Create a `.env` file at the project root:

```
CENSUS_API_KEY=your_key_here
```

Get a free key at [api.census.gov/data/key_signup.html](https://api.census.gov/data/key_signup.html).
Only needed if running Census-related scripts.
