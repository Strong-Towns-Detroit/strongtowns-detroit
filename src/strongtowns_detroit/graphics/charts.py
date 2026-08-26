"""Data-driven chart primitives for the graphics library."""

from __future__ import annotations

import html
import math
import textwrap
from dataclasses import dataclass
from enum import StrEnum

import polars as pl

from strongtowns_detroit.graphics.svg import Graphic, SvgComponent
from strongtowns_detroit.graphics.typography import MOBILE_TYPOGRAPHY


class BarOrientation(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class BarArrangement(StrEnum):
    STACKED = "stacked"
    GROUPED = "grouped"


class BarPattern(StrEnum):
    SOLID = "solid"
    DIAGONAL = "diagonal"


class ChartAlignment(StrEnum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class NumericAxis:
    title: str
    tick_step: float

    def __post_init__(self) -> None:
        if self.tick_step <= 0:
            raise ValueError("numeric axis tick step must be positive")


@dataclass(frozen=True)
class BarSeries:
    """A dataframe column and its visual encoding."""

    column: str
    label: str
    color: str
    pattern: BarPattern = BarPattern.SOLID


@dataclass(frozen=True)
class BarChartStyle:
    text_color: str = "#082647"
    muted_color: str = "#526477"
    grid_color: str = "#e4dccf"


def _validate_bar_data(
    data: pl.DataFrame,
    category_column: str,
    annotation_column: str | None,
    series: tuple[BarSeries, ...],
) -> None:
    if not series:
        raise ValueError("a bar chart requires at least one series")
    columns = {category_column, *(item.column for item in series)}
    if annotation_column:
        columns.add(annotation_column)
    missing = columns - set(data.columns)
    if missing:
        raise ValueError(f"bar chart data is missing columns: {sorted(missing)}")
    if data.is_empty():
        raise ValueError("bar chart data cannot be empty")
    if any(data[column].null_count() for column in columns):
        raise ValueError("bar chart data cannot contain nulls")
    if any(data.filter(pl.col(item.column) < 0).height for item in series):
        raise ValueError("bar chart values cannot be negative")


def _axis_maximum(
    data: pl.DataFrame,
    series: tuple[BarSeries, ...],
    arrangement: BarArrangement,
    tick_step: float,
) -> float:
    if arrangement is BarArrangement.STACKED:
        maximum = data.select(
            pl.sum_horizontal(*(pl.col(item.column) for item in series)).max()
        ).item()
    else:
        maximum = max(float(data[item.column].max()) for item in series)
    return max(tick_step, math.ceil(float(maximum) / tick_step) * tick_step)


def _fill(series: BarSeries, index: int) -> str:
    if series.pattern is BarPattern.DIAGONAL:
        return f"url(#bar-pattern-{index})"
    return series.color


def _patterns(series: tuple[BarSeries, ...]) -> str:
    patterns = []
    for index, item in enumerate(series):
        if item.pattern is not BarPattern.DIAGONAL:
            continue
        patterns.append(
            f'<pattern id="bar-pattern-{index}" width="8" height="8" '
            'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<line x1="0" y1="0" x2="0" y2="8" stroke="{item.color}" '
            'stroke-width="2" opacity=".5"/></pattern>'
        )
    return "".join(patterns)


def _legend(
    series: tuple[BarSeries, ...], *, mobile: bool, alignment: ChartAlignment
) -> str:
    size = 24 if mobile else 14
    font_size = MOBILE_TYPOGRAPHY.legend if mobile else 14
    gap = 32 if mobile else 20
    widths = [
        size + 10 + len(item.label) * font_size * 0.52
        for item in series
    ]
    total_width = sum(widths) + gap * (len(widths) - 1)
    x = 1450 - 55 - total_width if alignment is ChartAlignment.RIGHT else 55
    y = 4 if mobile else 1
    text_y = 24 if mobile else 13
    items = []
    for index, (item, width) in enumerate(zip(series, widths)):
        items.append(
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" '
            f'fill="{_fill(item, index)}" stroke="{item.color}" '
            f'stroke-opacity=".5"/><text class="bar-legend" '
            f'x="{x + size + 10}" y="{text_y}">{html.escape(item.label)}</text>'
        )
        x += width + gap
    return "".join(items)


def _horizontal_bars(
    data: pl.DataFrame,
    *,
    category_column: str,
    annotation_column: str | None,
    series: tuple[BarSeries, ...],
    arrangement: BarArrangement,
    axis: NumericAxis,
    axis_maximum: float,
    style: BarChartStyle,
    category_label_angle: float,
) -> str:
    chart_x, chart_width = 510, 800
    scale = chart_width / axis_maximum
    ticks = []
    value = 0.0
    while value <= axis_maximum + axis.tick_step / 1000:
        x = chart_x + value * scale
        label = f"{value:,.0f}" if value.is_integer() else f"{value:g}"
        ticks.append(
            f'<line x1="{x:.1f}" y1="73" x2="{x:.1f}" y2="594" '
            f'stroke="{style.grid_color}" stroke-width="1"/>'
            f'<text class="bar-axis" x="{x:.1f}" y="63" '
            f'text-anchor="middle">{label}</text>'
        )
        value += axis.tick_step

    rows = []
    for row_index, row in enumerate(data.iter_rows(named=True)):
        y = 100 + row_index * 82
        annotation = (
            f'<text class="bar-annotation" x="58" y="{y + 44}">'
            f'{html.escape(str(row[annotation_column]))}</text>'
            if annotation_column
            else ""
        )
        rows.append(
            f'<text class="bar-category" x="58" y="{y + 21}" '
            f'transform="rotate({category_label_angle:g} 58 {y + 21})">'
            f'{html.escape(str(row[category_column]))}</text>{annotation}'
        )
        offset = 0.0
        thickness = 31 if arrangement is BarArrangement.STACKED else 31 / len(series)
        total = sum(float(row[item.column]) for item in series)
        clip_width = total * scale if arrangement is BarArrangement.STACKED else chart_width
        rows.append(
            f'<clipPath id="bar-row-{row_index}"><rect x="{chart_x}" y="{y}" '
            f'width="{clip_width:.1f}" height="31" rx="4"/></clipPath>'
            f'<g clip-path="url(#bar-row-{row_index})">'
        )
        for series_index, item in enumerate(series):
            width = float(row[item.column]) * scale
            bar_x = chart_x + offset if arrangement is BarArrangement.STACKED else chart_x
            bar_y = y if arrangement is BarArrangement.STACKED else y + series_index * thickness
            rows.append(
                f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{width:.1f}" '
                f'height="{thickness:.1f}" fill="{_fill(item, series_index)}" '
                f'stroke="{item.color}" stroke-opacity=".5" stroke-width="1.5"/>'
            )
            if arrangement is BarArrangement.STACKED:
                offset += width
        rows.append("</g>")

    axis_title = (
        f'<text class="bar-axis-title" x="{chart_x}" y="45">'
        f'{html.escape(axis.title)}</text>'
        if axis.title
        else ""
    )
    return f'{axis_title}{"".join(ticks)}{"".join(rows)}'


def _vertical_bars(
    data: pl.DataFrame,
    *,
    category_column: str,
    annotation_column: str | None,
    series: tuple[BarSeries, ...],
    arrangement: BarArrangement,
    axis: NumericAxis,
    axis_maximum: float,
    style: BarChartStyle,
    category_label_angle: float,
) -> str:
    chart_x, chart_y, chart_width, chart_height = 120, 100, 1220, 875
    scale = chart_height / axis_maximum
    ticks = []
    value = 0.0
    while value <= axis_maximum + axis.tick_step / 1000:
        y = chart_y + chart_height - value * scale
        label = f"{value:,.0f}" if value.is_integer() else f"{value:g}"
        ticks.append(
            f'<line x1="{chart_x}" y1="{y:.1f}" x2="{chart_x + chart_width}" '
            f'y2="{y:.1f}" stroke="{style.grid_color}" stroke-width="1"/>'
            f'<text class="bar-axis" x="{chart_x - 12}" y="{y + 4:.1f}" '
            f'text-anchor="end">{label}</text>'
        )
        value += axis.tick_step

    groups = []
    group_width = chart_width / data.height
    available = group_width * 0.68
    for row_index, row in enumerate(data.iter_rows(named=True)):
        group_x = chart_x + row_index * group_width + (group_width - available) / 2
        center_x = group_x + available / 2
        category_lines = textwrap.wrap(
            str(row[category_column]),
            width=21,
            break_long_words=False,
            break_on_hyphens=False,
        )
        category_markup = "".join(
            f'<tspan x="{center_x:.1f}" dy="{0 if index == 0 else 21}">'
            f'{html.escape(line)}</tspan>'
            for index, line in enumerate(category_lines)
        )
        label_anchor = "end" if category_label_angle else "middle"
        label_y = 1015
        groups.append(
            f'<text class="bar-category" x="{center_x:.1f}" y="{label_y}" '
            f'text-anchor="{label_anchor}" transform="rotate('
            f'{category_label_angle:g} {center_x:.1f} {label_y})">'
            f'{category_markup}</text>'
        )
        offset = 0.0
        thickness = available if arrangement is BarArrangement.STACKED else available / len(series)
        total_height = (
            sum(float(row[item.column]) for item in series) * scale
            if arrangement is BarArrangement.STACKED
            else max(float(row[item.column]) for item in series) * scale
        )
        if annotation_column:
            annotation_lines = str(row[annotation_column]).split(" · ")
            annotation_y = chart_y + chart_height - total_height - 34
            annotation_markup = "".join(
                f'<tspan x="{center_x:.1f}" dy="{0 if index == 0 else 26}">'
                f'{html.escape(line)}</tspan>'
                for index, line in enumerate(annotation_lines)
            )
            groups.append(
                f'<text class="bar-annotation" x="{center_x:.1f}" '
                f'y="{annotation_y:.1f}" text-anchor="middle">'
                f'{annotation_markup}</text>'
            )
        for series_index, item in enumerate(series):
            height = float(row[item.column]) * scale
            x = group_x if arrangement is BarArrangement.STACKED else group_x + series_index * thickness
            y = chart_y + chart_height - height - offset
            groups.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{thickness:.1f}" '
                f'height="{height:.1f}" fill="{_fill(item, series_index)}" '
                f'stroke="{item.color}" stroke-opacity=".5" stroke-width="1.5"/>'
            )
            if arrangement is BarArrangement.STACKED:
                offset += height
    axis_title = (
        f'<text class="bar-axis-title" x="{chart_x}" y="72">'
        f'{html.escape(axis.title)}</text>'
        if axis.title
        else ""
    )
    return f'{axis_title}{"".join(ticks)}{"".join(groups)}'


def _bar_component(
    data: pl.DataFrame,
    *,
    category: str,
    annotation: str | None,
    series: tuple[BarSeries, ...],
    orientation: BarOrientation,
    arrangement: BarArrangement,
    section_heading: str | None,
    axis: NumericAxis,
    axis_maximum: float,
    style: BarChartStyle,
    category_label_angle: float,
    legend_alignment: ChartAlignment,
) -> SvgComponent:
    renderer = (
        _horizontal_bars
        if orientation is BarOrientation.HORIZONTAL
        else _vertical_bars
    )
    visual_bars = renderer(
        data,
        category_column=category,
        annotation_column=annotation,
        series=series,
        arrangement=arrangement,
        axis=axis,
        axis_maximum=axis_maximum,
        style=style,
        category_label_angle=category_label_angle,
    )
    mobile = orientation is BarOrientation.VERTICAL
    section_size = MOBILE_TYPOGRAPHY.section_heading if mobile else 32
    category_size = MOBILE_TYPOGRAPHY.label if mobile else 18
    annotation_size = MOBILE_TYPOGRAPHY.minimum if mobile else 14
    axis_size = MOBILE_TYPOGRAPHY.axis if mobile else 13
    axis_title_size = MOBILE_TYPOGRAPHY.minimum if mobile else 12
    legend_size = MOBILE_TYPOGRAPHY.legend if mobile else 14
    visual = f"""
<defs>{_patterns(series)}</defs>
<style>
.bar-section{{font:700 {section_size}px Georgia,'Times New Roman',serif;fill:{style.text_color}}}
.bar-category,.bar-annotation,.bar-axis,.bar-axis-title,.bar-legend{{font-family:Arial,Helvetica,sans-serif}}
.bar-category{{font-size:{category_size}px;font-weight:700;fill:{style.text_color}}}
.bar-annotation{{font-size:{annotation_size}px;fill:{style.muted_color}}}
.bar-axis{{font-size:{axis_size}px;fill:{style.muted_color}}}
.bar-axis-title{{font-size:{axis_title_size}px;font-weight:700;letter-spacing:1px;fill:{style.muted_color}}}
.bar-legend{{font-size:{legend_size}px;fill:{style.text_color}}}
</style>
{f'<text class="bar-section" x="55" y="23">{html.escape(section_heading)}</text>' if section_heading else ''}
{_legend(series, mobile=mobile, alignment=legend_alignment)}
{visual_bars}
"""
    return SvgComponent(
        visual,
        width=1450,
        height=1170 if orientation is BarOrientation.VERTICAL else 620,
    )


def bar_chart(
    data: pl.DataFrame,
    *,
    category: str,
    series: tuple[BarSeries, ...],
    orientation: BarOrientation,
    portrait_orientation: BarOrientation | None = None,
    category_label_angle: float = 0,
    portrait_category_label_angle: float | None = None,
    legend_alignment: ChartAlignment = ChartAlignment.RIGHT,
    arrangement: BarArrangement,
    title: str,
    subtitle: str,
    section_heading: str | None = None,
    axis: NumericAxis,
    annotation: str | None = None,
    portrait_annotation: str | None = None,
    style: BarChartStyle = BarChartStyle(),
    notes: tuple[str, ...] = (),
    sources: tuple[str, ...] = (),
    description: str = "",
) -> Graphic:
    """Render a configured grouped or stacked bar chart from dataframe columns."""
    _validate_bar_data(data, category, annotation, series)
    if portrait_annotation and portrait_annotation != annotation:
        _validate_bar_data(data, category, portrait_annotation, series)
    maximum = _axis_maximum(data, series, arrangement, axis.tick_step)
    visual = _bar_component(
        data,
        category=category,
        annotation=annotation,
        series=series,
        orientation=orientation,
        arrangement=arrangement,
        section_heading=section_heading,
        axis=axis,
        axis_maximum=maximum,
        style=style,
        category_label_angle=category_label_angle,
        legend_alignment=legend_alignment,
    )
    if portrait_orientation is not None and portrait_orientation is not orientation:
        portrait_visual = _bar_component(
            data,
            category=category,
            annotation=portrait_annotation,
            series=series,
            orientation=portrait_orientation,
            arrangement=arrangement,
            section_heading=section_heading,
            axis=axis,
            axis_maximum=maximum,
            style=style,
            category_label_angle=(
                portrait_category_label_angle
                if portrait_category_label_angle is not None
                else category_label_angle
            ),
            legend_alignment=legend_alignment,
        )
        visual = SvgComponent(
            visual.markup,
            visual.width,
            visual.height,
            portrait_variant=portrait_visual,
        )
    return Graphic(
        title=title,
        subtitle=subtitle,
        visual=visual,
        notes=notes,
        sources=sources,
        description=description,
        metadata={
            "chart_type": "bar",
            "orientation": orientation.value,
            "portrait_orientation": (
                portrait_orientation.value if portrait_orientation else None
            ),
            "arrangement": arrangement.value,
            "axis_maximum": maximum,
        },
    )
