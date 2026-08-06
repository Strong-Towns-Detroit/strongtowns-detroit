#!/usr/bin/env python3
"""Extract BZA addresses and match them to current Detroit assessor parcels."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "bza_dataset_gemini/classified_cases.csv"
DEFAULT_OCCURRENCES = HERE / "bza_dataset_gemini/case_occurrences.csv"
DEFAULT_PARCELS = HERE.parent / "parcel-data/parcels_with_compliance.gpkg"
DEFAULT_OVERRIDES = HERE / "bza_site_overrides.csv"
DEFAULT_OUTPUT = HERE / "bza_dataset_gemini"

SUFFIXES = (
    r"\b(?:AVENUE|AVE|STREET|ST|ROAD|RD|BOULEVARD|BLVD|DRIVE|DR|"
    r"COURT|CT|HIGHWAY|HWY|FREEWAY|FWY)\b$"
)


def clean_street(value: str) -> str:
    value = value.upper().replace(".", " ").strip()
    value = re.sub(r"[^A-Z0-9]+$", "", value)
    previous = None
    while value != previous:
        previous = value
        value = re.sub(SUFFIXES, "", value).strip()
    value = re.sub(r"\bEIGHTH\b", "EIGHT", value)
    value = re.sub(r"\b8\b", "EIGHT", value)
    value = re.sub(r"\b7\b", "SEVEN", value)
    value = re.sub(r"\bNEVEDA\b", "NEVADA", value)
    value = re.sub(r"\bJR\b", "", value)
    value = re.sub(r"\bKLENK ISLAND\b", "KLENK", value)
    value = re.sub(r"^WEST\b", "W", value)
    value = re.sub(r"^EAST\b", "E", value)
    value = re.sub(r"^NORTH\b", "N", value)
    value = re.sub(r"^SOUTH\b", "S", value)
    value = re.sub(r"^MOUNT\b", "MT", value)
    value = re.sub(r"\bFOURTH\b", "4TH", value)
    return re.sub(r"[^A-Z0-9]+", " ", value).strip()


def expanded_numbers(value: str) -> list[int]:
    """Parse address lists, expanding abbreviated range endpoints."""
    numbers = [int(item) for item in re.findall(r"\d{1,6}", value)]
    if re.search(r"(?:-|THRU|TO)", value, flags=re.I) and len(numbers) == 2:
        start, end = numbers
        if end < start:
            magnitude = 10 ** len(str(end))
            end = (start // magnitude) * magnitude + end
            if end < start:
                end += magnitude
        return [start, end]
    return numbers


def address_candidates(location: object) -> list[tuple[int, str]]:
    """Extract every explicit house number/street group before the cross streets."""
    if pd.isna(location):
        return []
    raw = str(location)
    lead = re.split(
        r"\b(?:BETWEEN|LOCATED|CITY COUNCIL|COUNCIL DISTRICT|"
        r"SURROUNDING STREETS|BORDERED BY|CORNER OF)\b",
        raw, 1, flags=re.I,
    )[0]
    aliases = re.findall(
        r"\bAKA\s+(.+?)(?=\bBETWEEN\b|\bIN\s+(?:AN?\s+)?[A-Z0-9-]+\s+"
        r"(?:ZONE|DISTRICT)\b|$)",
        raw,
        flags=re.I,
    )
    parenthetical_addresses = re.findall(
        r"\(\s*(\d{1,6}\s+[A-Za-z][^)]+)\)", raw
    )
    lead = re.sub(r"\([^)]*\)", " ", lead)
    lead_before_aka = re.split(r"\bAKA\b", lead, 1, flags=re.I)[0]
    lead = re.sub(r"\bAKA\b.*$", " ", lead, flags=re.I)
    # Convert an ampersand between two complete address groups to "and" while
    # preserving "& 2535 Green" inside a list of house numbers.
    lead = re.sub(r"([A-Za-z])\s*&\s*(?=\d)", r"\1 and ", lead)
    segments = re.split(r"\s+\bAND\b\s+(?=\d)", lead, flags=re.I)
    segments.extend(aliases)
    segments.extend(parenthetical_addresses)
    candidates: list[tuple[int, str]] = []
    bare_numbers: list[int] = []
    for segment in segments:
        segment = re.sub(r",\s*&", "&", segment)
        match = re.search(
            r"\b(\d{1,6}(?:\s*(?:,|&|AND|-|THRU|TO)\s*\d{1,6})*)"
            r"(?:\s+|(?=[A-Za-z]))(.+)",
            segment, flags=re.I,
        )
        if not match:
            bare = re.fullmatch(
                r"\s*(\d{1,6}(?:\s*(?:,|&|-|THRU|TO)\s*\d{1,6})*)\s*",
                segment,
                flags=re.I,
            )
            if bare:
                bare_numbers.extend(expanded_numbers(bare.group(1)))
            continue
        numbers = expanded_numbers(match.group(1))
        street = clean_street(
            re.split(r"\s+\b(?:IN|WITHIN)\b\s+(?:AN?\s+)?[A-Z0-9-]+", match.group(2), 1, flags=re.I)[0]
        )
        if street:
            candidates.extend((number, street) for number in numbers)
    if bare_numbers and candidates:
        candidates = [
            *((number, candidates[0][1]) for number in bare_numbers),
            *candidates,
        ]
    if aliases:
        alias_candidates = [
            candidate for candidate in candidates
            if any(str(candidate[0]) in alias for alias in aliases)
        ]
        bare_primary = re.fullmatch(r"\s*(\d{1,6})\s*", lead_before_aka)
        if bare_primary and alias_candidates:
            candidates.append((int(bare_primary.group(1)), alias_candidates[0][1]))
    return list(dict.fromkeys(candidates))


def site_key(number: int, street: str) -> str:
    return f"{number}:{clean_street(street)}"


def site_id(key: str) -> str:
    return "site-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def build_matches(
    cases: pd.DataFrame,
    occurrence_map: pd.DataFrame,
    parcels: gpd.GeoDataFrame,
    overrides: pd.DataFrame,
) -> tuple[pd.DataFrame, gpd.GeoDataFrame, dict]:
    minutes = cases[cases["record_type"].eq("minutes_case")][
        ["occurrence_id", "location"]
    ].merge(
        occurrence_map[["occurrence_id", "case_history_id"]],
        on="occurrence_id", how="inner",
    )
    extracted = []
    for row in minutes.itertuples():
        for number, street in address_candidates(row.location):
            extracted.append({
                "case_history_id": row.case_history_id,
                "occurrence_id": row.occurrence_id,
                "site_key": site_key(number, street),
                "site_id": site_id(site_key(number, street)),
                "number": number,
                "street": street,
                "source_location": row.location,
            })
    candidates = pd.DataFrame(extracted).drop_duplicates(
        ["case_history_id", "site_key"]
    )

    parcels = parcels.copy()
    parcels["number"] = pd.to_numeric(parcels["street_number"], errors="coerce")
    parcels = parcels[parcels["number"].notna()].copy()
    parcels["number"] = parcels["number"].astype(int)
    parcels["street"] = (
        parcels["street_prefix"].fillna("").astype(str)
        + " "
        + parcels["street_name"].fillna("").astype(str)
    ).map(clean_street)
    parcels["street_nodir"] = parcels["street"].str.replace(
        r"^(?:N|S|E|W)\s+", "", regex=True
    )
    candidates["street_nodir"] = candidates["street"].str.replace(
        r"^(?:N|S|E|W)\s+", "", regex=True
    )

    exact = candidates.merge(
        parcels[["number", "street", "parcel_id", "address", "geometry"]],
        on=["number", "street"], how="left",
    )
    exact["match_method"] = exact["geometry"].notna().map(
        {True: "exact", False: "unmatched"}
    )

    missing_keys = exact.loc[exact["geometry"].isna(), [
        "case_history_id", "site_key", "number", "street_nodir"
    ]].drop_duplicates()
    # Directionless fallback is allowed only when all matches resolve to one
    # directional street name; condo/unit parcel multiplicity is retained.
    fallback_source = parcels.groupby(["number", "street_nodir"]).filter(
        lambda group: group["street"].nunique() == 1
    )
    fallback = missing_keys.merge(
        fallback_source[
            ["number", "street_nodir", "parcel_id", "address", "geometry"]
        ],
        on=["number", "street_nodir"], how="left",
    )
    fallback = fallback[fallback["geometry"].notna()].copy()
    fallback["match_method"] = "direction_omitted"
    if not fallback.empty:
        base = candidates.merge(
            fallback[[
                "case_history_id", "site_key", "parcel_id", "address",
                "geometry", "match_method",
            ]],
            on=["case_history_id", "site_key"], how="inner",
        )
        exact = pd.concat([exact[exact["geometry"].notna()], base], ignore_index=True)
    else:
        exact = exact[exact["geometry"].notna()].copy()

    override_rows = []
    if not overrides.empty:
        parcel_by_id = parcels.set_index("parcel_id")
        for row in overrides.itertuples():
            if row.action != "assign":
                continue
            if row.parcel_id not in parcel_by_id.index:
                raise ValueError(f"Override parcel absent: {row.parcel_id}")
            source = candidates[candidates["site_key"].eq(row.site_key)]
            for candidate in source.itertuples():
                parcel = parcel_by_id.loc[row.parcel_id]
                override_rows.append({
                    **candidate._asdict(),
                    "parcel_id": row.parcel_id,
                    "address": parcel.address,
                    "geometry": parcel.geometry,
                    "match_method": "manual_override",
                })
    if override_rows:
        override_keys = {(row["case_history_id"], row["site_key"]) for row in override_rows}
        exact = exact[
            ~exact.apply(
                lambda row: (row.case_history_id, row.site_key) in override_keys,
                axis=1,
            )
        ]
        exact = pd.concat([exact, pd.DataFrame(override_rows)], ignore_index=True)

    matched_keys = set(zip(exact["case_history_id"], exact["site_key"]))
    candidates["match_status"] = candidates.apply(
        lambda row: "matched"
        if (row.case_history_id, row.site_key) in matched_keys else "unmatched",
        axis=1,
    )
    counts = exact.groupby(["case_history_id", "site_key"]).size()
    candidates["parcel_match_count"] = candidates.set_index(
        ["case_history_id", "site_key"]
    ).index.map(counts).fillna(0).astype(int)
    candidates.loc[
        candidates["parcel_match_count"].gt(1), "match_status"
    ] = "matched_multiple_parcels"

    geodata = gpd.GeoDataFrame(exact, geometry="geometry", crs=parcels.crs)
    histories_with_candidates = set(candidates["case_history_id"])
    histories_matched = set(geodata["case_history_id"])
    all_histories = set(occurrence_map["case_history_id"])
    audit = {
        "case_histories": len(all_histories),
        "histories_with_extracted_address": len(histories_with_candidates),
        "histories_with_any_parcel_match": len(histories_matched),
        "application_match_share": len(histories_matched) / len(all_histories),
        "address_candidates": int(len(candidates)),
        "matched_address_candidates": int(candidates["match_status"].ne("unmatched").sum()),
        "unmatched_address_candidates": int(candidates["match_status"].eq("unmatched").sum()),
        "matched_multiple_parcels": int(
            candidates["match_status"].eq("matched_multiple_parcels").sum()
        ),
        "histories_without_extracted_address": sorted(
            all_histories - histories_with_candidates
        ),
    }
    return candidates, geodata, audit


def run(
    cases_path: Path,
    occurrences_path: Path,
    parcels_path: Path,
    overrides_path: Path,
    output_dir: Path,
) -> None:
    cases = pd.read_csv(cases_path)
    occurrence_map = pd.read_csv(occurrences_path)
    parcels = gpd.read_file(
        parcels_path,
        columns=[
            "parcel_id", "address", "street_number", "street_prefix",
            "street_name", "geometry",
        ],
    )
    overrides = pd.read_csv(overrides_path)
    candidates, geodata, audit = build_matches(
        cases, occurrence_map, parcels, overrides
    )
    candidates.to_csv(output_dir / "case_site_candidates.csv", index=False)
    geodata.to_file(output_dir / "map_sites.gpkg", driver="GPKG")
    geodata.drop(columns="geometry").to_csv(
        output_dir / "case_site_parcels.csv", index=False
    )
    (output_dir / "site_match_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--occurrences", type=Path, default=DEFAULT_OCCURRENCES)
    parser.add_argument("--parcels", type=Path, default=DEFAULT_PARCELS)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.cases, args.occurrences, args.parcels, args.overrides, args.output_dir)


if __name__ == "__main__":
    main()
