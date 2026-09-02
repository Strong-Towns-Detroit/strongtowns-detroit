#!/usr/bin/env python3
"""Compare Detroit BZA parking requirements by primary project type."""

from __future__ import annotations

import html
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))
from exhibit_components import (
    forum_css,
    ghost_hatch_pattern,
)
from strongtowns_graphics import (
    CONFERENCE_LANDSCAPE,
    Graphic,
    SvgComponent,
    render_graphic_svg,
    write_graphic_bundle,
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


def classified_cases(path: Path = PARKING_AUDIT) -> pd.DataFrame:
    cases = pd.read_csv(path, dtype=str).fillna("")
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


def build_graphic(
    cases: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    title: str = (
        "Developers consistently propose far fewer parking spaces "
        "than the law requires."
    ),
    subtitle: str = "Parking gaps by project type · Detroit BZA cases, 2019–2026",
    notes: tuple[str, ...] | None = None,
    sources: tuple[str, ...] | None = None,
    description: str | None = None,
) -> Graphic:
    grants = int(cases["final_outcome"].eq("granted_reversed").sum())
    max_required = int(summary["required"].max())
    tick_step = 200
    axis_max = math.ceil(max_required / tick_step) * tick_step
    chart_x = 510
    chart_width = 800
    pixels_per_space = chart_width / axis_max

    ticks = []
    for value in range(0, axis_max + 1, tick_step):
        x = chart_x + value * pixels_per_space
        ticks.append(
            f'<line x1="{x:.1f}" y1="73" x2="{x:.1f}" y2="594" '
            f'stroke="{PALE}" stroke-width="1"/>'
            f'<text class="axis" x="{x:.1f}" y="63" text-anchor="middle">'
            f'{value:,}</text>'
        )

    rows = []
    y0 = 100
    for index, row in summary.iterrows():
        y = y0 + index * 82
        full_width = row.required * pixels_per_space
        proposed_width = row.proposed * pixels_per_space
        ghost_x = chart_x + proposed_width
        ghost_width = max(0, full_width - proposed_width)
        rows.append(
            f'<text class="row-label" x="58" y="{y + 21}">'
            f'{html.escape(row.project_type)}</text>'
            f'<text class="case-count" x="58" y="{y + 44}">'
            f'{row.proposed:,} spaces proposed · '
            f'{row.required:,} required by law</text>'
            f'<clipPath id="bar-{index}"><rect x="{chart_x}" y="{y}" '
            f'width="{full_width:.1f}" height="31" rx="4"/></clipPath>'
            f'<g clip-path="url(#bar-{index})">'
            f'<rect x="{chart_x}" y="{y}" width="{proposed_width:.1f}" '
            f'height="31" fill="{NAVY}"/>'
            f'<rect x="{ghost_x:.1f}" y="{y}" width="{ghost_width:.1f}" '
            f'height="31" fill="url(#ghost-parking)" stroke="{RED}" '
            f'stroke-opacity=".5" stroke-width="1.5"/>'
            f'</g>'
        )

    visual = f"""
<defs>
  {ghost_hatch_pattern(color=RED)}
</defs>
<style>{forum_css(title_size=56, note_size=18, legend_size=14,
extra_sans=(".row-label", ".case-count", ".proposed-spaces",
".required-spaces", ".column", ".axis"),
extra_rules=f".row-label{{font-size:18px;font-weight:700;fill:{NAVY}}}"
f".case-count{{font-size:14px;fill:{MUTED}}}"
f".proposed-spaces{{font-size:14px;font-weight:700;fill:{NAVY}}}"
f".required-spaces{{font-size:14px;font-weight:700;fill:{RED}}}"
f".column{{font-size:12px;font-weight:700;letter-spacing:1px;fill:{MUTED}}}"
f".axis{{font-size:13px;fill:{MUTED}}}",
cream=CREAM, navy=NAVY, red=RED, muted=MUTED)}</style>
<text class="section-title" x="55" y="23">Required and proposed spaces</text>
<rect x="1010" y="1" width="14" height="14" fill="{NAVY}"/>
<text class="legend" x="1031" y="13">Proposed or provided</text>
<rect x="1175" y="1" width="14" height="14" fill="url(#ghost-parking)"
  stroke="{RED}" stroke-opacity=".5"/>
<text class="legend" x="1196" y="13">Required beyond proposal</text>
<text class="column" x="510" y="45">TOTAL PARKING SPACES</text>
{''.join(ticks)}
{''.join(rows)}
"""
    return Graphic(
        title=title,
        subtitle=subtitle,
        visual=SvgComponent(visual, width=1450, height=620),
        notes=notes if notes is not None else (
            f"{grants} of 62 parking cases ended in a grant or reversal. "
            "These comparisons describe cases reaching the BZA; they do not "
            "establish why a requirement or outcome occurred.",
        ),
        sources=sources if sources is not None else (
            "An additional 27 parking cases were found in the BZA minutes but "
            "did not state both required and proposed counts, so no parking "
            "gap could be calculated.",
            "Project groups are mutually exclusive. Source: Detroit BZA "
            "minutes, 2019–2026.",
        ),
        description=description if description is not None else (
            "Required and proposed parking in 35 Detroit Board of Zoning "
            "Appeals cases, grouped by project type."
        ),
    )


def build_svg(cases: pd.DataFrame, summary: pd.DataFrame) -> str:
    """Compatibility helper returning the fully composed SVG."""
    return render_graphic_svg(
        build_graphic(cases, summary),
        aspect_ratio=CONFERENCE_LANDSCAPE,
    )


def write_assets(cases: pd.DataFrame, summary: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stem = "detroit-parking-by-project-type"
    write_graphic_bundle(
        OUT,
        stem,
        build_graphic(cases, summary),
        aspect_ratio=CONFERENCE_LANDSCAPE,
        png_width=2900,
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
