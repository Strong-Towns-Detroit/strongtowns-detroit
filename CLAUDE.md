# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Data analysis and policy research project examining Detroit's zoning, housing, and land use. The project analyzes the impact of Michigan's proposed zoning preemption legislation on Detroit parcels, including lot size compliance, dwelling size caps, and missing middle housing legality. It also includes Census-based housing analysis and Board of Zoning Appeals (BZA) meeting minutes extraction.

## Repository Structure

Three independent Python sub-projects live under `pipelines/`:

### `pipelines/parcel-data/` — Parcel Zoning & Preemption Analysis
Data pipeline that processes Detroit parcel data against zoning regulations:
1. **`extract_tables_from_docx.py`** — Parses Detroit's zoning use tables from a Word document into CSV (`merged_tables.csv`)
2. **`build_use_code.py`** — Converts the CSV use tables into structured JSON (`detroit_zoning.json`)
3. **`zoning_use_mapper.py`** — Uses SBERT (sentence-transformers) to semantically match parcel use codes to zoning-specific uses
4. **`merge_and_calculate.py`** — Merges `Parcels.geojson` with `parcel-data-cleaned.csv`, calculates compliance metrics, outputs `parcels_with_compliance.csv` and `.gpkg`
5. **`calculate_buildable.py`** — Alternative compliance calculator (CSV-only, no geometry merge)
6. **`analyze_preemption.py`** — Generates the final preemption impact report (`preemption_analysis_report.md`) with statistics on lot size, dwelling size, and use code legality
7. **`map_parcels.py`** — Creates matplotlib maps of buildable vs non-buildable parcels using geography from `housingDataAnalysis/street_simplification/output/`

Key data files: `zoning_districts_to_lot_size_restrictions.json`, `parcel_use_codes_to_zoning_districts_mapping.json`, `parcel_uses_to_zoning_uses_mapping.json`

### `pipelines/housingDataAnalysis/` — Census & Housing Data
- **`src/detroit_census_fetcher.py`** — Fetches ACS data via `pytidycensus`, aggregates tract-level data to ZCTAs, calculates housing burden metrics (30%+ income threshold)
- **`src/detroit_maps_with_geography.py`** — Map rendering with geographic layers
- **`street_simplification/`** — OSMnx-based street network simplification; outputs boundary, water, and network GeoPackages used by `parcel-data/map_parcels.py`
- **`search_tables.py`, `scan_vars.py`, `verify_vars.py`** — Census variable discovery utilities

### `pipelines/zoning-parser/` — Zoning Ordinance Parser
- **`parse_ordinance.py`** — CLI wrapper that parses all 18 .docx articles from `resources/` into structured JSON + CSV datasets

### `pipelines/zoning/` — BZA Minutes Extraction
- **`scrape_bza_minutes.py`** — Scrapes BZA meeting minutes PDFs from detroitmi.gov
- **`rename_bza_minutes.py`** — Normalizes PDF filenames to `YYYY-MM-DD_bza_minutes.pdf` format
- **`create_bza_dataset_from_minutes.py`** — OCR pipeline (Tesseract or RapidOCR) that extracts structured case data (case number, petitioner, location, proposal, decision, votes) from PDFs into JSON/CSV datasets

## Environment Setup

Each sub-project has its own Python virtual environment (Python 3.12):

```bash
# parcel-data
cd pipelines/parcel-data
source venv/bin/activate
# No requirements.txt — install: pandas, geopandas, matplotlib, sentence-transformers, python-docx, lxml

# housingDataAnalysis
cd pipelines/housingDataAnalysis
source .venv/bin/activate
pip install -r requirements.txt  # jupyter, censusdata, pyCensus, cenpy, geopandas, pandas, requests, matplotlib

# street_simplification (sub-environment)
pip install -r street_simplification/requirements.txt  # osmnx, networkx, matplotlib, pandas, geopandas

# zoning — uses parcel-data venv or its own
# Requires: requests, beautifulsoup4, PyPDF2, pytesseract, pdf2image, rapidocr-onnxruntime, numpy
```

## Running Pipelines

All scripts use `if __name__ == "__main__":` and are run directly. Scripts expect to be run from their own directory due to relative file paths.

```bash
# Parcel analysis pipeline (run in order, from pipelines/parcel-data/)
python extract_tables_from_docx.py
python build_use_code.py
python merge_and_calculate.py       # or calculate_buildable.py
python analyze_preemption.py
python map_parcels.py

# Zoning ordinance parsing (from pipelines/zoning-parser/)
python parse_ordinance.py           # reads resources/*.docx, outputs JSON + CSV

# BZA extraction (from pipelines/zoning/)
python scrape_bza_minutes.py
python rename_bza_minutes.py
python create_bza_dataset_from_minutes.py --engine tesseract  # or --engine rapidocr
```

## Key Technical Details

- **Parcel join key**: GeoJSON uses `parcel_number`, CSV uses `parcel_id` — `merge_and_calculate.py` renames to align
- **Area field ambiguity**: `shape_area` (geometric, small values ~1290) vs `total_square_footage` (legal, ~7400 mean) — `merge_and_calculate.py` prefers `total_square_footage`
- **Preemption thresholds**: Proposed min lot = 1,500 sqft, proposed min dwelling = 500 sqft, assumed current min dwelling = 1,000 sqft
- **Residential zones**: R1, R2, R3, R4, R5, R6, SD1, SD2
- **Zoning permissions**: `R` = by-right, `C` = conditional, `C/R` or `R/C` = mixed
- **Census API**: `detroit_census_fetcher.py` requires a Census API key passed to the constructor
- **Cross-project dependency**: `map_parcels.py` reads geography files from `../housingDataAnalysis/street_simplification/output/` (within `pipelines/`)

## Shared Package: `src/strongtowns_detroit/`

Reusable library imported by all pipelines. Key modules:

```
src/strongtowns_detroit/
├── constants.py, config.py          # Thresholds, API key loading
├── parcels/                         # Parcel zoning analysis
│   ├── compliance.py                # Unified check_compliance()
│   ├── preemption.py, docx_parser.py, zoning_json.py, semantic_mapper.py
├── census/fetcher.py                # ACS data fetcher
├── bza/                             # BZA minutes extraction
│   ├── scraper.py, renamer.py, parser.py
├── geo/                             # Geography utilities
│   ├── loader.py, streets.py
├── mapping/                         # Map rendering
│   ├── colors.py, layers.py
└── zoning/                          # Zoning ordinance parser + knowledge graph
    ├── models.py                    # UsePermission, DimensionalStandard, ZoningDefinition, SectionNode, Citation, CitationGraph
    ├── table_parser.py              # XML-level table expansion (handles merged cells)
    ├── document.py                  # Section hierarchy parser (walk_sections, parse_document)
    ├── use_tables.py                # Type A: use permission matrices
    ├── dimensional.py               # Type B: dimensional standards
    ├── definitions.py               # Type C: definition lookups
    ├── ordinance.py                 # Orchestrator: parse_ordinance() + JSON/CSV export
    ├── citations.py                 # Citation extraction + CitationGraph builder
    ├── ontology.py                  # MZO OWL/SKOS ontology (T-Box schema)
    ├── rdf_builder.py               # RDF knowledge graph builder (A-Box instance data)
    └── kg_queries.py                # SPARQL query tools for AI agent
```

## Knowledge Graph (`zoning/ontology.py`, `rdf_builder.py`, `kg_queries.py`)

RDF/OWL knowledge graph for answering zoning questions via SPARQL. Designed to be **municipality-agnostic** — the same ontology works for any US city.

### Architecture

- **Ontology (T-Box)**: `ontology.py` defines the MZO namespace (`http://municipalzoning.org/ontology#`) with 20 OWL classes, properties with typed domains/ranges, 4 SKOS concept schemes, and named individuals for enumerations (4 PermissionLevel, 11 RelationshipType, 4 ExternalLawType). `build_ontology()` returns a schema-only `rdflib.Graph`.
- **RDF Builder (A-Box)**: `rdf_builder.py` converts parsed ordinance data into RDF triples layered on the ontology. `build_rdf_graph()` is the main entry point. Six private sub-builders handle document structure, districts, use permissions, dimensional standards, definitions, and cross-references (with context sentence extraction + relationship classification via 10 regex patterns).
- **Query Tools**: `kg_queries.py` provides 8 SPARQL query functions the AI agent calls: `query_use_permissions`, `query_dimensional_standards`, `query_definition`, `query_cross_references`, `query_concept_hierarchy`, `bfs_traverse`, `query_sections_by_topic`, `query_related_concepts`.

### Key Concepts

- **Municipality-scoped URIs**: All instance URIs include the city name (e.g., `http://municipalzoning.org/detroit/section/50-12-101`, `http://municipalzoning.org/detroit/district/R1`). Multiple cities can coexist in one graph.
- **Reified triples**: `UsePermission` and `CrossReference` are reified — they're nodes connecting multiple entities (use + district + permission, or from_section + to_section + relationship_type) because RDF triples can't carry attributes directly.
- **SKOS for hierarchies**: Districts and land uses are modeled as SKOS concepts with `broader`/`narrower` relationships rather than OWL class hierarchies, because zoning categories are classification schemes, not strict logical taxonomies.
- **Relationship classification**: Cross-reference edges are annotated with one of 11 RelationshipType values (defines, constrains, requires, excepts, references, authorizes, delegates, supplements, incorporates, supersedes, unknown) based on regex matching of the surrounding sentence context.
- **Symbolic SPARQL, not embeddings**: Queries use exact pattern matching. No vector embeddings or ML. This is intentional — zoning is a legal domain where precision and traceability to source text matter.

### Building a Knowledge Graph

```python
from pathlib import Path
from strongtowns_detroit.zoning.ordinance import parse_ordinance
from strongtowns_detroit.zoning.citations import build_citation_graph
from strongtowns_detroit.zoning.rdf_builder import build_rdf_graph, export_graph

# 1. Parse ordinance .docx files
data = parse_ordinance(Path("resources"))

# 2. Build citation graph
citation_graph = build_citation_graph(data["sections"], resolve_hierarchical=False)

# 3. Build RDF knowledge graph (ontology + instance data)
rdf = build_rdf_graph(
    citation_graph=citation_graph,
    sections=data["sections"],
    use_permissions=data["use_permissions"],
    dimensional_standards=data["dimensional_standards"],
    definitions=data["definitions"],
    use_categories=None,  # or load from detroit_zoning.json for SKOS hierarchy
    municipality="detroit",
    chapter="50",
)

# 4. Export
export_graph(rdf, Path("output/detroit_zoning.ttl"))
```

### Querying

```python
from strongtowns_detroit.zoning.kg_queries import (
    query_use_permissions,
    query_dimensional_standards,
    query_definition,
    query_cross_references,
    bfs_traverse,
)

# What uses are allowed by-right in R1?
query_use_permissions(rdf, district="R1", permission="by_right")
# → [{"use": "Single-family dwelling", "district": "R1", "permission": "by_right", "conditions": ""}]

# What's the minimum lot size in R1?
query_dimensional_standards(rdf, district="R1", standard_type="lot area")
# → [{"district": "R1", "standard": "Minimum Lot Area", "value": "5,000 sq ft", "unit": "sq ft"}]

# What does "dwelling" mean?
query_definition(rdf, "dwelling")
# → "A building designed for residential use."

# What does section 50-12-127 cite? What cites it?
query_cross_references(rdf, "50-12-127", direction="both")
# → [{"from_section": ..., "to_section": ..., "relationship": "requires", "context": "..."}]

# BFS traversal from a section
bfs_traverse(rdf, "50-12-101", max_depth=2)
# → {"start": "50-12-101", "layers": [{...}, {...}, {...}]}
```

### Dependencies

- `rdflib` 7.5.0 (pure Python, includes SPARQL engine)

### Gotcha

`MZO.term` returns the Namespace `.term()` method, not a URIRef. Use `MZO["term"]` bracket notation for any property that collides with Python method names.

### Data Model Summary

| Parsed Data | RDF Class | Key Properties |
|------------|-----------|----------------|
| `SectionNode` | `mzo:Section` | `sectionNumber`, `sectionContent`, `inArticle` |
| `UsePermission` | `mzo:UsePermission` | `permitsUse` → `mzo:LandUse`, `inDistrict` → `mzo:ZoningDistrict`, `permissionLevel` |
| `DimensionalStandard` | `mzo:DimensionalStandard` | `appliesTo`, `standardType`, `standardValue`, `standardUnit` |
| `ZoningDefinition` | `mzo:TermDefinition` | `mzo:term` (use `MZO["term"]`), `definitionText`, `definedInSection` |
| `Citation` edge | `mzo:CrossReference` | `fromSection`, `toSection`, `relationshipType`, `contextSentence` |
| District codes | `mzo:ZoningDistrict` + `skos:Concept` | `skos:notation`, `skos:broader` → `mzo:DistrictCategory` |
| Use categories | `mzo:LandUseCategory` + `skos:Concept` | `skos:narrower` → `mzo:LandUse` children |
