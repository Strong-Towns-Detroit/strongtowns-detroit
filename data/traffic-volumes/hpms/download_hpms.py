#!/usr/bin/env python3
"""
Download HPMS data for Detroit/Metro Detroit from FHWA ArcGIS REST API.

Usage:
    python3 download_hpms.py

This script attempts multiple known URL patterns for the FHWA HPMS
ArcGIS Feature Service. It downloads road segments within the Detroit
metro area bounding box and saves them as GeoJSON.

If automated download fails, the script prints manual instructions.
"""
import requests
import json
import os
import sys
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_DIR = os.path.expanduser("~/strongtowns-detroit/data/traffic-volumes/hpms")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Detroit metro bounding box (generous)
METRO_DETROIT_BBOX = "-83.60,42.10,-82.70,42.75"

# Detroit city proper bounding box
DETROIT_CITY_BBOX = "-83.29,42.26,-82.91,42.45"

# Wayne County FIPS (without state prefix)
WAYNE_COUNTY_CODE = 163
OAKLAND_COUNTY_CODE = 125
MACOMB_COUNTY_CODE = 99

# Michigan state FIPS
MICHIGAN_STATE_CODE = 26

# Years to try (most recent first)
YEARS = [2023, 2022, 2021, 2020]

# URL patterns to try — FHWA has changed these over the years
URL_PATTERNS = [
    "https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_Michigan_{year}/FeatureServer/0",
    "https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_MI_{year}/FeatureServer/0",
    "https://geo.dot.gov/server/rest/services/Hosted/HPMS_{year}_Michigan/FeatureServer/0",
    "https://geo.dot.gov/server/rest/services/Hosted/HPMS_{year}_Full_Michigan/FeatureServer/0",
    # National dataset (slower, but may be the only option)
    "https://geo.dot.gov/server/rest/services/Hosted/HPMS_Full_{year}/FeatureServer/0",
    "https://geo.dot.gov/server/rest/services/Hosted/HPMS_{year}/FeatureServer/0",
]

PAGE_SIZE = 2000

# ── Helper Functions ──────────────────────────────────────────────────────────

def check_service(url):
    """Check if an ArcGIS Feature Service exists and is accessible."""
    try:
        resp = requests.get(f"{url}?f=json", timeout=15)
        if resp.status_code != 200:
            return False
        data = resp.json()
        if "error" in data:
            return False
        # Check for expected fields
        if "fields" in data or "name" in data:
            return True
        return False
    except Exception:
        return False


def get_service_info(url):
    """Get metadata about the feature service layer."""
    try:
        resp = requests.get(f"{url}?f=json", timeout=15)
        data = resp.json()
        fields = [f["name"] for f in data.get("fields", [])]
        max_count = data.get("maxRecordCount", 1000)
        name = data.get("name", "Unknown")
        count_resp = requests.get(
            f"{url}/query",
            params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
            timeout=15,
        )
        total_count = count_resp.json().get("count", "unknown")
        return {
            "name": name,
            "fields": fields,
            "max_record_count": max_count,
            "total_features": total_count,
        }
    except Exception as e:
        return {"error": str(e)}


def download_by_bbox(base_url, bbox, output_file, where_clause="1=1"):
    """Download features within a bounding box with pagination."""
    all_features = []
    offset = 0

    while True:
        params = {
            "where": where_clause,
            "geometry": bbox,
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
            "resultRecordCount": PAGE_SIZE,
            "resultOffset": offset,
        }

        url = f"{base_url}/query"
        print(f"  Fetching offset {offset}...", end="", flush=True)

        try:
            resp = requests.get(url, params=params, timeout=120)
        except requests.exceptions.Timeout:
            print(" TIMEOUT")
            break
        except Exception as e:
            print(f" ERROR: {e}")
            break

        if resp.status_code != 200:
            print(f" HTTP {resp.status_code}")
            break

        try:
            data = resp.json()
        except json.JSONDecodeError:
            print(" INVALID JSON")
            break

        if "error" in data:
            print(f" API ERROR: {data['error'].get('message', 'unknown')}")
            break

        features = data.get("features", [])
        if not features:
            print(" (no more features)")
            break

        all_features.extend(features)
        print(f" got {len(features)} (total: {len(all_features)})")

        offset += PAGE_SIZE
        if len(features) < PAGE_SIZE:
            break

    if all_features:
        geojson = {
            "type": "FeatureCollection",
            "features": all_features,
            "metadata": {
                "source": base_url,
                "download_date": datetime.now().isoformat(),
                "bbox": bbox,
                "feature_count": len(all_features),
            },
        }
        output_path = os.path.join(OUTPUT_DIR, output_file)
        with open(output_path, "w") as f:
            json.dump(geojson, f)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Saved {len(all_features)} features to {output_path} ({size_mb:.1f} MB)")
        return True

    return False


def download_by_county(base_url, county_code, state_code, output_file):
    """Download features filtered by county code."""
    # Try different possible field names for county code
    where_clauses = [
        f"COUNTY_CODE={county_code}",
        f"COUNTY_CODE='{county_code}'",
        f"COUNTY_FIPS={county_code}",
        f"CNTY_CODE={county_code}",
    ]

    if state_code:
        where_clauses = [
            f"STATE_CODE={state_code} AND COUNTY_CODE={county_code}",
            f"State_Code={state_code} AND County_Code={county_code}",
        ] + where_clauses

    for where in where_clauses:
        print(f"  Trying filter: {where}")
        all_features = []
        offset = 0

        while True:
            params = {
                "where": where,
                "outFields": "*",
                "f": "geojson",
                "resultRecordCount": PAGE_SIZE,
                "resultOffset": offset,
            }

            try:
                resp = requests.get(f"{base_url}/query", params=params, timeout=120)
                data = resp.json()

                if "error" in data:
                    break

                features = data.get("features", [])
                if not features:
                    if offset == 0:
                        break  # Try next where clause
                    break  # No more pages

                all_features.extend(features)
                print(f"    offset {offset}: got {len(features)} (total: {len(all_features)})")
                offset += PAGE_SIZE

                if len(features) < PAGE_SIZE:
                    break

            except Exception:
                break

        if all_features:
            geojson = {
                "type": "FeatureCollection",
                "features": all_features,
                "metadata": {
                    "source": base_url,
                    "download_date": datetime.now().isoformat(),
                    "filter": where,
                    "feature_count": len(all_features),
                },
            }
            output_path = os.path.join(OUTPUT_DIR, output_file)
            with open(output_path, "w") as f:
                json.dump(geojson, f)
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"  Saved {len(all_features)} features to {output_path} ({size_mb:.1f} MB)")
            return True

    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("HPMS Data Downloader for Detroit / Metro Detroit")
    print("=" * 70)
    print()

    # Step 1: Find a working service URL
    working_url = None
    working_year = None

    print("Step 1: Searching for available HPMS Feature Services...")
    print()

    for year in YEARS:
        for pattern in URL_PATTERNS:
            url = pattern.format(year=year)
            print(f"  Checking: {url}")
            if check_service(url):
                print(f"  >>> FOUND! ({year})")
                working_url = url
                working_year = year
                break
        if working_url:
            break

    if not working_url:
        print()
        print("=" * 70)
        print("Could not find a working HPMS Feature Service URL.")
        print()
        print("MANUAL STEPS:")
        print()
        print("1. Browse available services at:")
        print("   https://geo.dot.gov/server/rest/services/Hosted?f=html")
        print("   Search (Ctrl+F) for 'HPMS' to find current service names.")
        print()
        print("2. Or download from USDOT Open Data Portal:")
        print("   https://data-usdot.opendata.arcgis.com/")
        print("   Search for 'HPMS' and download Michigan data.")
        print()
        print("3. Or try the BTS portal:")
        print("   https://geodata.bts.gov/search?q=HPMS")
        print()
        print("4. Or check MDOT's open data:")
        print("   https://gis-michigan.opendata.arcgis.com/")
        print("   Search for 'traffic' or 'HPMS'.")
        print()
        print("After downloading, place files in:")
        print(f"   {OUTPUT_DIR}")
        sys.exit(1)

    # Step 2: Get service info
    print()
    print(f"Step 2: Getting service metadata for {working_year}...")
    info = get_service_info(working_url)
    print(f"  Service name: {info.get('name', 'N/A')}")
    print(f"  Total features: {info.get('total_features', 'N/A')}")
    print(f"  Max records per query: {info.get('max_record_count', 'N/A')}")

    # Print relevant fields
    fields = info.get("fields", [])
    capacity_fields = [
        f for f in fields
        if any(
            kw in f.upper()
            for kw in [
                "AADT", "LANE", "CAPACITY", "V_C", "VOC", "VOLUME",
                "F_SYSTEM", "FUNC", "SPEED", "SHOULDER", "MEDIAN",
                "K_FACTOR", "DIR_FACTOR", "COUNTY", "URBAN", "SECTION",
            ]
        )
    ]
    if capacity_fields:
        print(f"  Key fields found: {', '.join(capacity_fields[:20])}")

    # Step 3: Download metro Detroit data by bounding box
    print()
    print("Step 3: Downloading metro Detroit data (bounding box method)...")
    success = download_by_bbox(
        working_url,
        METRO_DETROIT_BBOX,
        f"hpms_metro_detroit_{working_year}.geojson",
    )

    if not success:
        print("  Bounding box method failed. Trying county code method...")
        # Try Wayne County
        success = download_by_county(
            working_url,
            WAYNE_COUNTY_CODE,
            MICHIGAN_STATE_CODE,
            f"hpms_wayne_county_{working_year}.geojson",
        )

    # Step 4: Download Detroit city proper (smaller bbox)
    if success:
        print()
        print("Step 4: Downloading Detroit city proper (tighter bounding box)...")
        download_by_bbox(
            working_url,
            DETROIT_CITY_BBOX,
            f"hpms_detroit_city_{working_year}.geojson",
        )

    # Step 5: Also try tri-county (Wayne, Oakland, Macomb)
    if success:
        print()
        print("Step 5: Downloading Oakland and Macomb counties...")
        for county, code in [("oakland", OAKLAND_COUNTY_CODE), ("macomb", MACOMB_COUNTY_CODE)]:
            download_by_county(
                working_url,
                code,
                MICHIGAN_STATE_CODE,
                f"hpms_{county}_county_{working_year}.geojson",
            )

    print()
    print("=" * 70)
    if success:
        print("Download complete! Files saved to:")
        print(f"  {OUTPUT_DIR}")
        print()
        print("Next steps:")
        print("  1. Open in QGIS or load with geopandas to inspect")
        print("  2. Check for AADT, THROUGH_LANES, F_SYSTEM fields")
        print("  3. Compute V/C ratios if not already present")
        print("  4. Clip to Detroit city boundaries for city-level analysis")
    else:
        print("Automated download was not successful.")
        print("See manual steps printed above.")
    print("=" * 70)


if __name__ == "__main__":
    main()
