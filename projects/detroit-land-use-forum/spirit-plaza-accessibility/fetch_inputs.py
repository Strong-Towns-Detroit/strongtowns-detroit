#!/usr/bin/env python3
"""Download, hash, and minimally validate the frozen GTFS/OSM inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "strongtowns-detroit/0.1"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            out.write(chunk)
    return digest.hexdigest()


def _dates_from_calendar(zf):
    dates = []
    names = set(zf.namelist())
    if "calendar.txt" in names:
        rows = csv.DictReader(io.TextIOWrapper(zf.open("calendar.txt"), encoding="utf-8-sig"))
        for row in rows:
            dates.extend([row["start_date"], row["end_date"]])
    if "calendar_dates.txt" in names:
        rows = csv.DictReader(
            io.TextIOWrapper(zf.open("calendar_dates.txt"), encoding="utf-8-sig")
        )
        dates.extend(row["date"] for row in rows)
    return [datetime.strptime(value, "%Y%m%d").date() for value in dates if value]


def inspect_gtfs(path, service_date):
    required = {
        "agency.txt", "routes.txt", "trips.txt", "stops.txt", "stop_times.txt"
    }
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        missing = sorted(required - names)
        dates = _dates_from_calendar(zf)
        agencies = []
        if "agency.txt" in names:
            agencies = [
                row.get("agency_name", "")
                for row in csv.DictReader(
                    io.TextIOWrapper(zf.open("agency.txt"), encoding="utf-8-sig")
                )
            ]
    return {
        "agencies": agencies,
        "missing_required_files": missing,
        "calendar_min": min(dates).isoformat() if dates else None,
        "calendar_max": max(dates).isoformat() if dates else None,
        "service_date_within_calendar_envelope": (
            min(dates) <= service_date <= max(dates) if dates else False
        ),
        "warning": (
            "Envelope check is necessary but not sufficient; the R5 run confirms actual "
            "weekday service through calendar rules and exceptions."
        ),
    }


def run(manifest_path, spec_path, output_dir, include_osm=False):
    manifest = json.loads(manifest_path.read_text())
    spec = json.loads(spec_path.read_text())
    service_date = date.fromisoformat(spec["service_date"])
    report = {
        "downloaded_at": datetime.now().astimezone().isoformat(),
        "service_date": service_date.isoformat(),
        "inputs": [],
    }
    for feed in manifest["feeds"]:
        if not feed.get("url"):
            continue
        filename = feed["agency"].lower().replace(" ", "-") + ".zip"
        path = output_dir / filename
        sha = download(feed["url"], path)
        report["inputs"].append(
            {
                "agency": feed["agency"],
                "url": feed["url"],
                "path": str(path),
                "sha256": sha,
                **inspect_gtfs(path, service_date),
            }
        )
    if include_osm:
        path = output_dir / "michigan-latest.osm.pbf"
        sha = download(manifest["osm"]["url"], path)
        report["inputs"].append(
            {
                "agency": "OpenStreetMap/Geofabrik",
                "url": manifest["osm"]["url"],
                "path": str(path),
                "sha256": sha,
            }
        )
    report_path = output_dir / "input-report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Wrote {report_path}")
    for item in report["inputs"]:
        valid = item.get("service_date_within_calendar_envelope", "n/a")
        print(f"{item['agency']}: sha256={item['sha256'][:12]} date-envelope={valid}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=HERE / "feeds.json")
    parser.add_argument("--spec", type=Path, default=HERE / "spec.json")
    parser.add_argument("--output-dir", type=Path, default=HERE / "inputs")
    parser.add_argument(
        "--include-osm", action="store_true",
        help="Also download the large statewide Geofabrik PBF."
    )
    args = parser.parse_args()
    run(args.manifest, args.spec, args.output_dir, args.include_osm)


if __name__ == "__main__":
    main()
