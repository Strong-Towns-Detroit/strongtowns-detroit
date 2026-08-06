"""Small, composable SVG/HTML building blocks for forum exhibits.

The helpers deliberately return strings rather than owning a chart renderer.
Generators remain responsible for their analytical content and geometry while
sharing the visual grammar that should stay consistent across exports.
"""

from __future__ import annotations

import html
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CREAM = "#fffaf0"
NAVY = "#0c2340"
RED = "#c83a3a"
MUTED = "#526276"
PALE = "#e4dfd6"


def forum_css(
    *,
    title_size: int = 57,
    dek_size: int = 24,
    metric_size: int = 72,
    section_size: int = 27,
    note_size: int = 17,
    legend_size: int = 15,
    source_size: int = 13,
    extra_sans: Iterable[str] = (),
    extra_serif: Iterable[str] = (),
    extra_rules: str = "",
    cream: str = CREAM,
    navy: str = NAVY,
    red: str = RED,
    muted: str = MUTED,
) -> str:
    """Return the common typography and semantic SVG class rules."""
    sans = [
        ".kicker", ".metric-label", ".note", ".legend", ".source",
        *extra_sans,
    ]
    serif = [".title", ".dek", ".metric", ".section-title", *extra_serif]
    return (
        f".paper{{fill:{cream}}}"
        f"{','.join(sans)}{{font-family:Arial,Helvetica,sans-serif}}"
        f"{','.join(serif)}{{font-family:Georgia,'Times New Roman',serif;"
        f"fill:{navy}}}"
        f".kicker{{font-size:16px;font-weight:700;letter-spacing:3px;"
        f"fill:{red}}}"
        f".title{{font-size:{title_size}px;font-weight:700}}"
        f".dek{{font-size:{dek_size}px;fill:#48596d}}"
        f".metric{{font-size:{metric_size}px;font-weight:700}}"
        ".metric-label{font-size:15px;font-weight:700;letter-spacing:1.2px;"
        f"fill:{muted}}}"
        f".section-title{{font-size:{section_size}px;font-weight:700}}"
        f".note{{font-size:{note_size}px;fill:#34475d}}"
        f".legend{{font-size:{legend_size}px;fill:{navy}}}"
        f".source{{font-size:{source_size}px;fill:{muted}}}"
        f"{extra_rules}"
    )


def title_block(
    title: str,
    subtitle: str,
    *,
    x: int = 52,
    title_y: int = 116,
    subtitle_x: int | None = None,
    subtitle_y: int = 158,
    subtitle_class: str = "dek",
) -> str:
    """Render the standard exhibit title and subtitle."""
    return (
        f'<text class="title" x="{x}" y="{title_y}">'
        f"{html.escape(title)}</text>"
        f'<text class="{subtitle_class}" x="{subtitle_x or x + 3}" '
        f'y="{subtitle_y}">{html.escape(subtitle)}</text>'
    )


def map_frame(
    image_data_uri: str,
    *,
    x: int = 48,
    y: int = 205,
    width: int = 1015,
    height: int = 680,
) -> str:
    """Place a rendered map in the standard map column."""
    return (
        f'<image href="{image_data_uri}" x="{x}" y="{y}" '
        f'width="{width}" height="{height}" '
        'preserveAspectRatio="xMidYMid meet"/>'
    )


def metric_block(
    value: str,
    label_lines: Iterable[str],
    detail: str | None = None,
    *,
    x: int = 1120,
    value_y: int = 270,
    label_y: int = 301,
    label_line_height: int = 20,
    detail_gap: int = 33,
) -> str:
    """Render the large value, uppercase label, and supporting count."""
    labels = list(label_lines)
    label_markup = "".join(
        f'<text class="metric-label" x="{x + 3}" '
        f'y="{label_y + i * label_line_height}">'
        f"{html.escape(line)}</text>"
        for i, line in enumerate(labels)
    )
    detail_y = label_y + (len(labels) - 1) * label_line_height + detail_gap
    detail_markup = (
        f'<text class="note" x="{x + 3}" y="{detail_y}">'
        f"{html.escape(detail)}</text>"
        if detail is not None
        else ""
    )
    return (
        f'<text class="metric" x="{x}" y="{value_y}">'
        f"{html.escape(value)}</text>"
        f"{label_markup}"
        f"{detail_markup}"
    )


@dataclass(frozen=True)
class LegendItem:
    label: str
    color: str


def swatch_legend(
    items: Iterable[LegendItem],
    *,
    positions: Iterable[int],
    y: int = 918,
    size: int = 18,
    text_gap: int = 9,
) -> str:
    """Render positioned square swatches with labels."""
    return "".join(
        f'<rect x="{x}" y="{y}" width="{size}" height="{size}" '
        f'fill="{item.color}"/>'
        f'<text class="legend" x="{x + size + text_gap}" '
        f'y="{y + size - 3}">{html.escape(item.label)}</text>'
        for item, x in zip(items, positions)
    )


def source_lines(
    lines: Iterable[str],
    *,
    x: int = 55,
    first_y: int = 1038,
    line_height: int = 26,
) -> str:
    """Render escaped source/method lines at a predictable baseline."""
    return "".join(
        f'<text class="source" x="{x}" y="{first_y + i * line_height}">'
        f"{html.escape(line)}</text>"
        for i, line in enumerate(lines)
    )


def ghost_hatch_pattern(
    pattern_id: str = "ghost-parking", *, color: str = RED
) -> str:
    """Continuous architectural-wireframe hatch used for unrealized quantity."""
    return (
        f'<pattern id="{html.escape(pattern_id)}" width="10" height="10" '
        'patternUnits="userSpaceOnUse">'
        f'<rect width="10" height="10" fill="{color}" fill-opacity=".055"/>'
        f'<path d="M-2 2 L2 -2 M0 10 L10 0 M8 12 L12 8" fill="none" '
        f'stroke="{color}" stroke-width="1.2" stroke-opacity=".52"/>'
        "</pattern>"
    )


def html_document(
    title: str,
    svg: str,
    *,
    width: int,
    height: int,
    background: str = CREAM,
) -> str:
    """Wrap an inline SVG in the standard responsive and printable document."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        f"<style>html,body{{margin:0;background:{background}}}"
        f"main{{width:min(100%,{width}px);margin:auto}}"
        "svg{display:block;width:100%;height:auto}"
        f"@media print{{@page{{size:{width / 100:g}in "
        f"{height / 100:g}in;margin:0}}}}</style></head>"
        f"<body><main>{svg}</main></body></html>"
    )


def write_svg_bundle(
    output_dir: Path,
    stem: str,
    title: str,
    svg: str,
    *,
    width: int,
    height: int,
    png_width: int | None = None,
    background: str = CREAM,
) -> None:
    """Write shareable SVG/HTML and PNG when librsvg is available."""
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / f"{stem}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    (output_dir / f"{stem}.html").write_text(
        html_document(
            title, svg, width=width, height=height, background=background
        ),
        encoding="utf-8",
    )
    renderer = shutil.which("rsvg-convert")
    if renderer:
        subprocess.run(
            [
                renderer,
                "--width",
                str(png_width or width * 2),
                "--output",
                str(output_dir / f"{stem}.png"),
                str(svg_path),
            ],
            check=True,
        )
