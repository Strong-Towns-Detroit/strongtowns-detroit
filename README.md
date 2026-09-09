# Strong Towns Detroit

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

Reusable code and data tooling live in sibling repositories:

- `strongtowns-graphics` — publishing-neutral rendering library
- `strongtowns-data` — data contracts, pipelines, manifests, and review tooling
- `strongtowns-cli` — accessible command interface over the domain packages
- `zoning-rule-engine` — zoning-language compiler and rule engine

This repository contains Detroit-specific analysis, exhibits, and the Land
Forum site.

## Repository Structure

```
src/strongtowns_detroit/           # Detroit-only Python helpers and design tokens

pipelines/
  assessment-history/              # Detroit assessment-history analysis
  legislative-district/            # Detroit legislative-district products
  zoning-parser/                   # Ordinance parsing CLI

projects/                          # Detroit analyses and exhibit definitions
sites/land-forum/                  # Public Land Forum web application
tests/                             # Consumer-boundary and regression tests
strongtowns-data.lock.json         # Content-addressed input selection
```

## Setup

**Requirements:** Python 3.12+

```bash
# Clone the four repositories beside one another
git clone https://github.com/Strong-Towns-Detroit/strongtowns-detroit.git
git clone https://github.com/Strong-Towns-Detroit/strongtowns-data.git
git clone https://github.com/Strong-Towns-Detroit/strongtowns-graphics.git
git clone https://github.com/Strong-Towns-Detroit/strongtowns-cli.git
git clone https://github.com/Strong-Towns-Detroit/zoning-rule-engine.git
cd strongtowns-detroit

uv sync --locked --extra dev
uv run pytest -q
uv pip install -e ../strongtowns-cli
uv run --no-sync strongtowns doctor --require graphics --require data
```

The CLI requires Python 3.12+ and installs both the data and graphics SDKs
automatically; no extras or separate zoning executable are needed. The commands
above install it into this checkout's environment. For a standalone CLI install
in your Python environment:

```bash
python -m pip install 'strongtowns-cli @ git+https://github.com/Strong-Towns-Detroit/strongtowns-cli.git@main'
```

### Data Files

Large and third-party evidence files are not checked into this repository.
Materialize the content-addressed inputs through `strongtowns-data`. Adjacent
clones are detected automatically; set `STRONGTOWNS_DATA_REPOSITORY` when using
a different checkout layout.

## Running the Pipelines

### Publishing graphics

The repository includes a reusable graphics library and canonical definitions
that fan out to Instagram posts, Instagram Stories, and conference graphics.

- Start with the [plain-language graphics guide](projects/graphics/USING_GRAPHICS.md)
  if you want to produce or revise graphics without working directly in code.
- Open the [Instagram example notebooks](projects/graphics/notebooks/README.md)
  to generate and adapt our existing graphics directly with the Python SDKs.
- Read the [graphics contributor guide](projects/graphics/CONTRIBUTING.md) before
  changing library APIs or adding reusable rendering behavior.
- AI agents should follow [AGENTS.md](AGENTS.md), establish publishing or
  developer mode, and preserve the boundary between graphic definitions and
  the shared library.

```bash
strongtowns assets list --project .
strongtowns assets check --project .
strongtowns assets build --project . --target instagram
```

`assets check` is a read-only preflight. `assets build` first verifies every
content-addressed input in `strongtowns-data.lock.json`, then delegates output
generation to the graphics SDK. Select one or more definitions by placing their
names after `check` or `build`.

### Reproducible data and local SQL

```bash
strongtowns data status --repository ../strongtowns-data
strongtowns data materialize strongtowns-data.lock.json .data \
  --repository ../strongtowns-data
```

The DuckDB catalog is a read-only, downloadable mirror of promoted data. No
hosted database, R2 upload, or paid query service is required.

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
from strongtowns_data.zoning.ordinance import parse_ordinance
from strongtowns_data.zoning.citations import build_citation_graph
from strongtowns_data.zoning.rdf_builder import build_rdf_graph, export_graph

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
from strongtowns_data.zoning.kg_queries import *

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

## Tests

```bash
uv sync --locked --extra dev
uv run pytest -q
cd sites/land-forum
npm ci
npm test
npm run tokens:check
npm run build
```

The default suite covers Detroit consumer boundaries, exhibit logic, and the
Land Forum. Library, data-engine, and zoning-compiler suites run in their own
repositories. See [AGENTS.md](AGENTS.md) for the locked environment and
clean-checkout workflow.

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
