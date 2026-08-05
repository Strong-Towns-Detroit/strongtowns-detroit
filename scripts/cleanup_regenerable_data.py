#!/usr/bin/env python3
"""Inventory and remove explicitly classified reproducible repository data.

Dry-run is the default. Pass --apply only after reviewing the printed manifest.
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Target:
    path: str
    reason: str
    requires: str | None = None


SAFE = [
    Target(".venv", "Root Python environment; recreate from pyproject.toml"),
    Target(
        "pipelines/housingDataAnalysis/.venv",
        "Housing-analysis Python environment; recreate from dependency files",
    ),
    Target(
        "pipelines/parcel-data/.ipynb_checkpoints",
        "Automatic Jupyter checkpoints; notebooks and primary CSVs are retained",
    ),
    Target(".pytest_cache", "Pytest cache"),
    Target(
        "projects/detroit-land-use-forum/base-units-geometry/data/.addresses_pages",
        "Completed fetch pages duplicated by base_units_addresses.geojson",
        "projects/detroit-land-use-forum/base-units-geometry/data/base_units_addresses.geojson",
    ),
    Target(
        "projects/detroit-land-use-forum/base-units-geometry/data/.streets_pages",
        "Completed fetch pages duplicated by base_units_streets.geojson",
        "projects/detroit-land-use-forum/base-units-geometry/data/base_units_streets.geojson",
    ),
    Target(
        "projects/detroit-land-use-forum/base-units-geometry/data/.buildings_pages",
        "Completed fetch pages duplicated by base_units_buildings.geojson",
        "projects/detroit-land-use-forum/base-units-geometry/data/base_units_buildings.geojson",
    ),
]

STANDARD = [
    Target(
        "pipelines/parcel-data/venv",
        "Legacy parcel-pipeline environment; no lockfile, so excluded from safe profile",
    ),
    Target(
        "pipelines/parcel-data/parcels_with_buildability.gpkg",
        "Legacy derived parcel artifact; current analysis uses parcels_with_compliance.gpkg",
    ),
    Target(
        "pipelines/parcel-data/parcel-data-with-buildability.csv",
        "Legacy derived parcel table; reproducible from retained parcel inputs",
    ),
    Target(
        "pipelines/parcel-data/parcel-data-with-zoning-districts-mapping.csv",
        "Intermediate parcel/zoning join; reproducible from retained inputs",
    ),
    Target(
        "pipelines/parcel-data/parcels_with_compliance.csv",
        "CSV duplicate of retained parcels_with_compliance.gpkg",
        "pipelines/parcel-data/parcels_with_compliance.gpkg",
    ),
    Target(
        "pipelines/parcel-data/parcel-data-cleaned.csv",
        "Legacy input fallback; current pipeline prefers retained parcel-data.csv",
        "pipelines/parcel-data/parcel-data.csv",
    ),
    Target(
        "pipelines/parcel-data/non_conforming_parcels.csv",
        "Derived analysis export; reproducible from retained compliance data",
    ),
    Target(
        "projects/detroit-land-use-forum/base-units-geometry/output",
        "Derived Base Units analysis; regenerate with analyze_base_units.py analyze",
        "projects/detroit-land-use-forum/base-units-geometry/data/base_units_buildings.geojson",
    ),
    Target(
        "pipelines/housingDataAnalysis/street_simplification/cache",
        "Derived street-simplification cache",
    ),
    Target(
        "pipelines/housingDataAnalysis/street_simplification/output",
        "Derived street-simplification exports",
    ),
]

AGGRESSIVE = [
    Target(
        "cache",
        "Downloaded/generated OSM and routing caches; reproducible but costly",
    ),
    Target(
        "projects/detroit-land-use-forum/bza-relief-atlas/output",
        "Rendered HTML/SVG/PNG; regenerate with build_atlas.py",
    ),
    Target(
        "projects/detroit-land-use-forum/bza-repeat-sites/output",
        "Rendered repeat-site exhibit; regenerate with its build script",
    ),
    Target(
        "projects/detroit-land-use-forum/parcel-geometry/output",
        "Rendered parcel-geometry exhibit; regenerate with its build script",
    ),
    Target(
        "projects/detroit-land-use-forum/spirit-plaza-accessibility/output",
        "Rendered accessibility assets and prepared context; regenerate from project scripts",
    ),
    Target("output/viz", "Derived visualization exports"),
]


def size_bytes(path: Path) -> int:
    if not path.exists() and not path.is_symlink():
        return 0
    if path.is_file() or path.is_symlink():
        return path.lstat().st_size
    return sum(
        item.lstat().st_size
        for item in path.rglob("*")
        if item.is_file() or item.is_symlink()
    )


def human_size(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}"
        number /= 1024
    raise AssertionError("unreachable")


def validate_target(target: Target) -> tuple[Path, str | None]:
    path = (ROOT / target.path).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as error:
        raise RuntimeError(f"Target escapes repository: {path}") from error
    if path == ROOT:
        raise RuntimeError("Refusing to target repository root")
    if target.requires:
        required = ROOT / target.requires
        if not required.is_file() or required.stat().st_size == 0:
            return path, f"required retained file is absent: {target.requires}"
    return path, None


def discovered_cache_targets() -> list[Target]:
    result = []
    for path in ROOT.rglob("__pycache__"):
        if any(parent.name in {".venv", "venv"} for parent in path.parents):
            continue
        result.append(
            Target(str(path.relative_to(ROOT)), "Regenerable Python bytecode")
        )
    for path in ROOT.rglob(".DS_Store"):
        result.append(Target(str(path.relative_to(ROOT)), "macOS metadata"))
    return result


def remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run inventory of explicitly regenerable repository data."
    )
    parser.add_argument(
        "--profile",
        choices=["safe", "standard", "aggressive"],
        default="safe",
        help=(
            "safe: environments/checkpoints/page caches; standard: also legacy "
            "derived data; aggressive: also network caches and rendered assets"
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Permanently delete the displayed targets",
    )
    args = parser.parse_args()

    targets = [*SAFE, *discovered_cache_targets()]
    if args.profile in {"standard", "aggressive"}:
        targets.extend(STANDARD)
    if args.profile == "aggressive":
        targets.extend(AGGRESSIVE)

    unique = {target.path: target for target in targets}
    rows = []
    skipped = []
    for target in unique.values():
        path, error = validate_target(target)
        if error:
            skipped.append((target, error))
            continue
        size = size_bytes(path)
        if size:
            rows.append((target, path, size))
    rows.sort(key=lambda row: row[2], reverse=True)

    action = "DELETE" if args.apply else "WOULD DELETE"
    print(f"{action} profile={args.profile} root={ROOT}")
    print()
    for target, path, size in rows:
        print(f"{human_size(size):>10}  {path.relative_to(ROOT)}")
        print(f"{'':>12}{target.reason}")
    total = sum(row[2] for row in rows)
    print(f"\nEstimated reclaimable space: {human_size(total)}")
    if skipped:
        print("\nSkipped safety-guarded targets:")
        for target, error in skipped:
            print(f"  {target.path}: {error}")

    if not args.apply:
        print(
            f"\nDry run only. Re-run with --profile {args.profile} --apply "
            "to delete exactly these targets."
        )
        return
    for _, path, _ in rows:
        remove(path)
    print(f"\nRemoved {len(rows)} targets; estimated {human_size(total)} reclaimed.")


if __name__ == "__main__":
    main()
