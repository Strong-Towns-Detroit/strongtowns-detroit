#!/usr/bin/env python3
"""Match BZA case locations to Detroit parcels and build a repeat-site exhibit."""

from __future__ import annotations

import base64
import html
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from exhibit_brand import masthead_svg
ROOT = HERE.parents[2]
CASES = ROOT / "pipelines/zoning/bza_dataset_gemini/all_cases.csv"
PARCELS = ROOT / "pipelines/parcel-data/parcels_with_compliance.gpkg"
ROADS = ROOT / "projects/detroit-land-use-forum/spirit-plaza-accessibility/output/road_context.geojson"
OUT = HERE / "output"

NAVY, RED, GOLD, CREAM, MUTED = "#0c2340", "#c83a3a", "#ffb549", "#fffaf0", "#647184"


def clean_street(value: str) -> str:
    value = value.upper().replace(".", " ")
    value = re.sub(r"\b(AVENUE|AVE|STREET|ST|ROAD|RD|BOULEVARD|BLVD|DRIVE|DR)\b", "", value)
    value = re.sub(r"\bEIGHTH\b", "EIGHT", value)
    return re.sub(r"[^A-Z0-9]+", " ", value).strip()


def address_keys(location: str) -> list[tuple[int, str]]:
    """Return each explicit house number paired with the location's first street."""
    lead = re.split(r"\b(?:BETWEEN|LOCATED|IN\s+AN?|CITY COUNCIL|COUNCIL DISTRICT)\b", location, 1, flags=re.I)[0]
    lead = re.sub(r"\([^)]*\)", " ", lead)
    match = re.search(r"\b(\d{1,6}(?:\s*(?:,|&|AND|-)\s*\d{1,6})*)\s+(.+)", lead, re.I)
    if not match:
        return []
    numbers = [int(x) for x in re.findall(r"\d{1,6}", match.group(1))]
    street = clean_street(match.group(2))
    return [(number, street) for number in numbers if street]


def load_matches() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    cases = pd.read_csv(CASES).query("record_type == 'minutes_case'").copy()
    cases["meeting_date"] = pd.to_datetime(cases["meeting_date"])
    rows = []
    for row in cases.itertuples():
        for number, street in address_keys(str(row.location)):
            rows.append({
                "occurrence_id": row.occurrence_id, "meeting_date": row.meeting_date,
                "case_number": row.case_number, "location": row.location,
                "number": number, "street": street,
            })
    addresses = pd.DataFrame(rows)
    parcels = gpd.read_file(
        PARCELS, columns=["parcel_id", "address", "street_number", "street_prefix", "street_name", "geometry"]
    )
    parcels = parcels[parcels.street_number.notna()].copy()
    parcels["number"] = parcels.street_number.astype(int)
    parcels["street"] = (
        parcels.street_prefix.fillna("").astype(str) + " " + parcels.street_name.fillna("").astype(str)
    ).map(clean_street)
    parcels["street_nodir"] = parcels["street"].str.replace(r"^(?:N|S|E|W)\s+", "", regex=True)
    addresses["street_nodir"] = addresses["street"].str.replace(r"^(?:N|S|E|W)\s+", "", regex=True)
    # One representative geometry per assessor address.
    lookup = parcels.sort_values("parcel_id").drop_duplicates(["number", "street"])
    matched = addresses.merge(
        lookup[["number", "street", "parcel_id", "address", "geometry"]],
        on=["number", "street"], how="left",
    )
    # Minutes regularly omit the directional prefix. Only fall back when a
    # house-number/street pair resolves to one assessor address.
    fallback = (
        parcels.sort_values("parcel_id")
        .drop_duplicates(["number", "street_nodir"], keep=False)
        [["number", "street_nodir", "parcel_id", "address", "geometry"]]
    )
    missing = matched["geometry"].isna()
    rescued = matched.loc[missing, ["number", "street_nodir"]].merge(
        fallback, on=["number", "street_nodir"], how="left"
    )
    for column in ["parcel_id", "address", "geometry"]:
        matched.loc[missing, column] = rescued[column].to_numpy()
    points = gpd.GeoDataFrame(matched[matched.geometry.notna()], geometry="geometry", crs=parcels.crs)
    points["geometry"] = points.geometry.centroid
    return points, matched


def summarize(points: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    grouped = points.groupby(["number", "street"], as_index=False).agg(
        address=("address", "first"),
        appearances=("meeting_date", "nunique"),
        first_seen=("meeting_date", "min"),
        last_seen=("meeting_date", "max"),
        case_numbers=("case_number", lambda x: ", ".join(sorted(set(map(str, x))))),
        case_count=("case_number", "nunique"),
        geometry=("geometry", "first"),
    )
    return gpd.GeoDataFrame(grouped, geometry="geometry", crs=points.crs)


def map_image(sites: gpd.GeoDataFrame) -> str:
    parcels = gpd.read_file(PARCELS, columns=["geometry"])
    city = unary_union(parcels.geometry)
    fig, ax = plt.subplots(figsize=(10.3, 7.2), dpi=190)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    gpd.GeoSeries([city], crs=parcels.crs).plot(ax=ax, color="#ebe5da", edgecolor=NAVY, linewidth=.6)
    if ROADS.exists():
        roads = gpd.read_file(ROADS).to_crs(parcels.crs)
        roads.plot(ax=ax, color=NAVY, linewidth=.18, alpha=.25)
    singles = sites[sites.appearances == 1]
    repeats = sites[sites.appearances > 1]
    singles.plot(ax=ax, color=NAVY, markersize=7, alpha=.42, linewidth=0)
    repeats.plot(
        ax=ax, color=GOLD, edgecolor=NAVY,
        markersize=22 + repeats.appearances.pow(1.7) * 9, linewidth=.65, alpha=.94,
    )
    ax.set_axis_off()
    ax.margins(.01)
    fig.tight_layout(pad=0)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, facecolor=CREAM)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def build_svg(sites: gpd.GeoDataFrame, matched: pd.DataFrame) -> str:
    repeated = sites[sites.appearances > 1].sort_values(
        ["appearances", "case_count", "address"], ascending=[False, False, True]
    )
    top = repeated.head(10)
    rows = []
    for i, row in enumerate(top.itertuples()):
        y = 445 + i * 53
        years = str(row.first_seen.year) if row.first_seen.year == row.last_seen.year else f"{row.first_seen.year}–{row.last_seen.year}"
        rows.append(
            f'<text class="rank" x="1110" y="{y}">{i+1:02}</text>'
            f'<text class="site" x="1160" y="{y}">{html.escape(str(row.address).title())}</text>'
            f'<text class="detail" x="1160" y="{y+21}">{row.appearances} appearances · {row.case_count} case no. · {years}</text>'
        )
    image = map_image(sites)
    source_occurrences = matched.occurrence_id.nunique()
    geocoded_occurrences = matched.loc[matched.geometry.notna(), "occurrence_id"].nunique()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100" role="img">
<style>
.paper{{fill:{CREAM}}}.kicker,.metric-label,.note,.legend,.source,.rank,.detail{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.site{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}.title{{font-size:61px;font-weight:700}}
.dek{{font-size:24px;fill:#48596d}}.metric{{font-size:66px;font-weight:700}}.metric-label{{font-size:14px;font-weight:700;letter-spacing:1.1px;fill:{MUTED}}}
.note{{font-size:17px;fill:#34475d}}.legend{{font-size:15px;fill:{NAVY}}}.source{{font-size:13px;fill:{MUTED}}}
.rank{{font-size:14px;font-weight:700;fill:{RED}}}.site{{font-size:20px;font-weight:700}}.detail{{font-size:13px;fill:{MUTED}}}
</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
<text class="title" x="52" y="116">{len(repeated)} sites appeared before the BZA more than once</text>
<text class="dek" x="55" y="158">Each point is one located site; larger gold circles mark appearances on more meeting dates</text>
<image href="data:image/png;base64,{image}" x="48" y="205" width="1010" height="735" preserveAspectRatio="xMidYMid meet"/>
<circle cx="70" cy="965" r="4" fill="{NAVY}" opacity=".5"/><text class="legend" x="86" y="971">One appearance</text>
<circle cx="235" cy="965" r="10" fill="{GOLD}" stroke="{NAVY}"/><text class="legend" x="255" y="971">Repeat site</text>
<text class="metric" x="1110" y="267">{len(repeated)}</text>
<text class="metric-label" x="1113" y="297">LOCATED SITES WITH REPEAT APPEARANCES</text>
<text class="note" x="1113" y="331">Among {len(sites):,} located physical sites</text>
<text class="note" x="1113" y="356">{geocoded_occurrences} of {source_occurrences} address-bearing appearances located</text>
<text class="metric-label" x="1110" y="405">MOST FREQUENTLY APPEARING SITES</text>
{''.join(rows)}
<text class="source" x="55" y="1048">“Appearance” means a distinct meeting date, not necessarily a new application; postponements and rehearings can produce repeat appearances.</text>
<text class="source" x="55" y="1072">Source: Detroit BZA minutes and agendas, 2019–2026; locations linked to City of Detroit assessor parcel addresses.</text>
</svg>"""


def run() -> None:
    points, matched = load_matches()
    sites = summarize(points)
    OUT.mkdir(parents=True, exist_ok=True)
    matched.drop(columns="geometry").to_csv(OUT / "address_match_audit.csv", index=False)
    sites.drop(columns="geometry").to_csv(OUT / "repeat_sites.csv", index=False)
    svg = build_svg(sites, matched)
    svg_path = OUT / "bza-repeat-sites.svg"
    svg_path.write_text(svg)
    (OUT / "bza-repeat-sites.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>BZA repeat sites</title>'
        '<style>html,body{margin:0;background:#fffaf0}svg{display:block;width:100%;height:auto}</style>' + svg
    )
    renderer = shutil.which("rsvg-convert")
    if renderer:
        subprocess.run([renderer, "--width", "3200", "--output", str(OUT / "bza-repeat-sites.png"), str(svg_path)], check=True)
    repeated = sites[sites.appearances > 1].sort_values("appearances", ascending=False)
    print(f"Mapped {matched.loc[matched.geometry.notna(), 'occurrence_id'].nunique()} / {matched.occurrence_id.nunique()} address-bearing occurrences")
    print(f"{len(repeated)} repeat sites among {len(sites)} matched sites")
    print(repeated[["address", "appearances", "case_count", "first_seen", "last_seen"]].head(15).to_string(index=False))


if __name__ == "__main__":
    run()
