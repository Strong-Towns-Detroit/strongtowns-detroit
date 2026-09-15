#!/usr/bin/env python3
"""Build an auditable required-versus-proposed parking exhibit from BZA minutes."""

from __future__ import annotations

from strongtowns_detroit.bza import data_directory as bza_data_directory

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from strongtowns_detroit.repositories import data_repository

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))
from exhibit_brand import masthead_svg

DATA = bza_data_directory()
OUT = HERE / "output"

CREAM = "#fffaf0"
NAVY = "#082647"
RED = "#c8102e"
GOLD = "#ffb547"
BLUE = "#4e92ce"
MUTED = "#526477"
PALE = "#e9e1d3"

# Values are transcribed from the representative proposal text in
# case_histories.csv. A row is included only when both the applicable number
# required and the number proposed/provided are explicit. Notes document cases
# where the minutes state more than one preliminary requirement.
PARKING_VALUES: dict[str, tuple[int, int, str]] = {
    "bza-14-19-184cee7e49": (51, 0, ""),
    "bza-38-19-f657c9531f": (19, 7, ""),
    "bza-40-19-aae5d99948": (35, 0, ""),
    "bza-67-18-3e522c88c3": (24, 2, ""),
    "bza-78-19-9477858622": (25, 0, ""),
    "bza-88-19-07e1969543": (36, 5, ""),
    "bza-110-19-6035ce5f01": (191, 47, ""),
    "bza-112-19-8bdcb1c11b": (143, 100, ""),
    "bza-111-19-7252fe4512": (29, 0, ""),
    "bza-34-20-ee36e5ccb2": (50, 26, ""),
    "bza-38-20-ee1ac31af4": (
        40, 34, "27 residential plus 13 commercial spaces required"
    ),
    "bza-29-20-787a86c963": (10, 9, ""),
    "bza-06-21-e118eb8f66": (12, 7, "Building 2 figures stated in minutes"),
    "bza-31-21-ace9be1d9d": (77, 40, ""),
    "bza-41-21-988b579aea": (18, 14, ""),
    "bza-11-22-50abfc40df": (8, 3, ""),
    "bza-50-22-e2dd6e5b59": (41, 26, ""),
    "bza-58-22-943196124c": (51, 36, ""),
    "bza-53-22-f89cd6be57": (
        77, 0, "103 base spaces reduced to 77 near high-frequency transit"
    ),
    "bza-19-23-ed15514286": (15, 0, ""),
    "bza-24-24-ba03fb1f1d": (32, 25, ""),
    "bza-25-24-e30fbc8699": (33, 7, ""),
    "bza-29-24-6d70f0b779": (429, 208, ""),
    "bza-31-24-5f6ef1ba25": (120, 20, ""),
    "bza-32-24-9d20f69e4b": (22, 0, ""),
    "bza-35-24-7b8306b2c9": (8, 0, ""),
    "bza-40-24-8e2b4f04b1": (16, 7, ""),
    "bza-58-24-6532bebb8a": (38, 0, ""),
    "bza-60-24-fc667bdd68": (22, 17, ""),
    "bza-66-24-27cac6bb0f": (9, 0, ""),
    "bza-84-24-6f5548ffcb": (8, 0, ""),
    "bza-7-25-6f5b94d140": (3, 0, ""),
    "bza-15-25-aa055fbabb": (
        3, 2, "Employee-based requirement used; square-foot schedule stated 5"
    ),
    "bza-27-25-b460cdbf7e": (27, 12, ""),
    "bza-bza2025-00044-8af9060833": (19, 12, ""),
}


def parking_cases() -> pd.DataFrame:
    histories = pd.read_csv(DATA / "case_histories.csv", dtype=str).fillna("")
    categories = pd.read_csv(DATA / "case_categories.csv", dtype=str)
    ids = set(
        categories.loc[
            categories["category"].eq("parking_supply"), "case_history_id"
        ]
    )
    cases = histories[histories["case_history_id"].isin(ids)].copy()
    cases["required_spaces"] = cases["case_history_id"].map(
        lambda key: PARKING_VALUES.get(key, (None, None, ""))[0]
    )
    cases["proposed_spaces"] = cases["case_history_id"].map(
        lambda key: PARKING_VALUES.get(key, (None, None, ""))[1]
    )
    cases["transcription_note"] = cases["case_history_id"].map(
        lambda key: PARKING_VALUES.get(key, (None, None, ""))[2]
    )
    cases["numeric_status"] = cases["required_spaces"].notna().map(
        {True: "explicit_pair", False: "not_stated"}
    )
    cases["shortfall_spaces"] = (
        cases["required_spaces"] - cases["proposed_spaces"]
    )
    cases["shortfall_share"] = (
        cases["shortfall_spaces"] / cases["required_spaces"]
    )
    return cases.sort_values(["first_meeting_date", "case_history_id"])


def location_label(value: str) -> str:
    text = value.split(" between ")[0].split(" Between:")[0]
    text = text.split(", between ")[0].strip(" ,.")
    return text[:34]


def outcome_counts(cases: pd.DataFrame) -> tuple[int, int, int]:
    grants = int(cases["final_outcome"].eq("granted_reversed").sum())
    denials = int(cases["final_outcome"].eq("denied_upheld").sum())
    return grants, denials, len(cases) - grants - denials


def shortfall_histogram(frame: pd.DataFrame) -> list[tuple[str, int]]:
    bins = [-0.001, 0.2, 0.4, 0.6, 0.8, 1.001]
    labels = ["0–20%", "21–40%", "41–60%", "61–80%", "81–100%"]
    groups = pd.cut(frame["shortfall_share"], bins=bins, labels=labels)
    counts = groups.value_counts(sort=False)
    return [(label, int(counts.get(label, 0))) for label in labels]


def build_svg(cases: pd.DataFrame) -> str:
    numeric = cases[cases["numeric_status"].eq("explicit_pair")].copy()
    required = int(numeric["required_spaces"].sum())
    proposed = int(numeric["proposed_spaces"].sum())
    shortfall = required - proposed
    multiple = required / proposed
    median_shortfall = numeric["shortfall_share"].median()
    zero = int(numeric["proposed_spaces"].eq(0).sum())
    grants, denials, other = outcome_counts(cases)

    aggregate_width = 590
    proposed_width = aggregate_width * proposed / required
    histogram = shortfall_histogram(numeric)
    max_hist = max(count for _, count in histogram)
    hist_rows = []
    for index, (label, count) in enumerate(histogram):
        y = 685 + index * 54
        width = 330 * count / max_hist
        hist_rows.append(
            f'<text class="axis" x="62" y="{y + 20}">{label}</text>'
            f'<rect x="145" y="{y}" width="{width:.1f}" height="28" '
            f'rx="3" fill="{BLUE}"/>'
            f'<text class="bar-value" x="{155 + width:.1f}" y="{y + 20}">'
            f"{count}</text>"
        )

    top = numeric.nlargest(6, "shortfall_spaces")
    top_rows = []
    max_required = int(top["required_spaces"].max())
    for index, (_, row) in enumerate(top.iterrows()):
        y = 690 + index * 55
        width = 310 * row.required_spaces / max_required
        proposed_part = width * row.proposed_spaces / row.required_spaces
        label = html.escape(location_label(row.location))
        top_rows.append(
            f'<text class="case-label" x="720" y="{y + 18}">{label}</text>'
            f'<rect x="1010" y="{y}" width="{width:.1f}" height="25" '
            f'rx="3" fill="{RED}"/>'
            f'<rect x="1010" y="{y}" width="{proposed_part:.1f}" height="25" '
            f'rx="3" fill="{NAVY}"/>'
            f'<text class="case-value" x="1528" y="{y + 19}" text-anchor="end">'
            f"{int(row.required_spaces)} required · "
            f"{int(row.proposed_spaces)} proposed</text>"
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">Detroit asks projects to build more parking than they propose</title>
<desc id="desc">Across 35 Detroit Board of Zoning Appeals parking cases that state both figures, 1,741 spaces were required and 666 were proposed or provided.</desc>
<style>
.paper{{fill:{CREAM}}}
.kicker,.metric-label,.note,.source,.axis,.bar-value,.case-label,.case-value,.legend{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:58px;font-weight:700}}.dek{{font-size:24px;fill:#48596d}}
.metric{{font-size:78px;font-weight:700}}.metric-label{{font-size:15px;font-weight:700;letter-spacing:1.3px;fill:{MUTED}}}
.section-title{{font-size:28px;font-weight:700}}.note{{font-size:18px;fill:#34475d}}
.source{{font-size:13px;fill:{MUTED}}}.axis{{font-size:16px;fill:{NAVY}}}
.bar-value{{font-size:16px;font-weight:700;fill:{NAVY}}}
.case-label{{font-size:15px;fill:{NAVY}}}.case-value{{font-size:14px;font-weight:700;fill:{NAVY}}}
.legend{{font-size:14px;fill:{NAVY}}}
</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
<text class="title" x="52" y="120">Detroit required 2.6× the parking</text>
<text class="title" x="52" y="184">that applicants proposed</text>
<text class="dek" x="55" y="231">BZA parking requests with explicit required and proposed counts, 2019–2026</text>

<text class="metric" x="60" y="365">{required:,}</text>
<text class="metric-label" x="65" y="398">SPACES REQUIRED</text>
<text class="metric" x="390" y="365">{proposed:,}</text>
<text class="metric-label" x="395" y="398">PROPOSED OR PROVIDED</text>
<text class="metric" x="755" y="365">{shortfall:,}</text>
<text class="metric-label" x="760" y="398">SPACES IN THE REQUESTED GAP</text>
<text class="metric" x="1170" y="365">{median_shortfall:.0%}</text>
<text class="metric-label" x="1175" y="398">MEDIAN CASE SHORTFALL</text>

<rect x="62" y="449" width="{aggregate_width}" height="45" rx="4" fill="{RED}"/>
<rect x="62" y="449" width="{proposed_width:.1f}" height="45" rx="4" fill="{NAVY}"/>
<text class="legend" x="62" y="524">■ <tspan fill="{NAVY}">Proposed or provided</tspan></text>
<text class="legend" x="240" y="524">■ <tspan fill="{RED}">Additional spaces required</tspan></text>
<text class="note" x="755" y="462">{zero} of the {len(numeric)} applications proposed no on-site parking.</text>
<text class="note" x="755" y="495">Across all 62 parking cases: {grants} granted · {denials} denied · {other} other outcomes.</text>
<text class="source" x="755" y="525">Outcomes include parking cases whose minutes omit a required or proposed count.</text>

<line x1="55" y1="576" x2="1545" y2="576" stroke="{PALE}" stroke-width="2"/>
<text class="section-title" x="55" y="631">How large was the gap?</text>
<text class="source" x="58" y="655">Cases by spaces missing as a share of the stated requirement</text>
{''.join(hist_rows)}

<text class="section-title" x="715" y="631">The six largest requested gaps</text>
<rect x="1010" y="646" width="14" height="14" fill="{NAVY}"/>
<text class="legend" x="1031" y="658">Proposed</text>
<rect x="1120" y="646" width="14" height="14" fill="{RED}"/>
<text class="legend" x="1141" y="658">Required beyond proposal</text>
{''.join(top_rows)}

<text class="source" x="55" y="1037">Unit: one distinct BZA case. The numerical comparison includes only cases that state both the requirement and the proposed or provided count.</text>
<text class="source" x="55" y="1063">“Required” reports the operative figure stated in the minutes after any stated transit, employee, or use adjustment. Source: Detroit BZA minutes, March 2019–February 2026.</text>
</svg>"""


def write_assets(cases: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = build_svg(cases)
    stem = "detroit-parking-requirements"
    svg_path = OUT / f"{stem}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    (OUT / f"{stem}.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Detroit parking requirements</title>"
        "<style>html,body{margin:0;background:#fffaf0}"
        "main{width:min(100%,1600px);margin:auto}"
        "svg{display:block;width:100%;height:auto}"
        "@media print{@page{size:16in 11in;margin:0}}</style></head>"
        f"<body><main>{svg}</main></body></html>",
        encoding="utf-8",
    )
    renderer = shutil.which("rsvg-convert")
    if renderer:
        subprocess.run(
            [
                renderer,
                "--width", "3200",
                "--output", str(OUT / f"{stem}.png"),
                str(svg_path),
            ],
            check=True,
        )

    cases.to_csv(OUT / "parking-case-audit.csv", index=False)
    numeric = cases[cases["numeric_status"].eq("explicit_pair")]
    grants, denials, other = outcome_counts(cases)
    summary = {
        "parking_supply_case_histories": int(len(cases)),
        "cases_with_explicit_required_and_proposed_counts": int(len(numeric)),
        "cases_without_complete_numeric_pair": int(
            len(cases) - len(numeric)
        ),
        "spaces_required": int(numeric["required_spaces"].sum()),
        "spaces_proposed_or_provided": int(numeric["proposed_spaces"].sum()),
        "requested_shortfall_spaces": int(numeric["shortfall_spaces"].sum()),
        "median_shortfall_share": float(numeric["shortfall_share"].median()),
        "cases_proposing_zero_spaces": int(
            numeric["proposed_spaces"].eq(0).sum()
        ),
        "all_category_outcomes": {
            "granted_reversed": grants,
            "denied_upheld": denials,
            "other": other,
        },
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def main() -> None:
    cases = parking_cases()
    missing = sorted(set(PARKING_VALUES) - set(cases["case_history_id"]))
    if missing:
        raise ValueError(f"Transcribed case IDs absent from parking corpus: {missing}")
    numeric = cases[cases["numeric_status"].eq("explicit_pair")]
    if (numeric["required_spaces"] <= 0).any():
        raise ValueError("Every explicit requirement must be positive")
    if (numeric["proposed_spaces"] < 0).any():
        raise ValueError("Proposed spaces cannot be negative")
    if (numeric["proposed_spaces"] > numeric["required_spaces"]).any():
        raise ValueError("A parking-relief pair proposes more than required")
    write_assets(cases)


if __name__ == "__main__":
    main()
