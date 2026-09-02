"""Parking mandates by project type."""

import sys
from pathlib import Path

import polars as pl

FORUM = Path(__file__).resolve().parents[3] / "detroit-land-use-forum"
sys.path.insert(0, str(FORUM / "parking-by-project-type"))

from build_parking_by_type_asset import (  # noqa: E402
    classified_cases,
)
from strongtowns_graphics import (  # noqa: E402
    BarArrangement,
    BarChartStyle,
    BarOrientation,
    BarPattern,
    BarSeries,
    ChartAlignment,
    GraphicInput,
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


@graphic_definition(
    "parking_gaps_by_project_type",
    inputs=(
        GraphicInput(
            "parking_audit",
            "detroit.bza.parking-requirements",
            "parking-case-audit.csv",
        ),
    ),
)
def build(context):
    source = classified_cases(context.input("parking_audit"))
    cases = pl.DataFrame(
        {
            "project_type": source["project_type"].tolist(),
            "numeric_status": source["numeric_status"].tolist(),
            "proposed_spaces": source["proposed_spaces"].tolist(),
            "required_spaces": source["required_spaces"].tolist(),
        }
    )

    totals = (
        cases.filter(pl.col("numeric_status") == "explicit_pair")
        .group_by("project_type")
        .agg(
            pl.col("proposed_spaces").sum().cast(pl.Int64).alias("proposed"),
            pl.col("required_spaces").sum().cast(pl.Int64).alias("mandated"),
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
            "proposed": ordered_totals["proposed"],
            "additional_mandated": (
                ordered_totals["mandated"] - ordered_totals["proposed"]
            ),
            "annotation": [
                f"{row['proposed']:,} proposed · "
                f"{row['mandated'] - row['proposed']:,} additional spaces mandated"
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
                column="proposed",
                label="Proposed by developments",
                color="#082647",
            ),
            BarSeries(
                column="additional_mandated",
                label="Additional spaces mandated",
                color="#d9872c",
                pattern=BarPattern.DIAGONAL,
            ),
        ),
        title=(
            "Detroit's zoning code mandates far more parking than new developments propose"
        ),
        subtitle=(
            "Additional parking mandated by project type · Detroit BZA cases, "
            "2019–2026"
        ),
        axis=NumericAxis(
            title="",
            tick_step=200,
        ),
        style=BarChartStyle(
            text_color="#082647",
            muted_color="#526477",
            grid_color="#e4dccf",
        ),
        sources=(
            "Source: Detroit BZA minutes, 2019–2026.",
        ),
        description=(
            "Proposed and legally mandated parking in 35 Detroit Board of "
            "Zoning Appeals cases, grouped by project type. The hatched bar "
            "segments show spaces mandated beyond development proposals."
        ),
    )
    return {"parking-gaps-by-project-type": graphic}
