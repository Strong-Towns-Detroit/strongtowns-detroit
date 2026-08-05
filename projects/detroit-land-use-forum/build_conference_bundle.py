#!/usr/bin/env python3
"""Collect the canonical Detroit Land Use Forum conference exhibits."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "conference-canonical"

EXHIBITS = [
    (
        "01-bza-cases-by-request-type",
        "BZA cases by request type",
        HERE / "parcel-geometry/output/detroit-bza-request-types",
    ),
    (
        "02-bza-cases-map",
        "Detroit Board of Zoning Appeals cases",
        HERE / "bza-relief-atlas/output/relief_type_map",
    ),
    (
        "03-minimum-lot-area",
        "Detroit's 5,000-square-foot minimum lot area",
        HERE / "parcel-geometry/output/detroit-minimum-lot-size",
    ),
    (
        "04-minimum-lot-width",
        "Detroit's 50-foot minimum residential lot width",
        HERE / "parcel-geometry/output/detroit-minimum-lot-width",
    ),
    (
        "05-residential-setback-envelope",
        "Detroit's single- and two-family setback envelope",
        HERE / "parcel-geometry/output/detroit-residential-setback-envelope",
    ),
    (
        "06-parking-gaps-by-project-type",
        "Parking gaps by project type",
        HERE / "parking-by-project-type/output/detroit-parking-by-project-type",
    ),
    (
        "07-campus-martius-transit",
        "Transit is barely viable along the inner spokes",
        HERE / "spirit-plaza-accessibility/output/share/public-transit",
    ),
    (
        "08-campus-martius-driving",
        "A 15-minute city—by car",
        HERE / "spirit-plaza-accessibility/output/share/driving",
    ),
    (
        "09-bza-cases-by-proposed-use",
        "BZA cases by proposed use",
        HERE / "bza-use-types/output/detroit-bza-proposed-use-types",
    ),
    (
        "10-bza-proposed-use-map",
        "Proposed uses in Detroit BZA cases",
        HERE / "bza-use-types/output/detroit-bza-proposed-use-map",
    ),
    (
        "11-assessed-value-per-acre",
        "Detroit's assessed property value per acre",
        HERE / "assessed-value-per-acre/output/detroit-assessed-value-per-acre",
    ),
    (
        "12-estimated-assessed-land-value",
        "An estimate of Detroit's assessed land value",
        HERE / "land-value-estimate/output/detroit-estimated-assessed-land-value",
    ),
    (
        "13-dalt-property-tax-comparison",
        "A ten-year building exemption approaches a land value tax",
        HERE / "dalt-comparison/output/dalt-property-tax-comparison",
    ),
]


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for slug, title, source in EXHIBITS:
        files = {}
        for extension in ("html", "svg", "png"):
            source_file = source.with_suffix(f".{extension}")
            if not source_file.exists():
                raise FileNotFoundError(source_file)
            destination = OUT / f"{slug}.{extension}"
            shutil.copy2(source_file, destination)
            files[extension] = destination.name
        manifest.append(
            {
                "order": len(manifest) + 1,
                "slug": slug,
                "title": title,
                "source": str(source.relative_to(HERE)),
                "files": files,
            }
        )
    (OUT / "manifest.json").write_text(
        json.dumps({"exhibits": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(manifest)} canonical exhibits to {OUT}")


if __name__ == "__main__":
    run()
