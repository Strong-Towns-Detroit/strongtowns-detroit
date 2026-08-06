# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a multi-project research repository analyzing Detroit housing policy, zoning regulations, and land use. The work supports Strong Towns-style analysis of how zoning and land-use regulations affect housing affordability and buildability. All projects are Python-based, focused on data analysis and geospatial visualization.

## Project Structure

### `housingDataAnalysis/` — Census & Housing Burden Analysis
Fetches ACS Census data at the tract level, aggregates to ZCTAs/block groups, and produces choropleth maps of housing cost burden in Detroit.

- `src/detroit_census_fetcher.py` — Core class `DetroitCensusFetcher` that pulls ACS variables (B25070, B25091, B19013, B25077) via `pytidycensus`, spatially joins tracts to target geographies, and computes burden metrics (30%+, 50%+ cost burden, price-to-income ratio)
- `src/detroit_maps_with_geography.py` — Multi-panel matplotlib map generation overlaying census data with OSMnx-derived street networks, water features, and boundaries
- `street_simplification/` — OSMnx graph simplification for Detroit street network (basic, strict, consolidation methods). Outputs GeoPackage/GraphML files used as base layers by the mapping scripts
- **Venv**: `.venv/` (Python 3.12)
- **Key deps**: geopandas, pytidycensus, censusdata, matplotlib, osmnx

### `parcel-data/` — Parcel Zoning Compliance & Preemption Analysis
Analyzes ~340K Detroit parcels to determine which violate current zoning minimums and which would be legalized under proposed state preemption (1,500 sq ft lot minimum, 500 sq ft dwelling minimum).

- **Data pipeline** (run in order):
  1. `calculate_buildable.py` — Reads `parcel-data-cleaned.csv` + `zoning_districts_to_lot_size_restrictions.json`, computes per-parcel compliance flags (violates current/proposed lot size, dwelling size)
  2. `merge_and_calculate.py` — Merges `Parcels.geojson` geometry with cleaned CSV data, recalculates compliance, outputs `parcels_with_compliance.csv` and `.gpkg`
  3. `analyze_preemption.py` — Reads compliance CSV, generates the preemption impact report (`preemption_analysis_report.md`) with lot size, dwelling size, and use-code legality metrics
  4. `map_parcels.py` — Renders buildability map from `.gpkg` data overlaid on geography layers from `housingDataAnalysis/street_simplification/output/`
- `zoning_use_mapper.py` — `ZoningMapper` class using SBERT (`all-MiniLM-L6-v2`) to semantically match parcel use codes to zoning-specific uses via cosine similarity
- `extract_tables_from_docx.py` — Parses zoning use tables from Detroit's municipal code DOCX
- **Venv**: `venv/` (Python 3.12)
- **Key deps**: geopandas, pandas, matplotlib, sentence-transformers, torch

### `zoning/` — BZA Meeting Minutes Dataset
Scrapes, OCRs, and parses Detroit Board of Zoning Appeals meeting minutes into a structured dataset.

- `scrape_bza_minutes.py` — Scrapes PDFs from detroitmi.gov BZA documents listing
- `rename_bza_minutes.py` — Renames downloaded PDFs to `yyyy-mm-dd` format
- `create_bza_dataset_from_minutes.py` — OCR extraction (Tesseract or RapidOCR) + regex parsing of case fields (case number, petitioner, location, proposal, decision, votes). Generates CSV/JSON dataset and HTML report of cases with unknown fields
  - Usage: `python create_bza_dataset_from_minutes.py --engine tesseract|rapidocr [--output DIR]`
  - Output directories: `bza_dataset_tesseract/`, `bza_dataset_rapidocr/`
- **No venv** — uses system Python; requires `PyPDF2`, `pytesseract`, `pdf2image`, `rapidocr_onnxruntime`, `beautifulsoup4`

## Running Scripts

Each subproject has its own virtual environment. Activate before running:

```bash
# housingDataAnalysis
source housingDataAnalysis/.venv/bin/activate
python housingDataAnalysis/src/detroit_census_fetcher.py

# parcel-data
source parcel-data/venv/bin/activate
python parcel-data/calculate_buildable.py

# zoning (no venv)
python zoning/create_bza_dataset_from_minutes.py --engine rapidocr
```

## Key Data Files (parcel-data)

Large CSV/GeoJSON files that are inputs to the pipeline (not checked into git):
- `parcel-data.csv` / `parcel-data-cleaned.csv` — Raw and cleaned parcel records
- `Parcels.geojson` — Parcel geometries (~985MB)
- `parcels_with_compliance.csv` / `.gpkg` — Pipeline output with compliance flags
- JSON config files: `zoning_districts_to_lot_size_restrictions.json`, `parcel_use_codes_to_zoning_districts_mapping.json`, `detroit_zoning.json`

## Architecture Notes

- The `DetroitCensusFetcher` caches tract-level data as Parquet in `housingDataAnalysis/cache/` to avoid repeated API calls. It requires a Census API key passed at init.
- The parcel compliance pipeline uses `pd.DataFrame.apply()` row-by-row for compliance checks. This is intentionally chosen for clarity over vectorized operations given the multi-column logic.
- Cross-project dependency: `map_parcels.py` in `parcel-data/` reads geography layers from `housingDataAnalysis/street_simplification/output/` (boundary, water, network GeoPackages).
- The `ZoningMapper` loads a sentence-transformers model into memory. The `all-MiniLM-L6-v2` model is the default (fast/lightweight); `all-mpnet-base-v2` is available for higher accuracy.
- Detroit residential zoning districts referenced throughout: R1-R6, SD1, SD2.
