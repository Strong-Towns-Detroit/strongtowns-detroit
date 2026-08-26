"""Data-driven categorical proportional-symbol maps."""

from __future__ import annotations

import base64
import hashlib
import html
import io
import math
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from PIL import Image

from strongtowns_detroit.graphics.detroit import (
    LegendComparator,
    MapLegend,
    MobileMapInset,
    MobileMapPocket,
    map_on_mobile,
)
from strongtowns_detroit.graphics.model import MapMarkerStyle
from strongtowns_detroit.graphics.svg import Graphic, SvgComponent
from strongtowns_detroit.graphics.svg import MobileMapSegment


@dataclass(frozen=True)
class WebMercatorBasemap:
    """Background layers already normalized to EPSG:3857."""

    land_geometry: Any
    roads: gpd.GeoDataFrame
    water: gpd.GeoDataFrame | None = None

    def __post_init__(self) -> None:
        if self.roads.crs is None or self.roads.crs.to_epsg() != 3857:
            raise ValueError("basemap roads must use EPSG:3857")
        if self.water is not None and (
            self.water.crs is None or self.water.crs.to_epsg() != 3857
        ):
            raise ValueError("basemap water must use EPSG:3857")


_REQUIRED_COLUMNS = {
    "point_id",
    "easting",
    "northing",
    "category",
    "category_label",
    "color",
    "magnitude",
    "category_count",
}


def _validate_map_data(data: pl.DataFrame) -> None:
    missing = _REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(f"categorical map data is missing columns: {sorted(missing)}")
    if data.is_empty():
        raise ValueError("categorical map data cannot be empty")
    if data["point_id"].n_unique() != data.height:
        raise ValueError("categorical map point_id values must be unique")
    null_columns = [name for name in _REQUIRED_COLUMNS if data[name].null_count()]
    if null_columns:
        raise ValueError(f"categorical map columns cannot contain nulls: {null_columns}")
    if data.filter(pl.col("magnitude") <= 0).height:
        raise ValueError("categorical map magnitudes must be positive")
    if data.filter(pl.col("category_count") <= 0).height:
        raise ValueError("categorical map category counts must be positive")
    inconsistent = (
        data.group_by("category")
        .agg(
            pl.col("category_label").n_unique().alias("labels"),
            pl.col("color").n_unique().alias("colors"),
        )
        .filter((pl.col("labels") != 1) | (pl.col("colors") != 1))
    )
    if inconsistent.height:
        raise ValueError("each category must have exactly one label and color")


def _marker_magnitudes(data: pl.DataFrame, style: MapMarkerStyle) -> np.ndarray:
    values = data["magnitude"].cast(pl.Float64).to_numpy()
    if style.maximum_magnitude is not None:
        values = np.minimum(values, style.maximum_magnitude)
    return values


def _displace_points(
    coordinates: np.ndarray,
    identifiers: list[str],
    symbol_radii: np.ndarray,
    overlap_fraction: float,
    maximum_displacement: float = 1200.0,
    iterations: int = 180,
) -> tuple[np.ndarray, float]:
    original = coordinates.astype(float, copy=True)
    placed = original.copy()
    for _ in range(iterations):
        moved = False
        for left in range(len(placed)):
            delta = placed[left + 1 :] - placed[left]
            distances = np.linalg.norm(delta, axis=1)
            required = (
                symbol_radii[left] + symbol_radii[left + 1 :]
            ) * (1 - overlap_fraction)
            for offset in np.flatnonzero(distances < required):
                right = left + 1 + int(offset)
                distance = distances[offset]
                if distance < 1e-9:
                    digest = hashlib.sha256(
                        f"{identifiers[left]}|{identifiers[right]}".encode()
                    ).digest()
                    angle = 2 * math.pi * int.from_bytes(digest[:4], "big") / 2**32
                    direction = np.array([math.cos(angle), math.sin(angle)])
                else:
                    direction = delta[offset] / distance
                push = direction * (required[offset] - distance) * 0.52
                placed[left] -= push
                placed[right] += push
                moved = True
        displacement = placed - original
        lengths = np.linalg.norm(displacement, axis=1)
        beyond = lengths > maximum_displacement
        placed[beyond] = (
            original[beyond]
            + displacement[beyond]
            * (maximum_displacement / lengths[beyond])[:, None]
        )
        if not moved:
            break
    maximum_used = float(np.linalg.norm(placed - original, axis=1).max())
    return placed, maximum_used


def _legend_items(data: pl.DataFrame) -> list[tuple[str, int, str]]:
    totals = data.group_by("category", maintain_order=True).agg(
        pl.col("category_label").first(),
        pl.col("color").first(),
        pl.col("category_count").sum().alias("count"),
    )
    return [
        (row["category_label"], int(row["count"]), row["color"])
        for row in totals.iter_rows(named=True)
    ]


def _magnitude_legend_values(
    maximum: float, requested: tuple[float, ...] | None
) -> tuple[float, ...]:
    if requested is None:
        scale_ceiling = max(1.0, math.ceil(maximum / 2) * 2.0)
        return tuple(
            dict.fromkeys((scale_ceiling, scale_ceiling / 2, 1.0))
        )
    return tuple(
        dict.fromkeys(
            [maximum] + [float(level) for level in requested if level <= maximum]
        )
    )


def _desktop_legend(legend: MapLegend) -> str:
    items = legend.ordered_items()
    rows_per_column = max(1, math.ceil(len(items) / 2))
    parts = []
    for index, (label, count, color) in enumerate(items):
        column, row = divmod(index, rows_per_column)
        x, y = 1120 + column * 225, 565 + row * 42
        parts.append(
            f'<rect x="{x}" y="{y}" width="14" height="14" fill="{color}"/>'
            f'<text class="map-small" x="{x + 22}" y="{y + 12}">'
            f"{html.escape(label)}</text>"
            f'<text class="map-count" x="{x + 210}" y="{y + 12}" '
            f'text-anchor="end">{count}</text>'
        )
    return (
        f'<text class="map-section" x="1120" y="520">'
        f"{html.escape(legend.heading)}</text>{''.join(parts)}"
    )


def categorical_proportional_symbol_map(
    data: pl.DataFrame,
    *,
    basemap: WebMercatorBasemap,
    title: str,
    subtitle: str,
    category_legend_heading: str,
    magnitude_legend_heading: str,
    sources: tuple[str, ...] = (),
    description: str = "",
    notes: tuple[str, ...] = (),
    category_order: LegendComparator | None = None,
    magnitude_legend_levels: tuple[float, ...] | None = None,
    marker_style: MapMarkerStyle = MapMarkerStyle(),
    mobile_insets: tuple[MobileMapInset, ...] = (),
    mobile_segments: tuple[MobileMapSegment, ...] = (),
) -> Graphic:
    """Render explicit EPSG:3857 point records and their derived legends.

    ``data`` must contain point_id, easting, northing, category,
    category_label, color, magnitude, and category_count. Marker area is
    proportional to magnitude; category totals sum category_count.
    """
    _validate_map_data(data)
    magnitudes = _marker_magnitudes(data, marker_style)
    marker_areas = magnitudes * marker_style.area_per_unit

    fig, ax = plt.subplots(figsize=(10.7, 7.15), dpi=435)
    fig.patch.set_facecolor("#fffaf0")
    ax.set_facecolor("#fffaf0")
    gpd.GeoSeries([basemap.land_geometry], crs="EPSG:3857").plot(
        ax=ax, color="#ebe5da", edgecolor="none", zorder=1
    )
    if basemap.water is not None and not basemap.water.empty:
        basemap.water.plot(
            ax=ax,
            color="#fffaf0",
            edgecolor="none",
            zorder=2,
        )
    road_styles = {
        "local": (0.13, 0.16),
        "arterial": (0.22, 0.28),
        "major": (0.36, 0.40),
    }
    if "road_class" in basemap.roads.columns:
        for road_class in ("local", "arterial", "major"):
            roads = basemap.roads[
                basemap.roads["road_class"].eq(road_class)
            ]
            if roads.empty:
                continue
            linewidth, alpha = road_styles[road_class]
            roads.plot(
                ax=ax,
                color="#0c2340",
                linewidth=linewidth,
                alpha=alpha,
                zorder=3,
            )
    else:
        basemap.roads.plot(
            ax=ax, color="#0c2340", linewidth=0.22, alpha=0.28, zorder=3
        )
    ax.set_axis_off()
    x_min, y_min, x_max, y_max = basemap.land_geometry.bounds
    x_padding = (x_max - x_min) * 0.01
    y_padding = (y_max - y_min) * 0.01
    ax.set_xlim(x_min - x_padding, x_max + x_padding)
    shift = (y_max - y_min) * 0.02
    ax.set_ylim(
        y_min - y_padding + shift,
        y_max + y_padding + shift,
    )
    fig.tight_layout(pad=0)
    fig.canvas.draw()

    origin = ax.transData.transform((0.0, 0.0))
    kilometer = ax.transData.transform((1000.0, 0.0))
    pixels_per_unit = np.linalg.norm(kilometer - origin) / 1000.0
    radii_pixels = np.sqrt(marker_areas) * fig.dpi / 144.0
    radii_map_units = radii_pixels / pixels_per_unit
    coordinates = np.column_stack(
        (
            data["easting"].cast(pl.Float64).to_numpy(),
            data["northing"].cast(pl.Float64).to_numpy(),
        )
    )
    placed, maximum_displacement = _displace_points(
        coordinates,
        [str(value) for value in data["point_id"].to_list()],
        radii_map_units,
        marker_style.overlap_fraction,
    )
    for index, row in enumerate(data.iter_rows(named=True)):
        ax.scatter(
            [placed[index, 0]],
            [placed[index, 1]],
            s=marker_areas[index],
            marker="o",
            c=row["color"],
            edgecolors="#fffaf0",
            linewidths=0.7,
            alpha=marker_style.opacity,
            zorder=5,
        )

    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format="jpeg",
        bbox_inches="tight",
        pad_inches=0,
        facecolor="#fffaf0",
        pil_kwargs={"quality": 91, "optimize": True},
    )
    image_width = Image.open(io.BytesIO(buffer.getvalue())).width
    plt.close(fig)
    image = base64.b64encode(buffer.getvalue()).decode()
    radius_per_sqrt_unit = (
        math.sqrt(marker_style.area_per_unit) * 435 / 144.0 * 1015 / image_width
    )
    maximum = float(magnitudes.max())
    levels = _magnitude_legend_values(maximum, magnitude_legend_levels)
    category_legend = MapLegend(
        heading=category_legend_heading,
        items=_legend_items(data),
        order=category_order,
    )
    level_rows = tuple(
        ((str(int(level)) if level.is_integer() else f"{level:g}"), level)
        for level in levels
    )
    visual = SvgComponent(
        f"""
<style>
.map-section{{font:700 28px Georgia,'Times New Roman',serif;fill:#0c2340}}
.map-small,.map-count,.map-effect-heading,.map-effect-level{{font-family:Arial,Helvetica,sans-serif;fill:#0c2340}}
.map-small,.map-count{{font-size:11px}}.map-count{{font-weight:700}}
.map-effect-heading{{font-size:13px;font-weight:700;letter-spacing:1px}}
.map-effect-level{{font-size:11px;font-weight:700}}
</style>
<image href="data:image/jpeg;base64,{image}" x="48" y="205" width="1015" height="720" preserveAspectRatio="xMidYMid meet"/>
<text class="map-effect-heading" x="1120" y="410">{html.escape(magnitude_legend_heading)}</text>
{_desktop_effect_legend(level_rows, radius_per_sqrt_unit)}
{_desktop_legend(category_legend)}
""",
        1600,
        780,
        min_y=180,
    )
    graphic = Graphic(
        title=title,
        subtitle=subtitle,
        visual=visual,
        notes=notes,
        sources=sources,
        description=description,
        metadata={
            "maximum_magnitude": maximum,
            "magnitude_legend_ceiling": levels[0],
            "radius_per_sqrt_unit": radius_per_sqrt_unit,
            "maximum_displacement": maximum_displacement,
            "point_count": data.height,
        },
    )
    return map_on_mobile(
        graphic,
        legend=category_legend,
        insets=(
            *mobile_insets,
            MobileMapInset.effect_size_legend(
                pocket=MobileMapPocket.LOWER_RIGHT,
                heading=magnitude_legend_heading,
                levels=level_rows,
                radius_per_sqrt_unit=radius_per_sqrt_unit,
            ),
        ),
        segments=mobile_segments,
    )


def _desktop_effect_legend(
    levels: tuple[tuple[str, float], ...], radius_per_sqrt_unit: float
) -> str:
    baseline = 480.0
    circles = []
    labels = []
    middle_index = (len(levels) - 1) / 2
    for index, (label, value) in enumerate(levels):
        radius = radius_per_sqrt_unit * math.sqrt(value)
        top = baseline - 2 * radius
        label_y = top + (index - middle_index) * 8
        circles.append(
            f'<circle cx="1142" cy="{baseline - radius:.2f}" r="{radius:.2f}" '
            'fill="#0c2340" fill-opacity=".16" stroke="#0c2340"/>'
        )
        labels.append(
            f'<polyline points="1142,{top:.2f} 1172,{top:.2f} '
            f'1180,{label_y:.2f}" fill="none" stroke="#526276" '
            'stroke-width=".8"/>'
            f'<text class="map-effect-level" x="1186" y="{label_y + 4:.2f}">'
            f"{html.escape(label)}</text>"
        )
    return "".join(circles + labels)
