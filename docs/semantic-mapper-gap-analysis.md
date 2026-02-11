# Semantic Mapper Gap Analysis

The `ZoningMapper` class in `src/strongtowns_detroit/parcels/semantic_mapper.py` captures
only one step of the full use-code-to-zoning-district pipeline. The remaining logic lives
unextracted in `scripts/parcel-data/explore-parcel-data.ipynb`.

---

## What `ZoningMapper` Does (Extracted)

The class handles **SBERT semantic similarity matching** — step 2 of a 4-step pipeline:

| Method | Purpose |
|---|---|
| `extract_specific_uses()` | Flatten `detroit_zoning.json` into `(category, use)` pairs |
| `compute_similarities()` | Encode both sides with `all-MiniLM-L6-v2`, compute dot-product similarity matrix |
| `get_top_matches()` | Bucket matches into high (>=0.75) / medium (>=0.60) / low confidence |
| `generate_mapping()` | Auto-accept high-confidence matches into a use→specific_use mapping |
| `export_results()` | Write matches to JSON for human review |
| `print_summary()` | Print match counts by confidence tier |

This produces `parcel_uses_to_zoning_uses_mapping.json` — a mapping from parcel use codes
to zoning-specific land uses. But it does **not** resolve those uses to zoning districts.

---

## What's Missing (Still in Notebook)

### 1. District Resolution — `getZoningDistrictsFromUses()`

Located in notebook cell `763bec43`. Given a use category and list of specific uses,
looks up which zoning districts permit that use in `detroit_zoning.json`:

```python
def getZoningDistrictsFromUses(use_category, specific_uses):
    zoning_districts = {"conditional": [], "by_right": [], "by_right_subject_to_conditions": []}

    if use_category == 'Residential':
        zoning_districts['by_right'] = residential_zones
    elif use_category == 'Commercial':
        zoning_districts['by_right'] = commercial_zones
    elif use_category == 'Industrial':
        zoning_districts['by_right'] = industrial_zones
    elif use_category == 'All':
        zoning_districts['by_right'] = all_zones
    else:
        for specific_use in specific_uses:
            zoning_districts = unionZoningMaps(zoning_districts, zoning_uses[use_category][specific_use])

    return zoning_districts
```

This handles two cases:
- **Broad categories** ("Residential", "Commercial", "Industrial", "All") → map to entire zone groups
- **Specific uses** → look up permissions per-district from `detroit_zoning.json`

### 2. Permission Map Merging — `unionZoningMaps()`

```python
def unionZoningMaps(map1, map2):
    return {
        key: list(set(map1.get(key, []) + map2.get(key, [])))
        for key in ["conditional", "by_right", "by_right_subject_to_conditions"]
    }
```

When a parcel use code maps to multiple specific uses (e.g., "STORE-RETAIL" maps to
both "sales-oriented" and "occupant-oriented" retail categories), their permitted
districts are unioned together.

### 3. Extended Mapping Builder

The loop that combines inputs to produce the **final output**:

```python
for parcel_use_code, mappings in mapped_use_codes.items():
    extended_mapped_use_codes[parcel_use_code] = {
        'parcel_uses': mappings,
        'zoning_districts': EMPTY_ZONING_DISTRICTS_TEMPLATE.copy()
    }
    for mapping in mappings:
        specific_use_zoning_districts = getZoningDistrictsFromUses(
            mapping['use_category'], mapping['specific_use']
        )
        extended_mapped_use_codes[parcel_use_code]['zoning_districts'] = unionZoningMaps(
            extended_mapped_use_codes[parcel_use_code]['zoning_districts'],
            specific_use_zoning_districts
        )
```

**Input:** `parcel_use_codes_to_zoning_use_codes_manual_mapping.json`
**Output:** `parcel_use_codes_to_zoning_districts_mapping.json`

### 4. Conformance Classification

Notebook cells `a7c6cb43` through `4e8d85e7`. Applies the district mapping to every
parcel row:

```python
df['is_zoned_by_right'] = df.apply(
    lambda row: row['zoning_district'] in row['by_right_zoning_districts'], axis=1)
df['is_zoned_conditionally'] = df.apply(
    lambda row: row['zoning_district'] in row['conditional_zoning_districts'], axis=1)
df['is_zoned_special_approval'] = df.apply(
    lambda row: row['zoning_district'] in row['special_approval_zoning_districts'], axis=1)
df['is_non_conforming'] = ~(
    df['is_zoned_by_right'] | df['is_zoned_conditionally'] | df['is_zoned_special_approval'])
```

---

## The Wrapper Script Is Non-Functional

`scripts/parcel-data/zoning_use_mapper.py` references `zoning_data.json` and
`use_list.json` — neither file exists in the repository. The `main()` function is a
generic template that doesn't match the actual data flow.

The real entry points for this pipeline are:
1. The notebook (exploratory, produces the manual mapping interactively)
2. `analyze_preemption.py` (consumes the final `parcel_use_codes_to_zoning_districts_mapping.json`)

---

## Data Flow (Current vs Complete)

```
                       CURRENT PACKAGE COVERAGE
                       ========================

detroit_zoning.json ──────────────────────────────────────────────┐
                                                                  │
use_codes.json ──► ZoningMapper ──► parcel_uses_to_zoning_uses    │
(from notebook)     (SBERT)          _mapping.json                │
                                         │                        │
                                         ▼                        │
                                    Human review &                │
                                    manual curation               │
                                         │                        │
                                         ▼                        │
                                parcel_use_codes_to_zoning        │
                                _use_codes_manual_mapping.json    │
                                         │                        │
                       ┌─────────────────┘                        │
                       │     NOT IN PACKAGE                       │
                       │     ==============                       │
                       ▼                                          ▼
                  District Resolver ◄─────────────────────────────┘
                  (getZoningDistrictsFromUses +
                   unionZoningMaps)
                       │
                       ▼
                  parcel_use_codes_to_zoning
                  _districts_mapping.json
                       │
                       ▼
                  Conformance Classifier
                  (is_zoned_by_right, is_non_conforming, etc.)
                       │
                       ▼
                  analyze_preemption.py
```

---

## Recommended Extraction

Two functions to add to `src/strongtowns_detroit/parcels/semantic_mapper.py`
(or a new `district_resolver.py` module):

| Function | Input | Output |
|---|---|---|
| `resolve_districts(manual_mapping, zoning_data, zone_groups)` | manual mapping JSON + zoning DB + zone group lists | extended mapping with `zoning_districts` per use code |
| `classify_conformance(df, district_mapping, district_col)` | DataFrame + district mapping + column name | DataFrame with `is_zoned_by_right`, `is_non_conforming`, etc. |

Zone groups (`residential_zones`, `commercial_zones`, etc.) should come from
`constants.py`, extending the existing `RESIDENTIAL_ZONES` list with commercial,
industrial, and special zone lists.
