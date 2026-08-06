#!/usr/bin/env python3
"""Archive repository data that cannot be cheaply reproduced.

The complement of cleanup_regenerable_data.py: that script removes what a build
can rebuild, this one preserves what it cannot. Dry-run is the default for every
command that writes.

Backend is Cloudflare R2 over its S3-compatible API. Configure via environment:

    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET

Usage:

    python scripts/data_archive.py status                 # local vs remote
    python scripts/data_archive.py push --tier critical   # dry run
    python scripts/data_archive.py push --tier critical --apply
    python scripts/data_archive.py pull --tier critical --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "data_archive_manifest.json"
PREFIX = "archive/v1"
CHUNK = 8 * 1024 * 1024


@dataclass(frozen=True)
class Asset:
    path: str
    reason: str
    tier: str


# Impossible to reproduce. Municode is versioned and mutable upstream: a later
# scrape yields a different ordinance, which would silently invalidate every
# source-span citation in the compiled rule set. The BZA extractions cost real
# Gemini API spend across ~800 documents.
CRITICAL = [
    Asset(
        "resources/municode",
        "Point-in-time Chapter 50 snapshot (2025-10-09, Supplement 4); "
        "every compiled rule cites it and upstream overwrites it",
        "critical",
    ),
    Asset(
        "pipelines/zoning/bza_dataset_gemini",
        "Vision-model extraction over ~800 BZA documents; paid API spend",
        "critical",
    ),
    Asset(
        "pipelines/zoning/bza_minutes",
        "Scraped BZA minutes PDFs; the city rotates its document listing",
        "critical",
    ),
]

# Re-downloadable in principle, but these are dated snapshots of a mutable
# public source. Keeping them is what makes a past analysis reproducible.
SOURCE = [
    Asset(
        "pipelines/parcel-data/Parcels.geojson",
        "Detroit Open Data parcel geometry; the published layer changes over time",
        "source",
    ),
    Asset(
        "pipelines/parcel-data/parcel-data.csv",
        "Detroit assessor parcel table; superseded in place upstream",
        "source",
    ),
    Asset(
        "projects/detroit-land-use-forum/base-units-geometry/data",
        "Consolidated Base Units address, street, and building layers",
        "source",
    ),
    Asset(
        "data/lihtc",
        "HUD 2026 QCT designations as fetched; HUD re-designates annually",
        "source",
    ),
    Asset(
        "pipelines/housingDataAnalysis/street_simplification/output/detroit_boundary.geojson",
        "City boundary basemap; 49 KB, and re-deriving it needs an OSMnx network pull",
        "source",
    ),
    Asset(
        "pipelines/housingDataAnalysis/street_simplification/output/detroit_water.geojson",
        "Water basemap; 2.4 MB, same re-derivation cost as the boundary",
        "source",
    ),
]


@dataclass(frozen=True)
class Recipe:
    """A derived artifact that is deliberately not archived, and how to rebuild it."""

    path: str
    command: str
    inputs: tuple[str, ...]


# Everything here is recreatable, so it stays out of the archive. The point of
# recording it is that "recreatable" is only true while the inputs survive --
# `recipes` checks exactly that.
RECIPES = [
    Recipe(
        "pipelines/parcel-data/parcels_with_compliance.gpkg",
        "cd pipelines/parcel-data && python merge_and_calculate.py",
        ("pipelines/parcel-data/Parcels.geojson", "pipelines/parcel-data/parcel-data.csv"),
    ),
    Recipe(
        "pipelines/parcel-data/parcels_with_compliance.csv",
        "cd pipelines/parcel-data && python merge_and_calculate.py",
        ("pipelines/parcel-data/Parcels.geojson", "pipelines/parcel-data/parcel-data.csv"),
    ),
    Recipe(
        "projects/detroit-land-use-forum/lihtc-site-selection/output/parcels_qct.parquet",
        "python projects/detroit-land-use-forum/lihtc-site-selection/build_qct_join.py",
        ("pipelines/parcel-data/parcels_with_compliance.gpkg", "data/lihtc/qct_2026_wayne.geojson"),
    ),
    Recipe(
        "projects/detroit-land-use-forum/lihtc-site-selection/output/assembled_public.gpkg",
        "python projects/detroit-land-use-forum/lihtc-site-selection/assembly.py",
        ("pipelines/parcel-data/parcels_with_compliance.gpkg", "data/lihtc/qct_2026_wayne.geojson"),
    ),
    Recipe(
        "projects/detroit-land-use-forum/base-units-geometry/output",
        "python projects/detroit-land-use-forum/base-units-geometry/analyze_base_units.py analyze",
        ("projects/detroit-land-use-forum/base-units-geometry/data",),
    ),
    Recipe(
        "projects/detroit-land-use-forum/conference-canonical",
        "python projects/detroit-land-use-forum/build_conference_bundle.py",
        ("pipelines/parcel-data/parcels_with_compliance.gpkg", "pipelines/zoning/bza_dataset_gemini"),
    ),
]

# Rendered outputs. Reproducible from the build scripts only while their inputs
# survive, which is the whole reason the tiers above exist.
DELIVERABLE = [
    Asset(
        "projects/detroit-land-use-forum/conference-canonical",
        "Thirteen canonical forum exhibits as published",
        "deliverable",
    ),
    Asset(
        "projects/detroit-land-use-forum/conference-print",
        "Print-resolution exhibit bundles",
        "deliverable",
    ),
]

TIERS = {"critical": CRITICAL, "source": SOURCE, "deliverable": DELIVERABLE}


def human_size(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}"
        number /= 1024
    raise AssertionError("unreachable")


def resolve(asset: Asset) -> Path:
    """Resolve an asset path, refusing anything outside the repository."""
    path = (ROOT / asset.path).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as error:
        raise RuntimeError(f"Asset escapes repository: {path}") from error
    if path == ROOT:
        raise RuntimeError("Refusing to archive repository root")
    return path


def files_for(asset: Asset) -> list[Path]:
    path = resolve(asset)
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def key_for(path: Path) -> str:
    return f"{PREFIX}/{path.relative_to(ROOT).as_posix()}"


def selected(tiers: list[str]) -> list[Asset]:
    return [asset for tier in tiers for asset in TIERS[tier]]


def load_manifest() -> dict:
    if MANIFEST.is_file():
        return json.loads(MANIFEST.read_text())
    return {"entries": {}}


def client():
    """Build an R2 S3 client, failing with actionable guidance."""
    missing = [
        name
        for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
        if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit(
            "Missing environment variables: "
            + ", ".join(missing)
            + "\nSee scripts/DATA_ARCHIVE.md for how to create the bucket and token."
        )
    try:
        import boto3
        from botocore.config import Config
    except ModuleNotFoundError as error:
        raise SystemExit(
            "boto3 is required for push/pull. Install with:\n"
            "    pip install 'strongtowns-detroit[archive]'"
        ) from error
    account = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
    )


def cmd_status(args) -> None:
    manifest = load_manifest()["entries"]
    total = 0
    print(f"{'TIER':<12}{'ASSET':<58}{'FILES':>7}{'SIZE':>11}  STATE")
    for asset in selected(args.tier):
        paths = files_for(asset)
        size = sum(p.stat().st_size for p in paths)
        total += size
        if not paths:
            state = "MISSING locally"
        else:
            known = sum(1 for p in paths if key_for(p) in manifest)
            state = "archived" if known == len(paths) else f"{len(paths) - known} not archived"
        print(
            f"{asset.tier:<12}{asset.path[:56]:<58}{len(paths):>7}"
            f"{human_size(size):>11}  {state}"
        )
    print(f"\n{'':<12}{'TOTAL':<58}{'':>7}{human_size(total):>11}")
    if not manifest:
        print("\nNo manifest yet — nothing has been pushed.")


def cmd_push(args) -> None:
    manifest = load_manifest()
    entries = manifest["entries"]
    assets = selected(args.tier)
    pending: list[tuple[Path, str, str]] = []
    unchanged = 0

    for asset in assets:
        for path in files_for(asset):
            key = key_for(path)
            digest = sha256(path)
            if entries.get(key, {}).get("sha256") == digest:
                unchanged += 1
                continue
            pending.append((path, key, digest))

    size = sum(p.stat().st_size for p, _, _ in pending)
    print(f"{len(pending)} file(s) to upload, {human_size(size)}  ({unchanged} unchanged)")
    for path, key, _ in pending[:15]:
        print(f"  {human_size(path.stat().st_size):>10}  {key}")
    if len(pending) > 15:
        print(f"  … and {len(pending) - 15} more")

    if not args.apply:
        print("\nDry run. Re-run with --apply to upload.")
        return
    if not pending:
        print("Nothing to do.")
        return

    s3 = client()
    bucket = os.environ["R2_BUCKET"]
    for index, (path, key, digest) in enumerate(pending, start=1):
        print(f"[{index}/{len(pending)}] {key}", flush=True)
        s3.upload_file(str(path), bucket, key)
        entries[key] = {
            "sha256": digest,
            "size": path.stat().st_size,
            "path": path.relative_to(ROOT).as_posix(),
        }
        MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"\nUploaded {len(pending)} file(s). Manifest updated: {MANIFEST.relative_to(ROOT)}")


def cmd_pull(args) -> None:
    entries = load_manifest()["entries"]
    if not entries:
        raise SystemExit("No manifest — nothing has been archived yet.")
    wanted = {asset.path for asset in selected(args.tier)}
    targets = [
        (key, meta)
        for key, meta in sorted(entries.items())
        if any(meta["path"] == w or meta["path"].startswith(w + "/") for w in wanted)
    ]
    missing = [
        (key, meta)
        for key, meta in targets
        if not (ROOT / meta["path"]).is_file()
        or sha256(ROOT / meta["path"]) != meta["sha256"]
    ]
    size = sum(meta["size"] for _, meta in missing)
    print(f"{len(missing)} of {len(targets)} file(s) missing or altered, {human_size(size)}")
    for key, meta in missing[:15]:
        print(f"  {human_size(meta['size']):>10}  {meta['path']}")
    if len(missing) > 15:
        print(f"  … and {len(missing) - 15} more")

    if not args.apply:
        print("\nDry run. Re-run with --apply to download.")
        return
    if not missing:
        print("Everything present and verified.")
        return

    s3 = client()
    bucket = os.environ["R2_BUCKET"]
    for index, (key, meta) in enumerate(missing, start=1):
        destination = ROOT / meta["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{index}/{len(missing)}] {meta['path']}", flush=True)
        s3.download_file(bucket, key, str(destination))
        if sha256(destination) != meta["sha256"]:
            raise SystemExit(f"Checksum mismatch after download: {meta['path']}")
    print(f"\nRestored {len(missing)} file(s), all checksums verified.")


def cmd_recipes(args) -> None:
    """Report whether each unarchived derived artifact can still be rebuilt."""
    archived = {a.path for tier in TIERS.values() for a in tier}
    broken = 0
    for recipe in RECIPES:
        target = ROOT / recipe.path
        present = target.exists()
        missing = [
            i
            for i in recipe.inputs
            if not (ROOT / i).exists() and i not in archived
        ]
        if missing:
            state, broken = "NOT REBUILDABLE", broken + 1
        elif present:
            state = "present"
        else:
            state = "absent, rebuildable"
        print(f"\n{recipe.path}\n  state:   {state}\n  rebuild: {recipe.command}")
        for i in recipe.inputs:
            local = (ROOT / i).exists()
            mark = "local" if local else ("archived" if i in archived else "MISSING")
            print(f"  input:   [{mark}] {i}")
    print(
        f"\n{len(RECIPES)} derived artifact(s) tracked; {broken} cannot be rebuilt."
        if broken
        else f"\n{len(RECIPES)} derived artifact(s) tracked; all rebuildable."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    recipes = sub.add_parser("recipes", help="Show rebuild commands for unarchived derived data")
    recipes.set_defaults(handler=cmd_recipes, tier=["critical"])
    for name, handler, helptext in [
        ("status", cmd_status, "Compare local assets against the archive manifest"),
        ("push", cmd_push, "Upload changed assets to R2"),
        ("pull", cmd_pull, "Restore missing or altered assets from R2"),
    ]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument(
            "--tier",
            action="append",
            choices=sorted(TIERS),
            help="Repeatable. Defaults to critical only, the irreplaceable data.",
        )
        if name != "status":
            p.add_argument("--apply", action="store_true", help="Perform the transfer")
        p.set_defaults(handler=handler)

    args = parser.parse_args()
    args.tier = args.tier or ["critical"]
    args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
