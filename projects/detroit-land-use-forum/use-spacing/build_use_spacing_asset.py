#!/usr/bin/env python3
"""Build an auditable BZA use-spacing threshold exhibit."""

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
BLUE = "#4e92ce"
MUTED = "#526477"
PALE = "#e4dccf"

# One controlling distance pair per history. For cases with multiple cited
# conflicts, the pair with the smallest actual/required ratio is used. The
# context field describes the protected or regulated use behind that pair.
SPACING_VALUES: dict[str, tuple[float, float, str, str]] = {
    "bza-116-16-902857b7a3": (1000, 174, "controlled_use", "party store"),
    "bza-75-18-7d8e616722": (1000, 872.8, "drug_free_zone", "school"),
    "bza-76-18-cbc171d150": (1000, 950, "drug_free_zone", "playground"),
    "bza-77-18-95afed9f1e": (1000, 759, "controlled_use", "market"),
    "bza-49-18-7931dced47": (1000, 356, "controlled_use", "controlled use"),
    "bza-06-17-1938c13e88": (1000, 765, "controlled_use", "liquor store"),
    "bza-57-18-3495b99b21": (1000, 82, "controlled_use", "food store"),
    "bza-9-19-4602d22e22": (1000, 470, "drug_free_zone", "youth center/school"),
    "bza-8-19-5feed4f6f4": (1000, 430, "drug_free_zone", "family housing"),
    "bza-94-17-ef14740afe": (1000, 357.7, "controlled_use", "market"),
    "bza-20-19-f02fd63021": (1000, 245, "controlled_use", "liquor store"),
    "bza-27-19-79df09a810": (1000, 539, "drug_free_zone", "school"),
    "bza-80-17-303a06ac56": (1000, 701, "similar_use", "marijuana facility"),
    "bza-43-19-df0b0c111b": (1000, 138, "similar_use", "used-auto sales"),
    "bza-51-19-16581fdd54": (1000, 438, "drug_free_zone", "park"),
    "bza-55-19-0f4e1aa768": (1000, 250, "similar_use", "used-auto sales"),
    "bza-60-19-c1f3b6a77d": (1000, 600, "protected_institution", "church/school"),
    "bza-63-19-7f94d4aa9b": (1000, 800, "similar_use", "used-auto sales"),
    "bza-62-19-80921f9b24": (1000, 679, "similar_use", "used-auto sales"),
    "bza-76-19-8948b8b0cf": (1000, 950, "drug_free_zone", "playground"),
    "bza-81-19-7c4a7d5065": (1000, 458, "similar_use", "cabaret/lounge"),
    "bza-68-18-995664bec8": (1000, 872.8, "drug_free_zone", "school"),
    "bza-26-17-06a09b7674": (1000, 399, "controlled_use", "liquor store"),
    "bza-98-19-99e1df0223": (1000, 600, "similar_use", "used-auto sales"),
    "bza-107-19-7c49964699": (1000, 935, "drug_free_zone", "school"),
    "bza-14-17-07ea6a1a53": (1000, 30, "protected_institution", "religious institution"),
    "bza-33-21-ebd11a8b91": (1000, 820, "controlled_use", "liquor store"),
    "bza-56-22-ec38b25482": (1000, 421, "similar_use", "marijuana facility"),
    "bza-03-23-cdc3a2629c": (1000, 805, "drug_free_zone", "historic fort"),
    "bza-16-23-d69ef06e72": (1000, 446, "drug_free_zone", "park"),
    "bza-9-24-bb584396c6": (1000, 130, "similar_use", "vehicle repair"),
    "bza-16-24-5938101fbe": (100, 20, "residential_land", "residential zoning"),
    "bza-20-24-2cf05e2c11": (2000, 1442, "similar_use", "used-auto sales"),
    "bza-36-24-25e89f7eb8": (1000, 707, "drug_free_zone", "park"),
    "bza-45-24-0ac7b21e08": (1000, 90, "similar_use", "vehicle repair"),
    "bza-51-24-646801293c": (1000, 404, "similar_use", "vehicle repair"),
    "bza-49-24-176da3f813": (1000, 110, "similar_use", "vehicle repair"),
}

FALSE_POSITIVES = {
    # This rental-hall case concerns parking and a neighborhood petition. The
    # phrase "within 500 radial feet" triggered the broad spacing classifier,
    # but the case does not request a use-spacing variance.
    "bza-12-19-8f68a059f3",
}


def spacing_cases() -> pd.DataFrame:
    histories = pd.read_csv(DATA / "case_histories.csv", dtype=str).fillna("")
    categories = pd.read_csv(DATA / "case_categories.csv", dtype=str)
    ids = set(
        categories.loc[
            categories["category"].eq("use_spacing_separation"),
            "case_history_id",
        ]
    )
    cases = histories[histories["case_history_id"].isin(ids)].copy()
    cases["required_distance_ft"] = cases["case_history_id"].map(
        lambda key: SPACING_VALUES.get(key, (None, None, "", ""))[0]
    )
    cases["actual_distance_ft"] = cases["case_history_id"].map(
        lambda key: SPACING_VALUES.get(key, (None, None, "", ""))[1]
    )
    cases["rule_context"] = cases["case_history_id"].map(
        lambda key: SPACING_VALUES.get(key, (None, None, "", ""))[2]
    )
    cases["nearby_use"] = cases["case_history_id"].map(
        lambda key: SPACING_VALUES.get(key, (None, None, "", ""))[3]
    )
    cases["audit_status"] = "not_stated"
    cases.loc[
        cases["case_history_id"].isin(SPACING_VALUES), "audit_status"
    ] = "explicit_pair"
    cases.loc[
        cases["case_history_id"].isin(FALSE_POSITIVES), "audit_status"
    ] = "not_spacing_case"
    cases["distance_share"] = (
        cases["actual_distance_ft"] / cases["required_distance_ft"]
    )
    return cases.sort_values(["first_meeting_date", "case_history_id"])


def final_outcome(value: str) -> str:
    if value == "granted_reversed":
        return "Granted"
    if value == "denied_upheld":
        return "Denied"
    return "Other"


def jitter_positions(frame: pd.DataFrame, outcome: str) -> dict[str, float]:
    subset = frame[frame["outcome_label"].eq(outcome)].sort_values(
        ["distance_share", "case_history_id"]
    )
    levels = [-20, 0, 20, -10, 10]
    positions: dict[str, float] = {}
    recent: list[tuple[float, int]] = []
    for _, row in subset.iterrows():
        share = float(row.distance_share)
        used = {
            level for prior_share, level in recent if abs(prior_share - share) < 0.055
        }
        level = next((candidate for candidate in levels if candidate not in used), 0)
        positions[row.case_history_id] = level
        recent.append((share, level))
        recent = [item for item in recent if share - item[0] < 0.055]
    return positions


def build_svg(cases: pd.DataFrame) -> str:
    valid = cases[
        ~cases["audit_status"].eq("not_spacing_case")
    ].copy()
    numeric = valid[valid["audit_status"].eq("explicit_pair")].copy()
    numeric["outcome_label"] = numeric["final_outcome"].map(final_outcome)
    grants = numeric[numeric["outcome_label"].eq("Granted")]
    denials = numeric[numeric["outcome_label"].eq("Denied")]
    other = numeric[numeric["outcome_label"].eq("Other")]
    grant_median = grants["distance_share"].median()
    denial_median = denials["distance_share"].median()

    plot_x, plot_width = 180, 1320
    band_y = {"Granted": 556, "Denied": 706, "Other": 856}
    color = {"Granted": NAVY, "Denied": RED, "Other": GOLD}
    jitter = {}
    for outcome in band_y:
        jitter.update(jitter_positions(numeric, outcome))
    dots = []
    for _, row in numeric.iterrows():
        x = plot_x + plot_width * min(float(row.distance_share), 1)
        y = band_y[row.outcome_label] + jitter[row.case_history_id]
        tip = html.escape(
            f"{row.printed_case_number}: {row.actual_distance_ft:g} of "
            f"{row.required_distance_ft:g} ft; {row.nearby_use}; "
            f"{row.outcome_label.lower()}"
        )
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="10" '
            f'fill="{color[row.outcome_label]}" stroke="{CREAM}" '
            f'stroke-width="3"><title>{tip}</title></circle>'
        )

    ticks = []
    for percent in range(0, 101, 20):
        x = plot_x + plot_width * percent / 100
        ticks.append(
            f'<line x1="{x:.1f}" y1="495" x2="{x:.1f}" y2="900" '
            f'stroke="{PALE}" stroke-width="2"/>'
            f'<text class="tick" x="{x:.1f}" y="930" '
            f'text-anchor="middle">{percent}%</text>'
        )

    contexts = (
        numeric.groupby(["rule_context", "outcome_label"])
        .size()
        .unstack(fill_value=0)
    )
    context_order = [
        ("drug_free_zone", "Drug-free zone"),
        ("controlled_use", "Controlled use"),
        ("similar_use", "Similar regulated use"),
        ("protected_institution", "Religious/school use"),
        ("residential_land", "Residential land"),
    ]
    context_text = []
    for index, (key, label) in enumerate(context_order):
        if key not in contexts.index:
            continue
        row = contexts.loc[key]
        y = 1010 + index * 0  # retained as a single compact line below
        context_text.append(
            f"{label}: {int(row.get('Granted', 0))} granted / "
            f"{int(row.get('Denied', 0))} denied"
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">Distance alone did not decide Detroit spacing cases</title>
<desc id="desc">Granted and denied use-spacing cases overlap throughout the prohibited distance. The median granted case was at 42 percent of its required distance; the median denied case was at 57 percent.</desc>
<style>
.paper{{fill:{CREAM}}}
.kicker,.metric-label,.note,.source,.tick,.band-label,.legend{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:57px;font-weight:700}}.dek{{font-size:24px;fill:#48596d}}
.metric{{font-size:72px;font-weight:700}}.metric-label{{font-size:15px;font-weight:700;letter-spacing:1.2px;fill:{MUTED}}}
.section-title{{font-size:27px;font-weight:700}}.note{{font-size:18px;fill:#34475d}}
.source{{font-size:13px;fill:{MUTED}}}.tick{{font-size:15px;fill:{MUTED}}}
.band-label{{font-size:18px;font-weight:700;fill:{NAVY}}}.legend{{font-size:15px;fill:{NAVY}}}
</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
<text class="title" x="52" y="120">Distance alone did not decide</text>
<text class="title" x="52" y="184">Detroit’s spacing cases</text>
<text class="dek" x="55" y="231">Grants and denials overlap throughout the legally prohibited distance</text>

<text class="metric" x="60" y="365">{len(valid)}</text>
<text class="metric-label" x="65" y="397">VERIFIED SPACING HISTORIES</text>
<text class="metric" x="410" y="365">{len(numeric)}</text>
<text class="metric-label" x="415" y="397">WITH AN EXPLICIT DISTANCE PAIR</text>
<text class="metric" x="830" y="365">{grant_median:.0%}</text>
<text class="metric-label" x="835" y="397">MEDIAN DISTANCE · GRANTED</text>
<text class="metric" x="1200" y="365">{denial_median:.0%}</text>
<text class="metric-label" x="1205" y="397">MEDIAN DISTANCE · DENIED</text>

<text class="section-title" x="55" y="463">How close was each use to satisfying the rule?</text>
<text class="note" x="1500" y="463" text-anchor="end">100% = required separation met</text>
{''.join(ticks)}
<text class="band-label" x="58" y="563">Granted</text>
<text class="band-label" x="58" y="713">Denied</text>
<text class="band-label" x="58" y="863">Other</text>
<line x1="{plot_x}" y1="556" x2="1500" y2="556" stroke="{PALE}" stroke-width="3"/>
<line x1="{plot_x}" y1="706" x2="1500" y2="706" stroke="{PALE}" stroke-width="3"/>
<line x1="{plot_x}" y1="856" x2="1500" y2="856" stroke="{PALE}" stroke-width="3"/>
{''.join(dots)}

<circle cx="61" cy="973" r="8" fill="{NAVY}"/><text class="legend" x="78" y="979">{len(grants)} granted</text>
<circle cx="191" cy="973" r="8" fill="{RED}"/><text class="legend" x="208" y="979">{len(denials)} denied</text>
<circle cx="310" cy="973" r="8" fill="{GOLD}"/><text class="legend" x="327" y="979">{len(other)} other</text>
<text class="note" x="520" y="979">A case only 9% of the way to compliance was granted; one at 94% was denied.</text>

<text class="source" x="55" y="1037">Unit: one deduplicated BZA case history. For multiple cited conflicts, the chart uses the smallest actual-to-required distance ratio. Hover points in HTML for case details.</text>
<text class="source" x="55" y="1063">Seven verified cases omit an exact actual-and-required distance pair and are not plotted. Source: Detroit BZA minutes, March 2019–July 2025.</text>
</svg>"""


def write_assets(cases: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = build_svg(cases)
    stem = "detroit-use-spacing-threshold"
    svg_path = OUT / f"{stem}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    (OUT / f"{stem}.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Detroit use-spacing cases</title>"
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
    cases.to_csv(OUT / "use-spacing-case-audit.csv", index=False)

    valid = cases[~cases["audit_status"].eq("not_spacing_case")]
    numeric = valid[valid["audit_status"].eq("explicit_pair")].copy()
    numeric["outcome_label"] = numeric["final_outcome"].map(final_outcome)
    summary = {
        "raw_classified_histories": int(len(cases)),
        "verified_spacing_histories": int(len(valid)),
        "classifier_false_positives": int(
            cases["audit_status"].eq("not_spacing_case").sum()
        ),
        "histories_with_explicit_distance_pair": int(len(numeric)),
        "histories_without_explicit_distance_pair": int(
            valid["audit_status"].eq("not_stated").sum()
        ),
        "numeric_outcomes": {
            key.lower(): int(value)
            for key, value in numeric["outcome_label"].value_counts().items()
        },
        "median_actual_share_of_required": {
            "granted": float(
                numeric.loc[
                    numeric["outcome_label"].eq("Granted"), "distance_share"
                ].median()
            ),
            "denied": float(
                numeric.loc[
                    numeric["outcome_label"].eq("Denied"), "distance_share"
                ].median()
            ),
        },
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def main() -> None:
    cases = spacing_cases()
    absent = sorted(
        (set(SPACING_VALUES) | FALSE_POSITIVES) - set(cases["case_history_id"])
    )
    if absent:
        raise ValueError(f"Audited case IDs absent from spacing corpus: {absent}")
    numeric = cases[cases["audit_status"].eq("explicit_pair")]
    if (numeric["required_distance_ft"] <= 0).any():
        raise ValueError("Required distances must be positive")
    if (numeric["actual_distance_ft"] < 0).any():
        raise ValueError("Actual distances cannot be negative")
    if (numeric["actual_distance_ft"] >= numeric["required_distance_ft"]).any():
        raise ValueError("Every plotted case must fall inside its required distance")
    write_assets(cases)


if __name__ == "__main__":
    main()
