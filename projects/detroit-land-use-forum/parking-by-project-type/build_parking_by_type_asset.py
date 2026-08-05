#!/usr/bin/env python3
"""Compare Detroit BZA parking requirements by primary project type."""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))
from exhibit_brand import masthead_svg
from exhibit_components import (
    forum_css,
    ghost_hatch_pattern,
    title_block,
    write_svg_bundle,
)
PARKING_AUDIT = (
    PROJECT / "parking-requirements/output/parking-case-audit.csv"
)
OUT = HERE / "output"

CREAM = "#fffaf0"
NAVY = "#082647"
RED = "#c8102e"
BLUE = "#4e92ce"
MUTED = "#526477"
PALE = "#e4dccf"

# Mutually exclusive, manually reviewed primary-use groups. Mixed projects are
# classified by the dominant use described in the minutes.
PROJECT_TYPES: dict[str, list[str]] = {
    "Food, drink & gathering": """
        bza-14-19-184cee7e49 bza-88-19-07e1969543
        bza-101-19-2b70c94d41 bza-103-19-b51a4c7926
        bza-31-21-ace9be1d9d bza-60-21-edd97a26a1
        bza-40-22-1bccc643ae bza-08-23-aa01dd18f0
        bza-23-23-d43e4e845a bza-19-23-ed15514286
        bza-10-24-4e76e64453 bza-18-24-b7d9862137
        bza-25-24-e30fbc8699 bza-31-24-5f6ef1ba25
        bza-32-24-9d20f69e4b bza-40-24-8e2b4f04b1
        bza-84-24-6f5548ffcb bza-5-25-489295d35a
        bza-10-25-d76fac624f bza-27-25-b460cdbf7e
    """.split(),
    "Housing & mixed-use": """
        bza-67-18-3e522c88c3 bza-38-20-ee1ac31af4
        bza-06-21-e118eb8f66 bza-10-21-ae57d08409
        bza-42-20-373295a30e bza-41-21-988b579aea
        bza-50-22-e2dd6e5b59 bza-58-22-943196124c
        bza-24-23-39f2ee37b3 bza-29-23-1e6ae3ddb9
        bza-33-23-9df1fa2044 bza-58-24-6532bebb8a
        bza-60-24-fc667bdd68 bza-66-24-27cac6bb0f
        bza-82-24-c4233e3f2a
    """.split(),
    "Community & institutional": """
        bza-40-19-aae5d99948 bza-78-19-9477858622
        bza-110-19-6035ce5f01 bza-111-19-7252fe4512
        bza-27-23-9c40617de8 bza-17-24-ce52cb3966
        bza-24-24-ba03fb1f1d bza-29-24-6d70f0b779
        bza-38-24-5cdec3b56e bza-80-24-eb9518e9ff
        bza-14-25-61fbd5eb1b
    """.split(),
    "Vehicle, production & industrial": """
        bza-38-19-f657c9531f bza-43-20-83bc71214b
        bza-24-21-9280554649 bza-53-22-f89cd6be57
        bza-18-23-535a07c23f bza-12-24-a6fc69b387
        bza-bza2025-00044-8af9060833
    """.split(),
    "Retail, office & personal services": """
        bza-112-19-8bdcb1c11b bza-34-20-ee36e5ccb2
        bza-29-20-787a86c963 bza-06-22-239afc0021
        bza-7-25-6f5b94d140
    """.split(),
    "Cannabis facilities": """
        bza-3-22-cd12f2bbc2 bza-11-22-50abfc40df
        bza-35-24-7b8306b2c9 bza-15-25-aa055fbabb
    """.split(),
}


def classified_cases() -> pd.DataFrame:
    cases = pd.read_csv(PARKING_AUDIT, dtype=str).fillna("")
    mapping = {
        case_id: project_type
        for project_type, case_ids in PROJECT_TYPES.items()
        for case_id in case_ids
    }
    cases["project_type"] = cases["case_history_id"].map(mapping)
    for column in [
        "required_spaces", "proposed_spaces",
        "shortfall_spaces", "shortfall_share",
    ]:
        cases[column] = pd.to_numeric(cases[column], errors="coerce")
    return cases


def summarize(cases: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for project_type in PROJECT_TYPES:
        group = cases[cases["project_type"].eq(project_type)]
        numeric = group[group["numeric_status"].eq("explicit_pair")]
        rows.append(
            {
                "project_type": project_type,
                "histories": len(group),
                "numeric_histories": len(numeric),
                "granted": int(
                    group["final_outcome"].eq("granted_reversed").sum()
                ),
                "denied": int(
                    group["final_outcome"].eq("denied_upheld").sum()
                ),
                "required": int(numeric["required_spaces"].sum()),
                "proposed": int(numeric["proposed_spaces"].sum()),
                "gap": int(numeric["shortfall_spaces"].sum()),
                "median_gap_share": float(numeric["shortfall_share"].median()),
            }
        )
    return pd.DataFrame(rows)


def build_svg(cases: pd.DataFrame, summary: pd.DataFrame) -> str:
    grants = int(cases["final_outcome"].eq("granted_reversed").sum())
    max_required = int(summary["required"].max())

    rows = []
    y0 = 408
    for index, row in summary.iterrows():
        y = y0 + index * 80
        full_width = 500 * row.required / max_required
        proposed_width = (
            full_width * row.proposed / row.required if row.required else 0
        )
        ghost_x = 510 + proposed_width
        ghost_width = max(0, full_width - proposed_width)
        rows.append(
            f'<text class="row-label" x="58" y="{y + 21}">'
            f'{html.escape(row.project_type)}</text>'
            f'<text class="case-count" x="58" y="{y + 44}">'
            f'{row.histories} cases · '
            f'{row.numeric_histories} with counts</text>'
            f'<clipPath id="bar-{index}"><rect x="510" y="{y}" '
            f'width="{full_width:.1f}" height="31" rx="4"/></clipPath>'
            f'<g clip-path="url(#bar-{index})">'
            f'<rect x="510" y="{y}" width="{proposed_width:.1f}" '
            f'height="31" fill="{NAVY}"/>'
            f'<rect x="{ghost_x:.1f}" y="{y}" width="{ghost_width:.1f}" '
            f'height="31" fill="url(#ghost-parking)" stroke="{RED}" '
            f'stroke-opacity=".5" stroke-width="1.5"/>'
            f'</g>'
            f'<text class="proposed-spaces" x="1160" y="{y + 21}" '
            f'text-anchor="end">'
            f'{row.proposed:,} proposed</text>'
            f'<text class="required-spaces" x="1325" y="{y + 21}" '
            f'text-anchor="end">'
            f'{row.required:,} required</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1450 1100"
role="img" aria-labelledby="title desc">
<title id="title">Parking gaps by project type</title>
<desc id="desc">Required and proposed parking in 35 Detroit Board of Zoning Appeals cases, grouped by project type.</desc>
<defs>
  {ghost_hatch_pattern(color=RED)}
</defs>
<style>{forum_css(title_size=56, note_size=18, legend_size=14,
extra_sans=(".row-label", ".case-count", ".proposed-spaces",
".required-spaces", ".column"),
extra_rules=f".row-label{{font-size:18px;font-weight:700;fill:{NAVY}}}"
f".case-count{{font-size:14px;fill:{MUTED}}}"
f".proposed-spaces{{font-size:14px;font-weight:700;fill:{NAVY}}}"
f".required-spaces{{font-size:14px;font-weight:700;fill:{RED}}}"
f".column{{font-size:12px;font-weight:700;letter-spacing:1px;fill:{MUTED}}}",
cream=CREAM, navy=NAVY, red=RED, muted=MUTED)}</style>
<rect class="paper" width="1450" height="1100"/>
{masthead_svg()}
{title_block("Parking gaps by project type",
"Required and proposed parking in 35 Detroit BZA cases, 2019–2026",
title_y=145, subtitle_y=195)}

<text class="section-title" x="55" y="343">Required and proposed spaces</text>
<rect x="1010" y="321" width="14" height="14" fill="{NAVY}"/>
<text class="legend" x="1031" y="333">Proposed or provided</text>
<rect x="1175" y="321" width="14" height="14" fill="url(#ghost-parking)"
  stroke="{RED}" stroke-opacity=".5"/>
<text class="legend" x="1196" y="333">Required beyond proposal</text>
<text class="column" x="1160" y="380" text-anchor="end">PROPOSED</text>
<text class="column" x="1325" y="380" text-anchor="end">REQUIRED</text>
{''.join(rows)}

<line x1="55" y1="991" x2="1395" y2="991" stroke="{PALE}" stroke-width="2"/>
<text class="note" x="55" y="1022">{grants} of 62 parking cases ended in a grant or reversal. These comparisons describe cases reaching the BZA; they do not establish why a requirement or outcome occurred.</text>
<text class="source" x="55" y="1050">An additional 27 parking cases were found in the BZA minutes but did not state both required and proposed counts, so no parking gap could be calculated.</text>
<text class="source" x="55" y="1078">Project groups are mutually exclusive. Source: Detroit BZA minutes, 2019–2026.</text>
</svg>"""


def write_assets(cases: pd.DataFrame, summary: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = build_svg(cases, summary)
    stem = "detroit-parking-by-project-type"
    write_svg_bundle(
        OUT, stem, "Detroit parking by project type", svg,
        width=1450, height=1100, png_width=2900, background=CREAM,
    )
    cases.to_csv(OUT / "parking-project-type-audit.csv", index=False)
    summary.to_csv(OUT / "parking-project-type-summary.csv", index=False)
    payload = {
        "parking_histories": int(len(cases)),
        "explicit_count_histories": int(
            cases["numeric_status"].eq("explicit_pair").sum()
        ),
        "project_type_counts": {
            row.project_type: int(row.histories)
            for _, row in summary.iterrows()
        },
    }
    (OUT / "summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


def main() -> None:
    cases = classified_cases()
    if cases["project_type"].isna().any():
        missing = cases.loc[
            cases["project_type"].isna(), "case_history_id"
        ].tolist()
        raise ValueError(f"Unclassified parking histories: {missing}")
    listed = [
        case_id for case_ids in PROJECT_TYPES.values() for case_id in case_ids
    ]
    if len(listed) != len(set(listed)):
        raise ValueError("A case appears in more than one project type")
    if set(listed) != set(cases["case_history_id"]):
        raise ValueError("Project-type crosswalk does not match parking corpus")
    summary = summarize(cases)
    write_assets(cases, summary)


if __name__ == "__main__":
    main()
