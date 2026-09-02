#!/usr/bin/env python3
"""Build web map tiles for the parcel-geometry publications.

Python owns the classification; the browser only draws it. Each legal test is
imported from its published exhibit builder rather than restated here, so the
interactive map, the frozen board, and the printed conference exhibit cannot
disagree about which parcels fail.

Every rule shares the same 378,366 parcel geometries, so they share one archive
with one column per rule. Shipping a 52 MB archive per rule would be five
copies of the same polygons, and it would make layer switching a download
rather than a repaint.

Two tiers, both static and servable from object storage:

    public/data/zoning/parcels-display.pmtiles   overview, z10 only, ~8 MB
    public/data/zoning/parcels.pmtiles           full detail, z10-z15, ~60 MB
    public/data/zoning/parcel-rules.json         the figures pages and boards show

The citywide view paints the overview tier: a single z10 tile out of the full
archive is several megabytes, which is a poor first paint for a map whose
opening view is the whole city. The full archive backs zoomed-in painting and
every click lookup. Both are generated here from one classification pass, so a
column added to one is never missing from the other — which is exactly the bug
this split caused when the display tier was built by hand.

Usage:
    python scripts/build_parcel_tiles.py [--max-zoom 15] [--rules lot_area,lot_width]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import geopandas as gpd
import pandas as pd

from strongtowns_detroit.repositories import data_repository

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
ROOT = SITE.parents[1]
FORUM = ROOT / "projects/detroit-land-use-forum"

sys.path.insert(0, str(FORUM))
sys.path.insert(0, str(FORUM / "parcel-geometry"))
from build_minimum_lot_size_asset import (  # noqa: E402
    AREA_MINIMUM,
    classify_lot_area,
    select_residential_area_cases,
)
from build_minimum_lot_size_asset import (  # noqa: E402
    SCREENING_BOUNDARY as AREA_BOUNDARY,
)
from build_minimum_lot_width_asset import (  # noqa: E402
    WIDTH_MINIMUM,
    classify_lot_width,
    select_residential_width_cases,
)
from build_minimum_lot_width_asset import (  # noqa: E402
    SCREENING_BOUNDARY as WIDTH_BOUNDARY,
)
from build_residential_setback_asset import (  # noqa: E402
    load_merged_classification,
    select_house_setback_cases,
)

sys.path.insert(0, str(FORUM / "assessed-value-per-acre"))
from build_assessed_value_asset import (  # noqa: E402
    BANDS,
    classify as classify_assessed_value,
    concentration,
)

DATA_REPOSITORY = data_repository()
PARCELS = DATA_REPOSITORY / "pipelines/parcel-data/parcels_with_compliance.gpkg"
ROADS = FORUM / "spirit-plaza-accessibility/output/road_context.geojson"
BZA = DATA_REPOSITORY / "pipelines/zoning/bza_dataset_gemini"
OUT_DIR = SITE / "public/data/zoning"

RESIDENTIAL = [f"R{i}" for i in range(1, 7)]


@dataclass(frozen=True)
class Rule:
    """One dimensional standard, evaluated over every parcel."""

    key: str
    """Short name used for the tile column: `st_<key>`."""
    measure_column: str
    """Column on the classified frame holding the measured value."""
    measure_field: str
    """Tile property name for the measured value."""
    select_cases: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]
    unit: str

    # A rule either derives its result from parcel attributes we already read...
    source_columns: list[str] = field(default_factory=list)
    classify: Callable[[gpd.GeoDataFrame], gpd.GeoDataFrame] | None = None
    # ...or loads a result computed elsewhere and joins it on parcel_id. The
    # setback envelope is the second kind: running its geometry model over every
    # parcel takes hours, so the exhibit publishes a results CSV and this reads
    # that, exactly as the printed board does.
    load: Callable[[], gpd.GeoDataFrame] | None = None

    legal_minimum: float | None = None
    screening_boundary: float | None = None

    #: Boolean column meaning "fails the standard as measured".
    failing_column: str = "below_minimum"
    #: The dimensional rules treat a parcel with no zoning district as unevaluable;
    #: the setback rule scopes by building type instead, where a missing district
    #: simply falls outside scope.
    unknown_when_district_missing: bool = True


RULES = {
    "lot_area": Rule(
        key="area",
        measure_column="area_sqft",
        measure_field="sqft",
        source_columns=["total_square_footage"],
        classify=classify_lot_area,
        select_cases=select_residential_area_cases,
        legal_minimum=AREA_MINIMUM,
        screening_boundary=AREA_BOUNDARY,
        unit="square_feet",
    ),
    "lot_width": Rule(
        key="width",
        measure_column="width_ft",
        measure_field="width",
        source_columns=["frontage"],
        classify=classify_lot_width,
        select_cases=select_residential_width_cases,
        legal_minimum=WIDTH_MINIMUM,
        screening_boundary=WIDTH_BOUNDARY,
        unit="feet",
    ),
    "setback_envelope": Rule(
        key="setback",
        measure_column="principal_outside_envelope_sqft",
        measure_field="outside_sqft",
        load=load_merged_classification,
        select_cases=select_house_setback_cases,
        failing_column="crosses_envelope",
        unknown_when_district_missing=False,
        unit="square_feet",
    ),
}

@dataclass(frozen=True)
class Quantity:
    """A banded quantity choropleth, as opposed to a four-state rule.

    Assessed value per acre is not a compliance test — nothing passes or fails
    it — so it carries a band per parcel rather than a status, and a
    distribution statistic rather than a share below a minimum.
    """

    key: str
    """Tile column suffix: `band_<key>` and the measured value field."""
    measure_field: str
    source_columns: list[str]
    classify: Callable[[gpd.GeoDataFrame], gpd.GeoDataFrame]
    value_column: str
    #: Maps the classifier's own output colour back to a stable band key. The
    #: exhibit's bins are exclusive-lower and inclusive-upper, which a MapLibre
    #: `step` expression cannot express, so the binning stays in Python and the
    #: browser only paints a category. Reading the colour the published
    #: classifier already assigned avoids restating its comparisons.
    band_of_color: dict[str, str]
    summarize: Callable[[gpd.GeoDataFrame], dict[str, object]]


def assessed_value_summary(frame: gpd.GeoDataFrame) -> dict[str, object]:
    recorded = frame[frame["recorded"]]
    return {
        "totalParcels": int(len(frame)),
        "recordedParcels": int(len(recorded)),
        "zeroAssessmentParcels": int(recorded["assessed"].eq(0).sum()),
        "unrecordedParcels": int((~frame["recorded"]).sum()),
        "topTenPercentLandValueShare": concentration(frame),
    }


QUANTITIES = {
    "assessed_value_per_acre": Quantity(
        key="av",
        measure_field="vpa",
        source_columns=["assessed_value", "total_square_footage"],
        classify=classify_assessed_value,
        value_column="assessed_value_per_acre",
        band_of_color={
            color: f"b{index}" for index, (_, _, _, color) in enumerate(BANDS)
        },
        summarize=assessed_value_summary,
    ),
}


BASE_COLUMNS = [
    "parcel_id",
    "address",
    "zoning_district",
    "taxpayer_1",
    "taxpayer_2",
    "geometry",
]


def status_of(frame: gpd.GeoDataFrame, rule: "Rule") -> pd.Series:
    """Collapse the classification flags into one categorical status.

    Four states, never three: "meets" and "fails" are not exhaustive, and
    collapsing "unknown" into either would misreport the finding. `outside` and
    `unknown` share a colour on the map but stay distinct in the data so the
    inspector can tell a visitor which one applies to their parcel.
    """
    failing = frame[rule.failing_column]
    status = pd.Series("outside", index=frame.index, dtype="object")
    if rule.unknown_when_district_missing:
        status[frame["zoning_district"].isna()] = "unknown"
    status[frame["in_scope"] & ~frame["evaluated"]] = "unknown"
    status[frame["evaluated"] & ~failing] = "meets"
    status[failing] = "below"
    return status


def summarize(
    frame: gpd.GeoDataFrame,
    rule: Rule,
    cases: pd.DataFrame,
    status: pd.Series,
) -> dict[str, object]:
    """Report the same counts the map paints.

    The status series is the single source: deriving the reported totals from a
    second, separately written predicate is how the summary came to claim 39,106
    unevaluable parcels while the map coloured 37,213 of them.
    """
    evaluated = int(frame["evaluated"].sum())
    below = int(frame[rule.failing_column].sum())
    assert below == int((status == "below").sum()), "status disagrees with the flag"
    return {
        "legalMinimum": rule.legal_minimum,
        "screeningBoundary": rule.screening_boundary,
        "unit": rule.unit,
        "evaluatedParcels": evaluated,
        "belowMinimumParcels": below,
        "meetsMinimumParcels": evaluated - below,
        "belowMinimumShare": below / evaluated,
        "unknownParcels": int((status == "unknown").sum()),
        "outsideScopeParcels": int((status == "outside").sum()),
        "parksParcels": int(
            (
                frame["parks_taxpayer"]
                & frame["zoning_district"].isin(RESIDENTIAL)
            ).sum()
        ) if "parks_taxpayer" in frame else 0,
        "totalParcels": int(len(frame)),
        "bzaCases": int(len(cases)),
        "bzaGrantedOrReversed": int(
            cases["final_outcome"].eq("granted_reversed").sum()
        ),
    }


def run_tippecanoe(
    parcels: Path,
    roads: Path,
    destination: Path,
    *,
    max_zoom: int,
    full_detail: int,
    simplification: int,
    shared_borders: bool,
    min_zoom: int = 10,
) -> None:
    if not shutil.which("tippecanoe"):
        raise SystemExit(
            "tippecanoe not found. Install it with `brew install tippecanoe`."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "tippecanoe",
            "--output", str(destination),
            "--force",
            "--minimum-zoom", str(min_zoom),
            "--maximum-zoom", str(max_zoom),
            # The display archive is intentionally authored with z10 as its
            # maximum. Preserve real parcel outlines there rather than applying
            # Tippecanoe's low-zoom simplification and tiny-polygon diffusion.
            "--full-detail", str(full_detail),
            "--simplify-only-low-zooms",
            "--no-tiny-polygon-reduction-at-maximum-zoom",
            # -r1 keeps every parcel at every zoom. The default density
            # thinning would quietly change the colour proportions of a
            # citywide choropleth, which is exactly the number these
            # publications report.
            "--drop-rate", "1",
            "--no-feature-limit",
            "--no-tile-size-limit",
            "--simplification", str(simplification),
            # --detect-shared-borders snaps adjacent parcel edges together to
            # remove slivers. It also grows parcels into the street gaps
            # between them, which shows up against the printed board as red
            # painted over what should be background. Off by default.
            *(["--detect-shared-borders"] if shared_borders else []),
            "--named-layer", f"parcels:{parcels}",
            "--named-layer", f"roads:{roads}",
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-zoom", type=int, default=15)
    parser.add_argument("--full-detail", type=int, default=14)
    parser.add_argument("--simplification", type=int, default=2)
    parser.add_argument("--shared-borders", action="store_true")
    parser.add_argument("--output", default="parcels.pmtiles")
    parser.add_argument(
        "--display-output", default="parcels-display.pmtiles"
    )
    parser.add_argument("--display-zoom", type=int, default=10)
    parser.add_argument(
        "--skip-display",
        action="store_true",
        help="Only rebuild the full archive.",
    )
    parser.add_argument(
        "--rules",
        default=",".join(RULES),
        help="Comma-separated rule names to evaluate.",
    )
    parser.add_argument(
        "--quantities",
        default=",".join(QUANTITIES),
        help="Comma-separated quantity choropleths to evaluate.",
    )
    args = parser.parse_args()

    selected = [name.strip() for name in args.rules.split(",") if name.strip()]
    unknown = [name for name in selected if name not in RULES]
    if unknown:
        raise SystemExit(f"Unknown rule(s): {', '.join(unknown)}")

    quantities = [q.strip() for q in args.quantities.split(",") if q.strip()]
    unknown_q = [q for q in quantities if q not in QUANTITIES]
    if unknown_q:
        raise SystemExit(f"Unknown quantity/quantities: {', '.join(unknown_q)}")

    needed = sorted(
        {c for name in selected for c in RULES[name].source_columns}
        | {c for name in quantities for c in QUANTITIES[name].source_columns}
    )
    print(f"Reading {PARCELS.name} ...", flush=True)
    raw = gpd.read_file(PARCELS, columns=BASE_COLUMNS + needed)
    print(f"  {len(raw):,} parcels", flush=True)

    # One frame, one column per rule. Every rule is evaluated over the same
    # geometry, so the tiles stay a single archive.
    features = gpd.GeoDataFrame(
        {
            "pid": raw["parcel_id"].astype("string"),
            "addr": raw["address"].astype("string"),
            "zd": raw["zoning_district"].astype("string"),
        },
        geometry=raw.geometry,
        crs=raw.crs,
    )

    summaries: dict[str, object] = {}
    histories = pd.read_csv(BZA / "case_histories.csv")
    categories = pd.read_csv(BZA / "case_categories.csv")

    for name in selected:
        rule = RULES[name]
        if rule.load is not None:
            # Loads and keys its own frame, so align on parcel_id rather than
            # trusting two independent reads to come back in the same order.
            classified = rule.load()
            keyed = classified.set_index(
                classified["parcel_id"].astype("string")
            )
            index = raw["parcel_id"].astype("string")
            status = status_of(classified, rule)
            status.index = keyed.index
            features[f"st_{rule.key}"] = (
                index.map(status).fillna("outside").to_numpy()
            )
            measured = keyed[rule.measure_column]
            features[rule.measure_field] = (
                pd.to_numeric(index.map(measured), errors="coerce")
                .round()
                .astype("Int64")
                .to_numpy()
            )
        else:
            assert rule.classify is not None
            classified = rule.classify(raw)
            status = status_of(classified, rule)
            features[f"st_{rule.key}"] = status
            features[rule.measure_field] = (
                classified[rule.measure_column].round().astype("Int64")
            )
        cases = rule.select_cases(histories, categories)
        summaries[name] = summarize(classified, rule, cases, status)
        counts = features[f"st_{rule.key}"].value_counts().to_dict()
        print(f"  {name}: {counts}", flush=True)

    for name in quantities:
        quantity = QUANTITIES[name]
        classified = quantity.classify(raw)
        # "no recorded value / $0" is its own band, painted like the absent
        # state elsewhere: an unmeasured parcel is never shown as a low value.
        band = (
            classified["map_color"]
            .map(quantity.band_of_color)
            .fillna("none")
        )
        features[f"band_{quantity.key}"] = band
        features[quantity.measure_field] = (
            pd.to_numeric(classified[quantity.value_column], errors="coerce")
            .round()
            .astype("Int64")
        )
        summaries[name] = quantity.summarize(classified)
        print(f"  {name}: {band.value_counts().to_dict()}", flush=True)

    features = features.to_crs("EPSG:4326")

    roads = gpd.read_file(ROADS)
    roads = roads[roads["road_class"].isin(["major", "arterial"])]
    roads = roads[["road_class", "geometry"]].to_crs("EPSG:4326")
    print(f"  {len(roads):,} major/arterial road features", flush=True)

    work = Path(tempfile.mkdtemp(prefix="parcel-tiles-"))
    parcels_path = work / "parcels.geojsonl"
    roads_path = work / "roads.geojsonl"
    print("Writing intermediate GeoJSONSeq ...", flush=True)
    features.to_file(parcels_path, driver="GeoJSONSeq")
    roads.to_file(roads_path, driver="GeoJSONSeq")

    destination = OUT_DIR / args.output
    print(f"Tiling to {destination} ...", flush=True)
    run_tippecanoe(
        parcels_path,
        roads_path,
        destination,
        max_zoom=args.max_zoom,
        full_detail=args.full_detail,
        simplification=args.simplification,
        shared_borders=args.shared_borders,
    )

    if not args.skip_display:
        display = OUT_DIR / args.display_output
        print(f"Tiling overview tier to {display} ...", flush=True)
        run_tippecanoe(
            parcels_path,
            roads_path,
            display,
            # Same authoring flags as the full tier, only capped at z10. The
            # overview is the citywide first paint, so its parcel outlines have
            # to survive: it is what the frozen board captures.
            max_zoom=args.display_zoom,
            full_detail=args.full_detail,
            simplification=args.simplification,
            shared_borders=args.shared_borders,
            min_zoom=args.display_zoom,
        )

    (OUT_DIR / "parcel-rules.json").write_text(
        json.dumps(summaries, indent=2) + "\n", encoding="utf-8"
    )
    shutil.rmtree(work, ignore_errors=True)

    print(json.dumps(summaries, indent=2))
    print(f"\nRules: {', '.join(selected)}")
    for path in (destination, OUT_DIR / args.display_output):
        if path.exists():
            print(f"  {path.name:28} {path.stat().st_size / 1024 / 1024:6.1f} MB")


if __name__ == "__main__":
    main()
