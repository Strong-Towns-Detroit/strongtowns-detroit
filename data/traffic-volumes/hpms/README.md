# FHWA Highway Performance Monitoring System (HPMS) Data — Michigan / Detroit

## Overview

The Highway Performance Monitoring System (HPMS) is the most comprehensive federal
dataset for road overcapacity analysis. It is submitted annually by each state DOT to
the Federal Highway Administration (FHWA) and contains segment-level data including
volume-to-capacity (V/C) ratios, AADT, lane counts, functional classification, and
capacity estimates.

## Why HPMS Matters for Overcapacity Analysis

HPMS is the **only** publicly available dataset that explicitly includes:
- **Volume-to-Service-Flow Ratios (V/SF or V/C ratios)** — the direct measure of
  whether a road is overbuilt relative to its traffic
- **AADT** — Annual Average Daily Traffic counts
- **Lane counts** (through lanes, turn lanes)
- **Functional classification** (Interstate, Principal Arterial, Minor Arterial,
  Collector, Local)
- **Capacity estimates** derived from Highway Capacity Manual methods
- **Road geometry** (lane width, shoulder width, median type)
- **Pavement condition** (IRI - International Roughness Index)
- **Speed limits**
- **Truck percentages**

A V/C ratio below 0.5 generally indicates significant overcapacity; below 0.3
indicates the road could likely be downsized.

---

## Data Sources and Access Methods

### 1. FHWA HPMS Public Data (Primary Source)

**URL:** https://www.fhwa.dot.gov/policyinformation/hpms.cfm

This is the main FHWA HPMS landing page. From here you can access:

- **HPMS Field Manual** — documents all data fields submitted by states
- **HPMS Submittal Tables** — summary statistics by state
- **Links to geospatial data viewers and downloads**

### 2. USDOT Geospatial Data Portal (Recommended for GIS Data)

**URL:** https://data-usdot.opendata.arcgis.com/

Search for "HPMS" on this ArcGIS Open Data portal. Datasets are typically available as:
- Shapefiles (.shp)
- GeoJSON
- CSV
- File Geodatabase (.gdb)
- KML

Look for datasets named like:
- `Highway Performance Monitoring System (HPMS) - Full Extent`
- `HPMS_Full_MI` or `HPMS_Full_Michigan`

### 3. Bureau of Transportation Statistics (BTS) / NTAD

**URL:** https://geodata.bts.gov/

The National Transportation Atlas Database (NTAD) includes HPMS data layers.

- Search for "HPMS" at https://geodata.bts.gov/search?q=HPMS
- Data is available as GIS layers, typically in shapefile or geodatabase format
- May lag behind the primary FHWA source by a year

### 4. geo.dot.gov ArcGIS Server (Direct REST API)

**URL:** https://geo.dot.gov/server/rest/services/Hosted/

FHWA publishes HPMS data as ArcGIS Feature Services. You can query these
programmatically:

```
# Base endpoint pattern:
https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_<State>_<Year>/FeatureServer

# Example for Michigan 2022:
https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_Michigan_2022/FeatureServer

# Query for Detroit area (approximate bounding box):
https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_Michigan_2022/FeatureServer/0/query?where=1%3D1&geometry=-83.5,42.2,-82.8,42.5&geometryType=esriGeometryEnvelope&spatialRel=esriSpatialRelIntersects&outFields=*&f=geojson&resultRecordCount=5000
```

### 5. HPMS Geospatial Data Viewer

**URL:** https://hpms.fhwa.dot.gov/

Interactive web map viewer for HPMS data. You can:
- Browse road segments visually
- Filter by state, county, functional class
- View attributes for individual segments
- Limited export capability (use the REST API for bulk downloads)

---

## Key HPMS Fields for Overcapacity Analysis

| Field Name | Description | Use in Analysis |
|---|---|---|
| `AADT` | Annual Average Daily Traffic | Actual traffic volume |
| `AADT_COMBINATION` | AADT for combination trucks | Truck traffic component |
| `AADT_SINGLE_UNIT` | AADT for single-unit trucks | Truck traffic component |
| `THROUGH_LANES` | Number of through lanes | Capacity indicator |
| `LANE_WIDTH` | Width of travel lanes (feet) | Overbuilding indicator |
| `SHOULDER_WIDTH_R` | Right shoulder width | Overbuilding indicator |
| `SHOULDER_WIDTH_L` | Left shoulder width | Overbuilding indicator |
| `MEDIAN_TYPE` | Type of median | Road design indicator |
| `MEDIAN_WIDTH` | Width of median (feet) | Overbuilding indicator |
| `SPEED_LIMIT` | Posted speed limit | Design speed indicator |
| `F_SYSTEM` | Functional system/classification | Road hierarchy |
| `FACILITY_TYPE` | One-way vs two-way | Capacity calculation |
| `K_FACTOR` | Proportion of AADT in peak hour | Peak period analysis |
| `DIR_FACTOR` | Directional distribution factor | Peak period analysis |
| `FUTURE_AADT` | Projected future AADT | Growth expectations |
| `IRI` | International Roughness Index | Pavement condition |
| `PEAK_LANES` | Number of peak-period lanes | Peak capacity |
| `COUNTY_CODE` | FIPS county code | Geographic filtering |
| `URBAN_CODE` | Census urban area code | Urban/rural classification |
| `NHS` | National Highway System designation | Federal significance |
| `STRAHNET` | Strategic highway network | Military significance |
| `SECTION_LENGTH` | Length of road segment (miles) | Lane-mile calculations |

### Volume-to-Capacity (V/C) Ratio

The V/C ratio may be included directly in HPMS data or can be computed:

```
V/C = AADT / (Through_Lanes x Per_Lane_Capacity x K_Factor_Adjustment)
```

Where per-lane capacity varies by functional class:
- Interstate: ~2,200 vehicles/lane/hour
- Principal Arterial: ~1,800 vehicles/lane/hour
- Minor Arterial: ~1,600 vehicles/lane/hour
- Collector: ~1,400 vehicles/lane/hour
- Local: ~1,200 vehicles/lane/hour

Some HPMS submissions include a `PEAK_PARKING` or capacity-related field directly.
The specific V/SF ratio field in HPMS is typically computed during FHWA processing.

---

## Filtering for Detroit

To extract Detroit-area data from the statewide Michigan HPMS dataset:

### By FIPS County Code
- **Wayne County:** FIPS 26163 (includes Detroit, Dearborn, Livonia)
- **Oakland County:** FIPS 26125 (includes Southfield, Troy, Pontiac)
- **Macomb County:** FIPS 26099 (includes Warren, Sterling Heights)

For Detroit city proper, filter to Wayne County (26163) and then clip to
Detroit city boundaries.

### By Urban Area Code
- **Detroit-Warren-Dearborn Urbanized Area:** Census Urban Area Code 26420
  (or the UA code used in your HPMS vintage)

### By Geography (Bounding Box)
Detroit approximate bounding box:
- West: -83.29
- East: -82.91
- South: 42.26
- North: 42.45

Metro Detroit approximate bounding box:
- West: -83.60
- East: -82.70
- South: 42.10
- North: 42.75

---

## Download Steps

### Method A: ArcGIS REST API (Recommended for Automation)

```bash
# 1. Check what years/layers are available
curl "https://geo.dot.gov/server/rest/services/Hosted?f=json" | \
  python3 -c "import sys,json; [print(s['name']) for s in json.load(sys.stdin)['services'] if 'HPMS' in s['name'] and 'Michigan' in s['name']]"

# 2. Query metadata for the layer
curl "https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_Michigan_2022/FeatureServer/0?f=json"

# 3. Download Detroit-area data as GeoJSON (paginated, 5000 records at a time)
# Note: ArcGIS Feature Services limit results per request (often 1000-5000)
# You may need to paginate using resultOffset

LAYER_URL="https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_Michigan_2022/FeatureServer/0"

# First page
curl "${LAYER_URL}/query?where=COUNTY_CODE%3D163&outFields=*&f=geojson&resultRecordCount=2000&resultOffset=0" \
  -o hpms_detroit_page1.geojson

# Second page (if needed)
curl "${LAYER_URL}/query?where=COUNTY_CODE%3D163&outFields=*&f=geojson&resultRecordCount=2000&resultOffset=2000" \
  -o hpms_detroit_page2.geojson

# Or use a bounding box query for the full metro area
curl "${LAYER_URL}/query?where=1%3D1&geometry=-83.6,42.1,-82.7,42.75&geometryType=esriGeometryEnvelope&spatialRel=esriSpatialRelIntersects&outFields=*&f=geojson&resultRecordCount=5000" \
  -o hpms_metro_detroit.geojson
```

### Method B: USDOT Open Data Portal (Manual Download)

1. Go to https://data-usdot.opendata.arcgis.com/
2. Search for "HPMS"
3. Select the Michigan or national dataset for the most recent year
4. Click "Download" and choose your format (Shapefile, GeoJSON, CSV, etc.)
5. For national datasets, filter to `STATE_CODE = 26` (Michigan FIPS)

### Method C: BTS / NTAD Download

1. Go to https://geodata.bts.gov/
2. Search for "HPMS" or browse Transportation > Highway
3. Download the national HPMS layer
4. Filter in GIS software: `STATE_CODE = 26` for Michigan
5. Further filter by county codes for Detroit metro area

### Method D: Python Script (Automated Download)

```python
#!/usr/bin/env python3
"""
Download HPMS data for Detroit/Wayne County from FHWA ArcGIS REST API.
"""
import requests
import json
import os

# Configuration
OUTPUT_DIR = os.path.expanduser("~/strongtowns-detroit/data/traffic-volumes/hpms")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ArcGIS Feature Service URL — update year as needed
# Try these URL patterns if one doesn't work:
BASE_URLS = [
    "https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_Michigan_2022/FeatureServer/0",
    "https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_MI_2022/FeatureServer/0",
    "https://geo.dot.gov/server/rest/services/Hosted/Highway_Performance_Monitoring_System_Full_Michigan/FeatureServer/0",
]

# Detroit metro bounding box
BBOX = "-83.6,42.1,-82.7,42.75"
# Or use county filter: COUNTY_CODE = 163 (Wayne County, where FIPS = 26163)

def download_hpms(base_url, output_file, use_bbox=True):
    """Download HPMS data with pagination."""
    all_features = []
    offset = 0
    page_size = 2000

    while True:
        params = {
            "outFields": "*",
            "f": "geojson",
            "resultRecordCount": page_size,
            "resultOffset": offset,
        }

        if use_bbox:
            params.update({
                "where": "1=1",
                "geometry": BBOX,
                "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects",
            })
        else:
            # Wayne County filter
            params["where"] = "COUNTY_CODE=163"

        url = f"{base_url}/query"
        print(f"Fetching offset {offset}...")
        resp = requests.get(url, params=params, timeout=60)

        if resp.status_code != 200:
            print(f"Error: HTTP {resp.status_code}")
            print(resp.text[:500])
            return False

        data = resp.json()
        features = data.get("features", [])

        if not features:
            break

        all_features.extend(features)
        offset += page_size
        print(f"  Got {len(features)} features (total: {len(all_features)})")

        if len(features) < page_size:
            break

    if all_features:
        geojson = {
            "type": "FeatureCollection",
            "features": all_features,
        }
        output_path = os.path.join(OUTPUT_DIR, output_file)
        with open(output_path, "w") as f:
            json.dump(geojson, f)
        print(f"Saved {len(all_features)} features to {output_path}")
        return True
    return False


if __name__ == "__main__":
    for url in BASE_URLS:
        print(f"\nTrying: {url}")
        # Check if service exists
        try:
            resp = requests.get(f"{url}?f=json", timeout=15)
            if resp.status_code == 200 and "error" not in resp.json():
                print("Service found! Downloading...")
                success = download_hpms(url, "hpms_metro_detroit.geojson", use_bbox=True)
                if success:
                    print("Download complete!")
                    break
            else:
                print("Service not found, trying next...")
        except Exception as e:
            print(f"Error: {e}")
            continue
    else:
        print("\nCould not find a working HPMS service URL.")
        print("Try browsing https://geo.dot.gov/server/rest/services/Hosted?f=html")
        print("and search for 'HPMS' to find the current service name.")
```

---

## Alternative Approach: HPMS Public Release Tables

If geospatial data is difficult to access, FHWA also publishes HPMS summary tables:

**URL:** https://www.fhwa.dot.gov/policyinformation/statistics.cfm

These "Highway Statistics" tables include:
- **Table HM-72** — Lane-miles by functional system (state-level)
- **Table HM-71** — Public road mileage by functional system
- **Table VM-2** — Vehicle-miles traveled by functional system
- These allow computation of VMT per lane-mile (a proxy for utilization)

While less granular than segment-level HPMS data, these can provide
state-level overcapacity indicators.

---

## Data Notes and Caveats

1. **Data Vintage:** HPMS data is typically 1-2 years behind the current year.
   The most recent available data as of early 2026 is likely from 2022 or 2023.

2. **Sample vs. Full Extent:** HPMS data comes in two forms:
   - **Full Extent** — every road on the state's public road inventory
   - **Sample Sections** — detailed data on a statistical sample of sections
   V/C ratios and detailed capacity data are more commonly available on
   sample sections. Full extent data has AADT and lane counts for major roads.

3. **State Variation:** Each state submits data with varying completeness.
   Michigan (MDOT) generally has good HPMS data quality.

4. **Coordinate System:** HPMS geospatial data typically uses WGS 84 (EPSG:4326)
   or NAD 83 (EPSG:4269) for national datasets.

5. **File Sizes:** The full Michigan HPMS shapefile can be 100+ MB. The
   Detroit metro area subset will be much smaller (10-30 MB).

6. **Functional Classification Codes (F_SYSTEM):**
   - 1 = Interstate
   - 2 = Principal Arterial - Other Freeways and Expressways
   - 3 = Principal Arterial - Other
   - 4 = Minor Arterial
   - 5 = Major Collector
   - 6 = Minor Collector
   - 7 = Local

---

## Recommended Analysis Workflow

1. Download HPMS data for Michigan (or Wayne/Oakland/Macomb counties)
2. Filter to Detroit city boundaries using a spatial clip
3. For each road segment, compute or extract V/C ratio
4. Classify segments:
   - V/C < 0.3 — Severely overcapacity (strong candidate for road diet)
   - V/C 0.3-0.5 — Overcapacity (candidate for lane reduction)
   - V/C 0.5-0.7 — Moderately utilized
   - V/C 0.7-0.85 — Well utilized
   - V/C 0.85-1.0 — Near capacity
   - V/C > 1.0 — Over capacity / congested
5. Calculate total excess lane-miles: sum of (actual lanes - needed lanes) x segment length
6. Map results to show overcapacity corridors

---

## Contact / Data Requests

If public downloads are insufficient, HPMS data can be requested from:

- **FHWA HPMS Team:** hpms@dot.gov
- **Michigan DOT (MDOT) Data & Analytics:** https://www.michigan.gov/mdot
  - MDOT's Transportation Data Management System (TDMS)
  - MDOT Open Data Portal: https://gis-michigan.opendata.arcgis.com/
    (search for traffic volume or HPMS)

---

*Last updated: 2026-02-21*
*Created for: Strong Towns Detroit — Road Overcapacity Analysis*
