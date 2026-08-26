"""Opinionated mobile layouts for maps of Detroit."""

from __future__ import annotations

import html
import math
import textwrap
from dataclasses import dataclass, replace
from enum import Enum
from functools import cmp_to_key
from typing import Callable, Mapping
from collections.abc import Sequence

from strongtowns_detroit.graphics.svg import (
    Graphic,
    MobileMapLayout,
    MobileMapSegment,
    SvgComponent,
    SvgRegion,
)
from strongtowns_detroit.graphics.typography import MOBILE_TYPOGRAPHY


class MobileMapPocket(str, Enum):
    """Stable negative-space pockets in the standard Detroit parcel map."""

    LOWER_LEFT = "lower_left"
    LOWER_RIGHT = "lower_right"


class MobileMapInsetKind(str, Enum):
    """Reusable kinds of content that can occupy a Detroit map pocket."""

    HERO_STATISTIC = "hero_statistic"
    EFFECT_SIZE_LEGEND = "effect_size_legend"
    TEXT_BLOCK = "text_block"


LegendItem = tuple[str, int, str]
LegendComparator = Callable[[LegendItem, LegendItem], int]


def _compare_labels(left: LegendItem, right: LegendItem) -> int:
    return (left[0] > right[0]) - (left[0] < right[0])


def _ascending_count(left: LegendItem, right: LegendItem) -> int:
    if left[1] != right[1]:
        return (left[1] > right[1]) - (left[1] < right[1])
    return _compare_labels(left, right)


def _descending_count(left: LegendItem, right: LegendItem) -> int:
    if left[1] != right[1]:
        return (right[1] > left[1]) - (right[1] < left[1])
    return _compare_labels(left, right)


class LegendOrders:
    """Reusable comparators for counted legend items."""

    ASCENDING: LegendComparator = staticmethod(_ascending_count)
    DESCENDING: LegendComparator = staticmethod(_descending_count)


@dataclass(frozen=True)
class MapLegend:
    """A complete counted legend supplied to a map layout."""

    heading: str
    items: Sequence[LegendItem]
    order: LegendComparator | None = None

    def ordered_items(self) -> list[LegendItem]:
        items = list(self.items)
        return sorted(items, key=cmp_to_key(self.order)) if self.order else items


def build_map_graphic(
    *,
    visual: SvgComponent,
    title: str,
    subtitle: str = "",
    notes: tuple[str, ...] = (),
    sources: tuple[str, ...] = (),
    description: str = "",
    metadata: Mapping[str, object] | None = None,
) -> Graphic:
    """Build a semantic map graphic from a rendered visual and its copy."""
    return Graphic(
        title=title,
        subtitle=subtitle,
        visual=visual,
        notes=notes,
        sources=sources,
        description=description,
        metadata=metadata if metadata is not None else {},
    )


@dataclass(frozen=True)
class _MobileMapPocketArea:
    left: float
    right: float
    top: float


@dataclass(frozen=True)
class _MobileMapContentBox:
    width: float

    def left_aligned_to(self, right: float) -> float:
        return right - self.width


_EFFECT_SIZE_GRAPHIC_BOX = _MobileMapContentBox(width=100)
_EFFECT_SIZE_HEADING_OVERHANG = 10


def bza_hearing_marker_area(hearing_count: float) -> float:
    """Return the exact Matplotlib marker area used by the BZA maps."""
    # 100 square points gives the dense maps more visual presence while
    # keeping area—not radius—proportional to the number of hearings.
    return 100.0 * min(max(float(hearing_count), 1.0), 10.0)


def bza_hearing_marker_radius(
    hearing_count: float,
    *,
    raster_dpi: float,
    raster_width: float,
    embedded_width: float,
) -> float:
    """Return a BZA map marker radius in the embedding SVG's coordinates.

    Matplotlib scatter sizes are square points. Its circular marker has a
    radius of half ``sqrt(area)`` points; the remaining factors convert that
    radius through the saved raster and into the SVG image's displayed width.
    A legend placed beside that image in the same SVG coordinate system will
    therefore receive the exact same final output scaling as the map marker.
    """
    if raster_dpi <= 0 or raster_width <= 0 or embedded_width <= 0:
        raise ValueError("marker conversion dimensions must be positive")
    radius_in_raster_pixels = (
        math.sqrt(bza_hearing_marker_area(hearing_count)) * raster_dpi / 144.0
    )
    return radius_in_raster_pixels * embedded_width / raster_width


@dataclass(frozen=True)
class MobileMapInset:
    """Optional content placed in one of the map's negative-space pockets."""

    kind: MobileMapInsetKind
    pocket: MobileMapPocket
    value: str = ""
    label: tuple[str, ...] = ()
    heading: str = ""
    levels: tuple[tuple[str, float], ...] = ()
    radius_per_sqrt_unit: float = 0.0
    text: str | tuple[str, ...] = ""

    @classmethod
    def hero_statistic(
        cls,
        *,
        pocket: MobileMapPocket,
        value: str,
        label: tuple[str, ...],
    ) -> MobileMapInset:
        return cls(
            kind=MobileMapInsetKind.HERO_STATISTIC,
            pocket=pocket,
            value=value,
            label=label,
        )

    @classmethod
    def effect_size_legend(
        cls,
        *,
        pocket: MobileMapPocket,
        heading: str,
        levels: tuple[tuple[str, float], ...],
        radius_per_sqrt_unit: float,
    ) -> MobileMapInset:
        return cls(
            kind=MobileMapInsetKind.EFFECT_SIZE_LEGEND,
            pocket=pocket,
            heading=heading,
            levels=levels,
            radius_per_sqrt_unit=radius_per_sqrt_unit,
        )

    @classmethod
    def text_block(
        cls,
        *,
        pocket: MobileMapPocket,
        text: str | tuple[str, ...],
    ) -> MobileMapInset:
        """Place automatically wrapped or explicitly lined editorial text."""
        return cls(
            kind=MobileMapInsetKind.TEXT_BLOCK,
            pocket=pocket,
            text=text,
        )

    def __post_init__(self) -> None:
        if self.kind is MobileMapInsetKind.HERO_STATISTIC:
            if not self.value or not self.label:
                raise ValueError("a hero statistic requires a value and label")
        elif self.kind is MobileMapInsetKind.EFFECT_SIZE_LEGEND:
            if not self.heading or not self.levels:
                raise ValueError("an effect-size legend requires a heading and levels")
            if any(amount <= 0 for _, amount in self.levels):
                raise ValueError("effect-size legend levels must be positive")
            if self.radius_per_sqrt_unit <= 0:
                raise ValueError(
                    "an effect-size legend requires a positive radius scale"
                )
        elif self.kind is MobileMapInsetKind.TEXT_BLOCK:
            lines = (self.text,) if isinstance(self.text, str) else self.text
            if not lines or not all(
                isinstance(line, str) and line.strip() for line in lines
            ):
                raise ValueError("a text-block inset requires nonempty text")


def _render_mobile_map_insets(insets: tuple[MobileMapInset, ...]) -> str:
    local_minimum = MOBILE_TYPOGRAPHY.local_minimum(1570 / 1047)
    areas = {
        MobileMapPocket.LOWER_LEFT: _MobileMapPocketArea(70, 350, 735),
        MobileMapPocket.LOWER_RIGHT: _MobileMapPocketArea(700, 915, 735),
    }
    if len({inset.pocket for inset in insets}) != len(insets):
        raise ValueError("each mobile map pocket can contain only one inset")
    inset_parts = []
    for inset in insets:
        area = areas[inset.pocket]
        x, y = area.left, area.top
        node_name = f"inset-{inset.pocket.value.replace('_', '-')}"
        if inset.kind is MobileMapInsetKind.HERO_STATISTIC:
            labels = "".join(
                f'<tspan x="{x}" dy="25">{html.escape(line)}</tspan>'
                for line in inset.label
            )
            inset_parts.append(
                '<g class="mobile-only mobile-map-inset" '
                f'data-layout-node="{node_name}">'
                f'<text class="mobile-inset-value" data-layout-node="value" '
                f'x="{x}" y="{y}">'
                f'{html.escape(inset.value)}</text>'
                f'<text class="mobile-inset-label" data-layout-node="label" '
                f'x="{x}" y="{y + 28}">'
                f'{labels}</text></g>'
            )
            continue

        if inset.kind is MobileMapInsetKind.TEXT_BLOCK:
            lines = (
                textwrap.wrap(
                    inset.text,
                    width=31,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                if isinstance(inset.text, str)
                else list(inset.text)
            )
            text_lines = "".join(
                f'<tspan x="{x}" dy="{0 if index == 0 else 29}">'
                f'{html.escape(line)}</tspan>'
                for index, line in enumerate(lines)
            )
            inset_parts.append(
                '<g class="mobile-only mobile-map-inset" '
                f'data-layout-node="{node_name}">'
                f'<text class="mobile-inset-text" data-layout-node="text" '
                f'x="{x}" y="{y}">{text_lines}</text></g>'
            )
            continue

        baseline = y + 100
        circles = []
        level_labels = []
        graphic_box_left = _EFFECT_SIZE_GRAPHIC_BOX.left_aligned_to(area.right)
        circle_x = 40
        line_elbow_x = 76
        line_end_x = 86
        number_x = 92
        middle_index = (len(inset.levels) - 1) / 2
        for index, (label, amount) in enumerate(inset.levels):
            radius = inset.radius_per_sqrt_unit * amount ** 0.5
            top = baseline - 2 * radius
            label_center_y = top + (index - middle_index) * 10
            circles.append(
                f'<circle cx="{circle_x}" cy="{baseline - radius}" r="{radius:.2f}" '
                'fill="#0c2340" fill-opacity=".16" stroke="#0c2340"/>'
            )
            level_labels.append(
                f'<polyline class="mobile-inset-leader" points="'
                f'{circle_x},{top:.2f} {line_elbow_x},{top:.2f} '
                f'{line_end_x},{label_center_y:.2f}"/>'
                f'<text class="mobile-inset-level" x="{number_x}" '
                f'y="{label_center_y + 5:.2f}" dominant-baseline="middle">'
                f'{html.escape(label)}</text>'
            )
        inset_parts.append(
            '<g class="mobile-only mobile-map-inset" '
            f'data-layout-node="{node_name}">'
            f'<text class="mobile-inset-heading" data-layout-node="heading" '
            f'x="{area.right + _EFFECT_SIZE_HEADING_OVERHANG}" '
            f'y="{y + 40}" text-anchor="end">'
            f'{html.escape(inset.heading)}</text>'
            f'<g class="mobile-inset-graphic-box" data-layout-node="graphic" '
            f'transform="translate({graphic_box_left} 0)">'
            f'{"".join(circles)}{"".join(level_labels)}</g></g>'
        )
    if not inset_parts:
        return ""
    return f"""
<style>
.mobile-only{{display:none}}
.mobile-inset-value{{font:700 66px Georgia,'Times New Roman',serif;fill:#0c2340}}
.mobile-inset-label,.mobile-inset-heading,.mobile-inset-level{{font-family:Arial,Helvetica,sans-serif;fill:#526276}}
.mobile-inset-label{{font-size:{local_minimum}px;font-weight:700;letter-spacing:1px}}
.mobile-inset-heading{{font-size:{local_minimum}px;font-weight:700;letter-spacing:1px}}
.mobile-inset-level{{font-size:{local_minimum}px;font-weight:700}}
.mobile-inset-text{{font:600 21px Georgia,'Times New Roman',serif;fill:#0c2340}}
.mobile-inset-leader{{fill:none;stroke:#526276;stroke-width:.8}}
</style>
{''.join(inset_parts)}
"""


def map_on_mobile(
    graphic: Graphic,
    *,
    legend: MapLegend | None = None,
    map_height: float | None = None,
    insets: tuple[MobileMapInset, ...] = (),
    segments: tuple[MobileMapSegment, ...] = (),
) -> Graphic:
    """Keep a map and its inline legend; omit its analytical sidebar."""
    legend_markup = _render_mobile_map_legend(legend) if legend else ""
    legend_height = None
    if legend:
        rows = max(1, math.ceil(len(legend.items) / 3))
        spacing = 44 if rows > 6 else 48
        legend_height = 110 + (rows - 1) * spacing
    map_region = (
        SvgRegion(32, 220, 1047, map_height or 680)
        if legend
        else SvgRegion(32, 180, 1047, map_height or 780)
    )
    visual = replace(
        graphic.visual,
        markup=(
            graphic.visual.markup
            + legend_markup
            + _render_mobile_map_insets(insets)
        ),
        mobile_map_layout=MobileMapLayout(
            map_region=map_region,
            legend_region=(
                SvgRegion(0, 980, 1080, legend_height)
                if legend_height is not None
                else None
            ),
            segments=segments,
        ),
    )
    return replace(graphic, visual=visual)


def _render_mobile_map_legend(legend: MapLegend) -> str:
    """Render a completed map legend into the standard mobile legend region."""
    items = legend.ordered_items()
    legend_items = []
    rows_per_column = max(1, math.ceil(len(items) / 3))
    row_spacing = 44 if rows_per_column > 6 else 48
    local_minimum = MOBILE_TYPOGRAPHY.local_minimum(1472 / 1080)
    for index, (label, count, color) in enumerate(items):
        column, row = divmod(index, rows_per_column)
        x = 32 + column * 350
        y = 1075 + row * row_spacing
        legend_items.append(
            f'<rect x="{x}" y="{y - 15}" width="16" height="16" '
            f'fill="{color}"/>'
            f'<text class="mobile-legend-label" x="{x + 26}" y="{y}">'
            f'{html.escape(label)}</text>'
            f'<text class="mobile-legend-count" x="{x + 325}" y="{y}" '
            f'text-anchor="end">{count}</text>'
        )
    mobile_legend = f"""
<style>
.mobile-legend-heading{{font:700 34px Georgia,'Times New Roman',serif;fill:#0c2340}}
.mobile-legend-label,.mobile-legend-count{{font:{local_minimum}px Arial,Helvetica,sans-serif;fill:#0c2340}}
.mobile-legend-count{{font-weight:700}}
</style>
<g data-layout-node="categories">
<text class="mobile-legend-heading" x="32" y="1025">{html.escape(legend.heading)}</text>
{''.join(legend_items)}
</g>
"""
    return mobile_legend


def wide_map_with_legend_on_mobile(
    graphic: Graphic, *, items: list[tuple[str, str]]
) -> Graphic:
    """Crop internal whitespace and use the standard Detroit mobile slot."""
    legend_items = []
    for index, (label, color) in enumerate(items):
        x = 42 + index * 205
        legend_items.append(
            f'<rect x="{x}" y="1007" width="22" height="22" fill="{color}"/>'
            f'<text class="mobile-map-legend" x="{x + 32}" y="1025">'
            f'{html.escape(label)}</text>'
        )
    local_minimum = MOBILE_TYPOGRAPHY.local_minimum(1472 / 1080)
    mobile_legend = f"""
<style>.mobile-map-legend{{font:700 {local_minimum}px Arial,Helvetica,sans-serif;fill:#0c2340}}</style>
{''.join(legend_items)}
"""
    visual = replace(
        graphic.visual,
        markup=graphic.visual.markup + mobile_legend,
        mobile_map_layout=MobileMapLayout(
            map_region=SvgRegion(150, 170, 1100, 730),
            legend_region=SvgRegion(0, 970, 1080, 90),
        ),
    )
    return replace(graphic, visual=visual)
