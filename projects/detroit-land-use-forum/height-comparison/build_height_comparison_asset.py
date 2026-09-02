#!/usr/bin/env python3
"""Build an allowed-versus-proposed BZA height exhibit."""

from __future__ import annotations

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

DATA = data_repository() / "pipelines/zoning/bza_dataset_gemini"
OUT = HERE / "output"

CREAM = "#fffaf0"
NAVY = "#082647"
RED = "#c8102e"
GOLD = "#ffb547"
MUTED = "#526477"
PALE = "#e4dccf"

# Feet stated in the representative BZA minutes. Fractional feet are retained
# as decimals (for example, 19 feet 1 inch = 19 + 1/12).
HEIGHT_VALUES: dict[str, tuple[float, float, str]] = {
    "bza-1-19-b17dd09224": (450, 535, "High-rise"),
    "bza-106-19-ac2502a929": (75, 98, "Hotel"),
    "bza-25-20-0c7c6c8bde": (35, 64, "Office"),
    "bza-23-21-67b09caf30": (35, 43, "Mixed-use"),
    "bza-30-21-d888c96eb5": (50, 64, "Mixed-use"),
    "bza-9-22-9fe538539b": (15, 16 + 0.75 / 12, "Carriage house"),
    "bza-51-22-07f10681c0": (15, 19 + 1 / 12, "Garage"),
    "bza-19-24-5152521f4c": (8, 20, "Screen wall"),
    "bza-39-24-fc8328dfcb": (8, 10, "Screen wall"),
    "bza-29-25-7515a970f7": (80, 101 + 7 / 12, "Mixed-use"),
}

OBJECT_TYPES: dict[str, str] = {
    "bza-01-19-6ca8bb24fa": "Building",
    "bza-33-19-ccbe2c0b37": "Accessory structure",
    "bza-65-19-ece5db0d26": "Sign",
    "bza-106-19-ac2502a929": "Building",
    "bza-1-19-b17dd09224": "Building",
    "bza-25-20-0c7c6c8bde": "Building",
    "bza-23-21-67b09caf30": "Building",
    "bza-30-21-d888c96eb5": "Building",
    "bza-9-22-9fe538539b": "Accessory structure",
    "bza-51-22-07f10681c0": "Accessory structure",
    "bza-22-23-4eb0024be7": "Accessory dwelling",
    "bza-4-24-1781607356": "Accessory structure",
    "bza-19-24-5152521f4c": "Wall",
    "bza-39-24-fc8328dfcb": "Wall",
    "bza-68-24-956bfd6d3d": "Accessory dwelling",
    "bza-86-24-15baadd557": "Storage container",
    "bza-24-25-67f735277c": "Accessory dwelling",
    "bza-29-25-7515a970f7": "Building",
}

# The same Monroe/Bedrock tower appears first as 01-19 with an unresolved
# outcome and later as 1-19 with the same 535/450-foot request and a grant.
PREDECESSOR_DUPLICATES = {"bza-01-19-6ca8bb24fa"}


def height_cases() -> pd.DataFrame:
    histories = pd.read_csv(DATA / "case_histories.csv", dtype=str).fillna("")
    categories = pd.read_csv(DATA / "case_categories.csv", dtype=str)
    ids = set(
        categories.loc[categories["category"].eq("height"), "case_history_id"]
    )
    cases = histories[histories["case_history_id"].isin(ids)].copy()
    cases["object_type"] = cases["case_history_id"].map(OBJECT_TYPES)
    cases["allowed_height_ft"] = cases["case_history_id"].map(
        lambda key: HEIGHT_VALUES.get(key, (None, None, ""))[0]
    )
    cases["proposed_height_ft"] = cases["case_history_id"].map(
        lambda key: HEIGHT_VALUES.get(key, (None, None, ""))[1]
    )
    cases["project_label"] = cases["case_history_id"].map(
        lambda key: HEIGHT_VALUES.get(key, (None, None, ""))[2]
    )
    cases["audit_status"] = "not_stated"
    cases.loc[
        cases["case_history_id"].isin(HEIGHT_VALUES), "audit_status"
    ] = "explicit_pair"
    cases.loc[
        cases["case_history_id"].isin(PREDECESSOR_DUPLICATES), "audit_status"
    ] = "same_project_predecessor"
    cases["proposed_share_of_limit"] = (
        cases["proposed_height_ft"] / cases["allowed_height_ft"]
    )
    cases["excess_height_ft"] = (
        cases["proposed_height_ft"] - cases["allowed_height_ft"]
    )
    cases["excess_share"] = cases["proposed_share_of_limit"] - 1
    return cases.sort_values(["first_meeting_date", "case_history_id"])


def display_feet(value: float) -> str:
    whole = int(value)
    inches = round((value - whole) * 12)
    return f"{whole}′ {inches}″" if inches else f"{whole}′"


def short_location(value: str) -> str:
    return (
        value.split(" between ")[0]
        .split(" Between:")[0]
        .split(", between ")[0]
        .split(", Corner")[0]
        .strip(" ,.")
    )


def build_svg(cases: pd.DataFrame) -> str:
    valid = cases[
        ~cases["audit_status"].eq("same_project_predecessor")
    ].copy()
    numeric = valid[valid["audit_status"].eq("explicit_pair")].copy()
    numeric = numeric.sort_values(
        ["object_type", "proposed_share_of_limit", "case_history_id"],
        ascending=[True, False, True],
    )
    grants = int(valid["final_outcome"].eq("granted_reversed").sum())
    denials = int(valid["final_outcome"].eq("denied_upheld").sum())
    other = len(valid) - grants - denials
    decided = grants + denials
    median_excess = numeric["excess_share"].median()

    plot_x = 660
    scale = 330  # 100% of the legal maximum
    rows = []
    for index, (_, row) in enumerate(numeric.iterrows()):
        y = 536 + index * 47
        proposed_width = scale * row.proposed_share_of_limit
        allowed_width = scale
        label = html.escape(
            f"{row.project_label} · {short_location(row.location)}"
        )
        values = (
            f"{display_feet(row.allowed_height_ft)} allowed · "
            f"{display_feet(row.proposed_height_ft)} proposed"
        )
        rows.append(
            f'<text class="row-label" x="58" y="{y + 18}">{label[:46]}</text>'
            f'<text class="row-values" x="625" y="{y + 18}" '
            f'text-anchor="end">{values}</text>'
            f'<rect x="{plot_x}" y="{y}" width="{proposed_width:.1f}" '
            f'height="27" rx="3" fill="{RED}"/>'
            f'<rect x="{plot_x}" y="{y}" width="{allowed_width}" '
            f'height="27" rx="3" fill="{NAVY}"/>'
            f'<text class="ratio" x="{plot_x + proposed_width + 12:.1f}" '
            f'y="{y + 19}">+{row.excess_share:.0%}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">Every decided Detroit BZA height case was granted</title>
<desc id="desc">Among 17 unique height projects from 2019 through 2025, 15 were granted, none were denied, and two were dismissed or withdrawn. Ten projects state explicit allowed and proposed heights.</desc>
<style>
.paper{{fill:{CREAM}}}
.kicker,.metric-label,.note,.source,.row-label,.row-values,.ratio,.legend,.axis{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:58px;font-weight:700}}.dek{{font-size:24px;fill:#48596d}}
.metric{{font-size:75px;font-weight:700}}.metric-label{{font-size:15px;font-weight:700;letter-spacing:1.2px;fill:{MUTED}}}
.section-title{{font-size:27px;font-weight:700}}.note{{font-size:18px;fill:#34475d}}
.source{{font-size:13px;fill:{MUTED}}}.row-label{{font-size:15px;font-weight:700;fill:{NAVY}}}
.row-values{{font-size:14px;fill:{MUTED}}}.ratio{{font-size:14px;font-weight:700;fill:{RED}}}
.legend{{font-size:14px;fill:{NAVY}}}.axis{{font-size:13px;font-weight:700;letter-spacing:1px;fill:{MUTED}}}
</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
<text class="title" x="52" y="120">Every decided height case</text>
<text class="title" x="52" y="184">was granted</text>
<text class="dek" x="55" y="231">Building, accessory-structure, wall, sign, and storage requests, 2019–2025</text>

<text class="metric" x="60" y="365">{len(valid)}</text>
<text class="metric-label" x="65" y="397">UNIQUE HEIGHT PROJECTS</text>
<text class="metric" x="390" y="365">{grants}</text>
<text class="metric-label" x="395" y="397">GRANTED OR REVERSED</text>
<text class="metric" x="735" y="365">{denials}</text>
<text class="metric-label" x="740" y="397">DENIED OR UPHELD</text>
<text class="metric" x="1035" y="365">{len(numeric)}</text>
<text class="metric-label" x="1040" y="397">WITH EXPLICIT HEIGHT PAIRS</text>
<text class="metric" x="1360" y="365">{median_excess:.0%}</text>
<text class="metric-label" x="1365" y="397">MEDIAN EXCESS</text>

<text class="section-title" x="55" y="475">How far above the stated maximum?</text>
<rect x="1035" y="450" width="14" height="14" fill="{NAVY}"/>
<text class="legend" x="1056" y="462">Allowed height</text>
<rect x="1160" y="450" width="14" height="14" fill="{RED}"/>
<text class="legend" x="1181" y="462">Additional proposed height</text>
<text class="axis" x="{plot_x + scale}" y="510" text-anchor="middle">100% · LEGAL MAXIMUM</text>
<line x1="{plot_x + scale}" y1="520" x2="{plot_x + scale}" y2="1010" stroke="{PALE}" stroke-width="3"/>
{''.join(rows)}

<line x1="55" y1="1021" x2="1545" y2="1021" stroke="{PALE}" stroke-width="2"/>
<text class="note" x="55" y="1051">{decided} projects reached a substantive recorded outcome: {grants} grants and {denials} denials. The other {other} were dismissed or withdrawn.</text>
<text class="source" x="55" y="1078">Bars show the 10 projects that state both the allowed and proposed height. Seven additional height projects omit one of those figures.</text>
</svg>"""


def write_assets(cases: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = build_svg(cases)
    stem = "detroit-height-comparison"
    svg_path = OUT / f"{stem}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    (OUT / f"{stem}.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Detroit BZA height comparison</title>"
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
                renderer, "--width", "3200",
                "--output", str(OUT / f"{stem}.png"), str(svg_path),
            ],
            check=True,
        )
    cases.to_csv(OUT / "height-case-audit.csv", index=False)
    valid = cases[
        ~cases["audit_status"].eq("same_project_predecessor")
    ]
    numeric = valid[valid["audit_status"].eq("explicit_pair")]
    summary = {
        "raw_height_histories": int(len(cases)),
        "unique_height_projects": int(len(valid)),
        "same_project_predecessors_collapsed": int(
            cases["audit_status"].eq("same_project_predecessor").sum()
        ),
        "explicit_height_pairs": int(len(numeric)),
        "without_explicit_pair": int(
            valid["audit_status"].eq("not_stated").sum()
        ),
        "outcomes": {
            "granted_reversed": int(
                valid["final_outcome"].eq("granted_reversed").sum()
            ),
            "denied_upheld": int(
                valid["final_outcome"].eq("denied_upheld").sum()
            ),
            "other": int(
                (
                    ~valid["final_outcome"].isin(
                        ["granted_reversed", "denied_upheld"]
                    )
                ).sum()
            ),
        },
        "median_excess_share_numeric_cases": float(
            numeric["excess_share"].median()
        ),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def main() -> None:
    cases = height_cases()
    if cases["object_type"].isna().any():
        raise ValueError("Every height history requires an object type")
    absent = sorted(
        (set(HEIGHT_VALUES) | PREDECESSOR_DUPLICATES)
        - set(cases["case_history_id"])
    )
    if absent:
        raise ValueError(f"Audited height cases absent from corpus: {absent}")
    numeric = cases[cases["audit_status"].eq("explicit_pair")]
    if (numeric["proposed_height_ft"] <= numeric["allowed_height_ft"]).any():
        raise ValueError("Every explicit height case must exceed its limit")
    write_assets(cases)


if __name__ == "__main__":
    main()
