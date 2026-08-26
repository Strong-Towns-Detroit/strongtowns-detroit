"""Parking gaps by project type."""

import sys
from pathlib import Path

import polars as pl

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
sys.path.insert(0, str(FORUM / "parking-by-project-type"))

from build_parking_by_type_asset import (  # noqa: E402
    classified_cases,
)
from strongtowns_detroit.graphics import (  # noqa: E402
    BarArrangement,
    BarChartStyle,
    BarOrientation,
    BarPattern,
    BarSeries,
    ChartAlignment,
    NumericAxis,
    bar_chart,
    graphic_definition,
)

CATEGORY_ORDER = (
    "Food, drink & gathering",
    "Housing & mixed-use",
    "Community & institutional",
    "Vehicle, production & industrial",
    "Retail, office & personal services",
    "Cannabis facilities",
)


@graphic_definition("parking_gaps_by_project_type")
def build():
    source = classified_cases()
    cases = pl.DataFrame(
        {
            "project_type": source["project_type"].tolist(),
            "numeric_status": source["numeric_status"].tolist(),
            "proposed_spaces": source["proposed_spaces"].tolist(),
            "required_spaces": source["required_spaces"].tolist(),
            "final_outcome": source["final_outcome"].tolist(),
        }
    )
    grants = cases.filter(
        pl.col("final_outcome") == "granted_reversed"
    ).height

    totals = (
        cases.filter(pl.col("numeric_status") == "explicit_pair")
        .group_by("project_type")
        .agg(
            pl.col("proposed_spaces").sum().cast(pl.Int64).alias("actual"),
            pl.col("required_spaces").sum().cast(pl.Int64).alias("target"),
        )
    )
    ordered_totals = (
        pl.DataFrame(
            {
                "category": CATEGORY_ORDER,
                "row_order": range(len(CATEGORY_ORDER)),
            }
        )
        .join(totals, left_on="category", right_on="project_type", how="left")
        .sort("row_order")
    )
    data = pl.DataFrame(
        {
            "category": ordered_totals["category"],
            "proposed_or_provided": ordered_totals["actual"],
            "required_beyond_proposal": (
                ordered_totals["target"] - ordered_totals["actual"]
            ),
            "annotation": [
                f"{row['actual']:,} spaces proposed · "
                f"{row['target']:,} required by law"
                for row in ordered_totals.iter_rows(named=True)
            ],
        }
    )
    graphic = bar_chart(
        data,
        category="category",
        annotation="annotation",
        orientation=BarOrientation.HORIZONTAL,
        portrait_orientation=BarOrientation.VERTICAL,
        portrait_category_label_angle=-35,
        legend_alignment=ChartAlignment.RIGHT,
        arrangement=BarArrangement.STACKED,
        series=(
            BarSeries(
                column="proposed_or_provided",
                label="Proposed or provided",
                color="#082647",
            ),
            BarSeries(
                column="required_beyond_proposal",
                label="Required beyond proposal",
                color="#c8102e",
                pattern=BarPattern.DIAGONAL,
            ),
        ),
        title=(
            "Detroit's Zoning Code mandates far more parking spaces than developments require"
        ),
        subtitle="Parking gaps by project type · Detroit BZA cases, 2019–2026",
        axis=NumericAxis(
            title="",
            tick_step=200,
        ),
        style=BarChartStyle(
            text_color="#082647",
            muted_color="#526477",
            grid_color="#e4dccf",
        ),
        notes=(
            f"{grants} of 62 parking cases ended in a grant or reversal. "
            "These comparisons describe cases reaching the BZA; they do not "
            "establish why a requirement or outcome occurred.",
        ),
        sources=(
            "An additional 27 parking cases were found in the BZA minutes but "
            "did not state both required and proposed counts, so no parking "
            "gap could be calculated.",
            "Project groups are mutually exclusive. Source: Detroit BZA "
            "minutes, 2019–2026.",
        ),
        description=(
            "Required and proposed parking in 35 Detroit Board of Zoning "
            "Appeals cases, grouped by project type."
        ),
    )
    return {"parking-gaps-by-project-type": graphic}
