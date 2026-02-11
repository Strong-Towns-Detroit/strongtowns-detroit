# Detroit Data Analysis

Data analysis and policy research examining Detroit's zoning, housing, and land use. The project quantifies the impact of Michigan's proposed zoning preemption legislation on Detroit's 235,000+ residential parcels and builds a machine-readable knowledge graph of the city's zoning ordinance.

## What This Project Does

**Parcel-level zoning compliance analysis** — Merges Detroit's parcel dataset with zoning regulations to determine, for every residential lot in the city, whether it complies with current rules and how proposed state legislation would change that.

Key findings from the analysis:

- **55.8%** of residential lots are single-family zoned (R1)
- **231,671** residential parcels would be legalized under a proposed 1,500 sqft minimum lot cap
- **73%** of existing multi-family parcels are non-conforming under current use codes
- **2,439** duplex/two-family parcels are currently non-conforming — missing middle housing that preemption would restore

**Zoning ordinance parser and knowledge graph** — Parses all 18 articles of Detroit's zoning ordinance (Chapter 50) from Word documents into structured data, then builds an RDF/OWL knowledge graph queryable via SPARQL. Designed to generalize to any US municipality.

**Census housing analysis** — Fetches American Community Survey data and maps housing burden metrics (30%+ income threshold) at the ZCTA and City Council district level.

**BZA minutes extraction** — Scrapes and OCRs Board of Zoning Appeals meeting minutes into structured case datasets (case number, petitioner, location, proposal, decision, votes).

## Repository Structure

```
src/strongtowns_detroit/           # Shared Python package
  parcels/                         # Parcel compliance & preemption analysis
  census/                          # ACS data fetching & aggregation
  bza/                             # BZA minutes scraping, renaming, OCR parsing
  geo/                             # Geography utilities (boundary, water, streets)
  mapping/                         # Choropleth map rendering
  zoning/                          # Ordinance parser + RDF knowledge graph
    models.py                      # Data models (UsePermission, DimensionalStandard, etc.)
    table_parser.py                # XML-level table expansion (merged cells)
    document.py                    # Section hierarchy parser
    use_tables.py                  # Type A: use permission matrices
    dimensional.py                 # Type B: dimensional standards
    definitions.py                 # Type C: definition lookups
    citations.py                   # Cross-reference extraction & citation graph
    ordinance.py                   # Orchestrator + JSON/CSV export
    ontology.py                    # MZO OWL/SKOS ontology (T-Box)
    rdf_builder.py                 # RDF knowledge graph builder (A-Box)
    kg_queries.py                  # SPARQL query tools for AI agents

pipelines/
  parcel-data/                     # Parcel zoning analysis pipeline
  housingDataAnalysis/             # Census & housing data pipeline
    street_simplification/         # OSMnx street network simplification
  zoning-parser/                   # Ordinance parsing CLI
  zoning/                          # BZA minutes extraction pipeline

tests/                             # 435 tests (393 unit + 42 integration)
resources/                         # Zoning ordinance .docx files (not in repo)
docs/                              # Internal documentation
```

## Setup

**Requirements:** Python 3.12+

```bash
# Clone the repo
git clone https://github.com/Strong-Towns-Detroit/data-analysis-scripts.git
cd data-analysis-scripts

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install pytest pytest-mock python-dotenv
pip install python-docx lxml rdflib        # zoning parser + knowledge graph
pip install pandas geopandas matplotlib    # parcel analysis
pip install sentence-transformers          # semantic use-code matching (optional)

# Census API (optional, for housing analysis pipeline)
cp .env.example .env
# Edit .env and add your Census API key from https://api.census.gov/data/key_signup.html
```

### Data Files

The large data files are not checked into git. To run the pipelines, you'll need:

| File | Size | Source | Used By |
|------|------|--------|---------|
| `resources/*.docx` | 111 MB | [Detroit Zoning Ordinance on Municode](https://library.municode.com/mi/detroit/codes/code_of_ordinances?nodeId=PTIVZOAM) | Ordinance parser |
| `pipelines/parcel-data/Parcels.geojson` | 939 MB | [Detroit Open Data](https://data.detroitmi.gov/) | Parcel analysis |
| `pipelines/parcel-data/parcel-data.csv` | 172 MB | Detroit Open Data | Parcel analysis |
| `pipelines/parcel-data/building-permits.csv` | 16 MB | Detroit Open Data | Parcel analysis |

## Running the Pipelines

### Parcel Zoning Analysis

Run in order from `pipelines/parcel-data/`:

```bash
python extract_tables_from_docx.py      # .docx → merged_tables.csv
python build_use_code.py                # CSV → detroit_zoning.json
python merge_and_calculate.py           # Merge parcels + zoning → compliance metrics
python analyze_preemption.py            # Generate preemption impact report
python map_parcels.py                   # Render choropleth maps
```

### Zoning Ordinance Parser

```bash
cd pipelines/zoning-parser
python parse_ordinance.py               # Reads resources/*.docx → JSON + CSV
```

Outputs: `use_permissions.json`, `dimensional_standards.json`, `definitions.json`, `sections.json`

Parsed data stats from Detroit's ordinance:
- **7,685** use permissions (245 land uses across 29 zoning districts)
- **1,655** dimensional standard records
- **468** defined terms
- **2,360** cross-reference nodes, **4,618** citation edges

### Knowledge Graph

Build an RDF knowledge graph from the parsed ordinance:

```python
from pathlib import Path
from strongtowns_detroit.zoning.ordinance import parse_ordinance
from strongtowns_detroit.zoning.citations import build_citation_graph
from strongtowns_detroit.zoning.rdf_builder import build_rdf_graph, export_graph

data = parse_ordinance(Path("resources"))
graph = build_citation_graph(data["sections"], resolve_hierarchical=False)
rdf = build_rdf_graph(
    citation_graph=graph,
    sections=data["sections"],
    use_permissions=data["use_permissions"],
    dimensional_standards=data["dimensional_standards"],
    definitions=data["definitions"],
    municipality="detroit",
    chapter="50",
)
export_graph(rdf, Path("output/detroit_zoning.ttl"))
```

Query it with the built-in SPARQL tools:

```python
from strongtowns_detroit.zoning.kg_queries import *

# What uses are allowed by-right in R1?
query_use_permissions(rdf, district="R1", permission="by_right")

# What's the minimum lot size in R2?
query_dimensional_standards(rdf, district="R2", standard_type="lot area")

# What does "nonconforming use" mean in the ordinance?
query_definition(rdf, "nonconforming")

# What sections cite 50-12-127, and why?
query_cross_references(rdf, "50-12-127", direction="incoming")

# BFS: what's connected to single-family use regulations?
bfs_traverse(rdf, "50-12-101", max_depth=2)
```

The ontology uses the `mzo:` namespace (`http://municipalzoning.org/ontology#`) and is designed to work for any US municipality, not just Detroit.

### Census Housing Analysis

```bash
cd pipelines/housingDataAnalysis
source .venv/bin/activate
pip install -r requirements.txt
python src/scripts/run_detroit_analysis.py
```

### BZA Minutes Extraction

```bash
cd pipelines/zoning
python scrape_bza_minutes.py
python rename_bza_minutes.py
python create_bza_dataset_from_minutes.py --engine tesseract
```

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short
```

435 tests (393 unit + 42 integration), ~10 seconds. Integration tests parse real `.docx` files and are skipped if `resources/*.docx` are not present.

## Key Technical Details

- **Parcel join**: GeoJSON uses `parcel_number`, CSV uses `parcel_id` — the pipeline renames to align
- **Area fields**: `shape_area` (geometric, ~1290) vs `total_square_footage` (legal, ~7400 mean) — the pipeline uses the legal field
- **Preemption thresholds**: Proposed min lot = 1,500 sqft, proposed min dwelling = 500 sqft
- **Residential zones**: R1, R2, R3, R4, R5, R6, SD1, SD2
- **Permission codes**: `R` = by-right, `C` = conditional, `C/R` = mixed
- **Zoning table parsing**: Uses XML-level parsing (ZIP → lxml → XPath) instead of python-docx to handle complex merged cells in dimensional standards tables
- **Knowledge graph**: Symbolic RDF/SPARQL, not embeddings — legal precision and source traceability matter more than fuzzy similarity

## License

This project analyzes publicly available municipal data and ordinances. The zoning ordinance text is published by the City of Detroit via Municode.
