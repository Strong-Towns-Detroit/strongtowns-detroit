#!/usr/bin/env python3
"""Run or merge bounded setback-envelope geometry batches."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from build_residential_setback_asset import load_and_classify

HERE = Path(__file__).resolve().parent
BATCH_DIR = HERE / "output/setback_batches"
RESULT_COLUMNS = [
    "parcel_key",
    "evaluation_reason",
    "frontage_confidence",
    "setback_envelope_area_sqft",
    "principal_outside_envelope_sqft",
    "evaluated",
    "crosses_envelope",
]


def run_batch(start: int, size: int) -> Path:
    frame = load_and_classify(size, start)
    selected = frame[
        frame["in_scope"]
        & ~frame["candidate_multi_parcel_site"]
        & ~frame["evaluation_reason"].eq("outside_debug_sample")
    ][RESULT_COLUMNS]
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    path = BATCH_DIR / f"batch_{start:06d}_{start + size:06d}.csv"
    selected.to_csv(path, index=False)
    print(
        f"{path}: {len(selected):,} processed; "
        f"{selected['evaluated'].sum():,} evaluated; "
        f"{selected['crosses_envelope'].sum():,} cross"
    )
    return path


def merge_batches() -> Path:
    paths = sorted(BATCH_DIR.glob("batch_*.csv"))
    if not paths:
        raise SystemExit(f"No batches found under {BATCH_DIR}")
    result = pd.concat(
        [pd.read_csv(path, dtype={"parcel_key": "string"}) for path in paths],
        ignore_index=True,
    )
    duplicates = result["parcel_key"].duplicated().sum()
    if duplicates:
        raise SystemExit(f"Refusing to merge {duplicates} duplicate parcel keys")
    path = BATCH_DIR.parent / "single-family-setback-results.csv"
    result.to_csv(path, index=False)
    print(
        f"{path}: {len(result):,} processed; "
        f"{result['evaluated'].sum():,} evaluated; "
        f"{result['crosses_envelope'].sum():,} cross"
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int)
    parser.add_argument("--size", type=int, default=10_000)
    parser.add_argument("--merge", action="store_true")
    args = parser.parse_args()
    if args.merge:
        merge_batches()
    elif args.start is not None:
        run_batch(args.start, args.size)
    else:
        parser.error("provide --start or --merge")


if __name__ == "__main__":
    main()
