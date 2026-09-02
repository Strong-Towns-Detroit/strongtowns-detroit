#!/usr/bin/env python3
"""Build the single- and two-family principal-building setback exhibit."""

from __future__ import annotations

import base64
import gc
import html
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exhibit_brand import masthead_svg
from exhibit_components import (
    LegendItem,
    forum_css,
    map_frame,
    metric_block,
    source_lines,
    swatch_legend,
    title_block,
    write_svg_bundle,
)
from parcel_exhibit_components import bza_case_stat
from strongtowns_graphics import (
    CONFERENCE_LANDSCAPE,
    Graphic,
    SvgComponent,
    render_graphic_svg,
    write_graphic_bundle,
)

from build_minimum_lot_size_asset import (
    BZA,
    CREAM,
    LIGHT_BLUE,
    MUTED,
    NAVY,
    OUT,
    OUTSIDE,
    PARCELS,
    RED,
    relief_histogram,
)
from lot_coverage_model import coverage_building_type
from setback_envelope_model import (
    principal_footprint_outside_area,
    single_family_setback_envelope,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GEOMETRY_ROOT = (
    ROOT / "projects/detroit-land-use-forum/base-units-geometry"
)
FRONTAGES = GEOMETRY_ROOT / "output/geometry_frontage_sample.gpkg"
BUILDINGS = GEOMETRY_ROOT / "data/base_units_buildings.geojson"
PRINCIPAL_SITE_AUDIT = (
    GEOMETRY_ROOT / "output/principal_building_site_audit.csv"
)
MERGED_RESULTS = OUT / "single-family-setback-results.csv"
TWO_FAMILY_RESULTS = OUT / "two-family-setback-results.csv"
ROADS = (
    ROOT
    / "projects/detroit-land-use-forum/spirit-plaza-accessibility"
    / "output/road_context.geojson"
)


def normalize_parcel_id(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    cleaned = re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()
    return cleaned or None


def load_and_classify(
    max_eligible: int | None = None,
    eligible_offset: int = 0,
    building_types: tuple[str, ...] = ("single_family",),
) -> gpd.GeoDataFrame:
    parcels = gpd.read_file(
        PARCELS,
        columns=[
            "parcel_id",
            "zoning_district",
            "use_code_description",
            "geometry",
        ],
    )
    parcels["parcel_key"] = parcels["parcel_id"].map(normalize_parcel_id)
    parcels["building_type"] = [
        coverage_building_type(district, use)
        for district, use in zip(
            parcels["zoning_district"], parcels["use_code_description"]
        )
    ]
    parcels["in_scope"] = parcels["building_type"].isin(building_types)

    candidate_rows = pd.read_csv(
        PRINCIPAL_SITE_AUDIT, dtype={"parcel_key": "string"}
    )
    candidate_keys = set(
        candidate_rows.loc[
            candidate_rows["principal_site_ambiguous"],
            "parcel_key",
        ].dropna()
    )
    parcels["candidate_multi_parcel_site"] = parcels["parcel_key"].isin(
        candidate_keys
    )
    eligible_keys = set(
        parcels.loc[
            parcels["in_scope"]
            & ~parcels["candidate_multi_parcel_site"],
            "parcel_key",
        ].dropna()
    )
    if max_eligible is not None:
        ordered_keys = sorted(eligible_keys)
        eligible_keys = set(
            ordered_keys[eligible_offset:eligible_offset + max_eligible]
        )
    parcels = parcels.to_crs(2898)

    frontages = gpd.read_file(FRONTAGES).to_crs(2898)
    frontages = frontages[
        frontages["parcel_key"].isin(eligible_keys)
        & frontages["frontage_confidence"].isin(["high", "medium"])
    ].drop_duplicates("parcel_key")
    front_edge = frontages.set_index("parcel_key").geometry.to_dict()
    front_confidence = frontages.set_index(
        "parcel_key"
    )["frontage_confidence"].to_dict()
    del frontages

    buildings = gpd.read_file(BUILDINGS)
    if "status" in buildings:
        buildings = buildings[
            buildings["status"].fillna("").str.lower().isin(
                {"active", "current"}
            )
        ].copy()
    buildings["parcel_key"] = buildings["parcel_id"].map(
        normalize_parcel_id
    )
    buildings = buildings[
        buildings["parcel_key"].isin(eligible_keys)
    ].to_crs(2898)
    buildings["footprint_area"] = buildings.geometry.area
    principal = (
        buildings.dropna(subset=["parcel_key", "geometry"])
        .sort_values("footprint_area", ascending=False)
        .drop_duplicates("parcel_key")
        .set_index("parcel_key")
    )
    principal_geometry = principal.geometry.to_dict()
    del principal
    del buildings
    gc.collect()

    evaluated = []
    crosses = []
    envelope_area = []
    outside_area = []
    reasons = []
    for row in parcels.itertuples():
        if not row.in_scope:
            evaluated.append(False)
            crosses.append(False)
            envelope_area.append(None)
            outside_area.append(None)
            reasons.append("other_building_type")
            continue
        if row.candidate_multi_parcel_site:
            evaluated.append(False)
            crosses.append(False)
            envelope_area.append(None)
            outside_area.append(None)
            reasons.append("possible_multi_parcel_site")
            continue
        if max_eligible is not None and row.parcel_key not in eligible_keys:
            evaluated.append(False)
            crosses.append(False)
            envelope_area.append(None)
            outside_area.append(None)
            reasons.append("outside_debug_sample")
            continue
        edge = front_edge.get(row.parcel_key)
        building = principal_geometry.get(row.parcel_key)
        if edge is None:
            evaluated.append(False)
            crosses.append(False)
            envelope_area.append(None)
            outside_area.append(None)
            reasons.append("no_confident_front_edge")
            continue
        if building is None or building.is_empty:
            evaluated.append(False)
            crosses.append(False)
            envelope_area.append(None)
            outside_area.append(None)
            reasons.append("no_principal_footprint")
            continue
        envelope = single_family_setback_envelope(row.geometry, edge)
        if envelope is None:
            evaluated.append(False)
            crosses.append(False)
            envelope_area.append(None)
            outside_area.append(None)
            reasons.append("irregular_geometry")
            continue
        available = max(
            envelope.option_left_4.area,
            envelope.option_right_4.area,
        )
        outside = principal_footprint_outside_area(building, envelope)
        tolerance = max(10.0, building.area * 0.01)
        evaluated.append(True)
        crosses.append(outside > tolerance)
        envelope_area.append(available)
        outside_area.append(outside)
        reasons.append("evaluated")

    parcels["evaluated"] = evaluated
    parcels["crosses_envelope"] = crosses
    parcels["setback_envelope_area_sqft"] = envelope_area
    parcels["principal_outside_envelope_sqft"] = outside_area
    parcels["evaluation_reason"] = reasons
    parcels["frontage_confidence"] = parcels["parcel_key"].map(
        front_confidence
    )
    return parcels


def load_merged_classification() -> gpd.GeoDataFrame:
    parcels = gpd.read_file(
        PARCELS,
        columns=[
            "parcel_id",
            "zoning_district",
            "use_code_description",
            "geometry",
        ],
    )
    parcels["parcel_key"] = parcels["parcel_id"].map(normalize_parcel_id)
    parcels["building_type"] = [
        coverage_building_type(district, use)
        for district, use in zip(
            parcels["zoning_district"], parcels["use_code_description"]
        )
    ]
    parcels["in_scope"] = parcels["building_type"].isin(
        ["single_family", "two_family"]
    )
    candidate_rows = pd.read_csv(
        PRINCIPAL_SITE_AUDIT, dtype={"parcel_key": "string"}
    )
    candidate_keys = set(
        candidate_rows.loc[
            candidate_rows["principal_site_ambiguous"],
            "parcel_key",
        ].dropna()
    )
    parcels["candidate_multi_parcel_site"] = parcels["parcel_key"].isin(
        candidate_keys
    )
    result_files = [MERGED_RESULTS]
    if TWO_FAMILY_RESULTS.exists():
        result_files.append(TWO_FAMILY_RESULTS)
    results = pd.concat(
        [
            pd.read_csv(path, dtype={"parcel_key": "string"})
            for path in result_files
        ],
        ignore_index=True,
    ).drop_duplicates("parcel_key", keep="last")
    parcels = parcels.merge(
        results,
        on="parcel_key",
        how="left",
        validate="one_to_one",
    )
    parcels["evaluated"] = parcels["evaluated"].fillna(False).astype(bool)
    parcels["crosses_envelope"] = (
        parcels["crosses_envelope"].fillna(False).astype(bool)
    )
    parcels.loc[
        parcels["in_scope"]
        & parcels["candidate_multi_parcel_site"],
        "evaluation_reason",
    ] = "possible_multi_parcel_site"
    parcels.loc[
        ~parcels["in_scope"], "evaluation_reason"
    ] = "other_building_type"
    return gpd.GeoDataFrame(parcels, geometry="geometry", crs=parcels.crs)


def select_house_setback_cases(
    histories: pd.DataFrame,
    categories: pd.DataFrame,
) -> pd.DataFrame:
    cases = categories[categories["category"].eq("setbacks_yards")].merge(
        histories, on="case_history_id", how="inner", validate="one_to_one"
    )
    proposal = cases["proposal"].fillna("")
    single_family = proposal.str.contains(
        r"single[- ]family dwelling|single[- ]family residential|"
        r"existing single family|single-family zoning lot",
        case=False,
        regex=True,
    )
    two_family = proposal.str.contains(
        r"(?:two|2)[- ]family dwellings?|\bduplex(?:es)?\b|"
        r"twenty \(20\) dwelling units in ten \(10\) two-story buildings",
        case=False,
        regex=True,
    )
    exclude = proposal.str.contains(
        r"restaurant|townhouse|multiple[- ]family|neighborhood center|"
        r"parking lot",
        case=False,
        regex=True,
    )
    accessory_only = proposal.str[:320].str.contains(
        r"(?:construct|legalize|relocate)[^.;]{0,180}"
        r"(?:\bgarage\b|\bcarport\b)",
        case=False,
        regex=True,
    )
    return cases[
        (single_family | two_family)
        & ~exclude
        & ~(accessory_only & ~two_family)
    ].copy()


def map_image(frame: gpd.GeoDataFrame, roads_path: Path = ROADS) -> str:
    other = frame[~frame["in_scope"]]
    unknown = frame[frame["in_scope"] & ~frame["evaluated"]]
    within = frame[frame["evaluated"] & ~frame["crosses_envelope"]]
    crosses = frame[frame["crosses_envelope"]]
    fig, ax = plt.subplots(figsize=(10.8, 7.0), dpi=435)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    other.plot(ax=ax, color=OUTSIDE, edgecolor="none")
    unknown.plot(ax=ax, color=OUTSIDE, edgecolor="none")
    within.plot(ax=ax, color=NAVY, edgecolor="none")
    crosses.plot(ax=ax, color=RED, edgecolor="none")
    roads = gpd.read_file(roads_path).to_crs(frame.crs)
    if "road_class" in roads:
        roads = roads[roads["road_class"].isin(["major", "arterial"])]
    roads.plot(
        ax=ax, color=NAVY, linewidth=0.22, alpha=0.36
    )
    ax.set_axis_off()
    ax.margins(0)
    fig.tight_layout(pad=0)
    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format="jpeg",
        bbox_inches="tight",
        pad_inches=0,
        facecolor=CREAM,
        pil_kwargs={"quality": 90, "optimize": True},
    )
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def histogram_svg(
    categories: pd.DataFrame,
    cases: pd.DataFrame,
) -> str:
    rows = relief_histogram(categories, cases)
    maximum = max(count for _, count, _ in rows)
    result = []
    for index, (label, count, selected) in enumerate(rows):
        if selected:
            label = "Single-family setbacks"
        y = 605 + index * 45
        width = max(3, round(245 * count / maximum))
        color = RED if selected else LIGHT_BLUE
        weight = 700 if selected else 400
        result.append(
            f'<text class="bar-label" x="1120" y="{y}" '
            f'font-weight="{weight}">{html.escape(label)}</text>'
            f'<rect x="1120" y="{y + 9}" width="{width}" height="11" '
            f'fill="{color}"/>'
            f'<text class="bar-value" x="{1128 + width}" y="{y + 20}" '
            f'font-weight="{weight}">{count}</text>'
        )
    return "".join(result)


def build_graphic(
    frame: gpd.GeoDataFrame,
    cases: pd.DataFrame,
    categories: pd.DataFrame,
    *,
    roads_path: Path = ROADS,
    title: str = "Detroit’s single- and two-family setback envelope",
    subtitle: str = (
        "Existing homes compared with Detroit’s required front, rear, and side yards"
    ),
    sources: tuple[str, ...] | None = None,
    description: str | None = None,
) -> Graphic:
    evaluated = frame[frame["evaluated"]]
    crossing = evaluated[evaluated["crosses_envelope"]]
    total, affected = len(evaluated), len(crossing)
    share = affected / total
    within = total - affected
    unknown = int((frame["in_scope"] & ~frame["evaluated"]).sum())
    other = int((~frame["in_scope"]).sum())
    candidate = int(
        (frame["in_scope"] & frame["candidate_multi_parcel_site"]).sum()
    )
    image = map_image(frame, roads_path)
    visual = f"""
<style>{forum_css(title_size=45,
extra_sans=(".bar-label", ".bar-value"),
extra_serif=(".bza-metric",),
extra_rules=f".bza-metric{{font-size:28px;font-weight:700}}"
f".bar-label,.bar-value{{font-size:13px;fill:{NAVY}}}",
muted=MUTED)}</style>
{map_frame(f"data:image/jpeg;base64,{image}")}
{swatch_legend([
LegendItem("Crosses ordinary envelope", RED),
LegendItem("Within ordinary envelope", NAVY),
LegendItem("Not evaluated / other parcel type", OUTSIDE),
], positions=(67, 325, 570))}
{metric_block(f"{share:.0%}", [
"OF PRINCIPAL BUILDING FOOTPRINTS VIOLATE",
"ONE OR MORE SETBACK RULES",
], f"{affected:,} of {total:,} evaluated properties")}
<text class="note" x="1120" y="399">Existing homes may remain as lawful</text>
<text class="note" x="1120" y="424">nonconformities; additions or replacement</text>
<text class="note" x="1120" y="449">construction can require setback relief.</text>
<text class="note" x="1120" y="474">Accessory buildings follow different rules.</text>
{bza_case_stat(
    len(cases), "setback", "single- and two-family setback", y=530
)}
"""
    return Graphic(
        title=title,
        subtitle=subtitle,
        visual=SvgComponent(visual, 1600, 780, min_y=180),
        sources=sources if sources is not None else (
            f"Ordinary rectangular lots only; {candidate:,} sites without one "
            "clear principal building are not evaluated. Front edges use City "
            "Base Units street links.",
            "Crossing requires more than 10 sq. ft. or 1% of the footprint "
            "outside both permissible side-yard allocations. Result: "
            f"{affected:,} cross · {within:,} within · {unknown:,} not "
            f"evaluated · {other:,} other type.",
        ),
        description=description if description is not None else (
            f"{affected:,} of {total:,} evaluated single- and two-family "
            "principal building footprints extend outside the ordinary current "
            "setback envelope."
        ),
    )


def build_svg(
    frame: gpd.GeoDataFrame,
    cases: pd.DataFrame,
    categories: pd.DataFrame,
) -> str:
    return render_graphic_svg(build_graphic(frame, cases, categories))


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if MERGED_RESULTS.exists() and not TWO_FAMILY_RESULTS.exists():
        duplex = load_and_classify(building_types=("two_family",))
        columns = [
            "parcel_key",
            "evaluated",
            "crosses_envelope",
            "setback_envelope_area_sqft",
            "principal_outside_envelope_sqft",
            "evaluation_reason",
            "frontage_confidence",
        ]
        duplex.loc[duplex["in_scope"], columns].to_csv(
            TWO_FAMILY_RESULTS, index=False
        )
    frame = (
        load_merged_classification()
        if MERGED_RESULTS.exists()
        else load_and_classify(
            building_types=("single_family", "two_family")
        )
    )
    histories = pd.read_csv(BZA / "case_histories.csv")
    categories = pd.read_csv(BZA / "case_categories.csv")
    cases = select_house_setback_cases(histories, categories)
    stem = "detroit-residential-setback-envelope"
    write_graphic_bundle(
        OUT, stem, build_graphic(frame, cases, categories),
        aspect_ratio=CONFERENCE_LANDSCAPE, png_width=3200,
    )
    cases.to_csv(OUT / f"{stem}-bza-cases.csv", index=False)
    result_columns = [
        "parcel_id",
        "evaluation_reason",
        "frontage_confidence",
        "setback_envelope_area_sqft",
        "principal_outside_envelope_sqft",
        "crosses_envelope",
    ]
    frame[frame["in_scope"]][result_columns].to_csv(
        OUT / f"{stem}-parcel-results.csv", index=False
    )
    evaluated = frame[frame["evaluated"]]
    summary = {
        "evaluated_properties": int(len(evaluated)),
        "principal_footprint_crosses": int(
            evaluated["crosses_envelope"].sum()
        ),
        "crossing_share": float(
            evaluated["crosses_envelope"].mean()
        ),
        "not_evaluated": int(
            (frame["in_scope"] & ~frame["evaluated"]).sum()
        ),
        "ambiguous_principal_building_sites_excluded": int(
            (
                frame["in_scope"]
                & frame["candidate_multi_parcel_site"]
            ).sum()
        ),
        "bza_case_histories": int(len(cases)),
        "granted_or_reversed": int(
            cases["final_outcome"].eq("granted_reversed").sum()
        ),
    }
    (OUT / f"{stem}-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
