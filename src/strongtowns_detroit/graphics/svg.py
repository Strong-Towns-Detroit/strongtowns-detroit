"""SVG-backed composition and bundle output for static HTML graphics."""

from __future__ import annotations

import base64
import html
import shutil
import subprocess
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping

from strongtowns_detroit.graphics.model import (
    CONFERENCE_LANDSCAPE,
    AspectRatio,
    GraphicTheme,
)
from strongtowns_detroit.graphics.typography import MOBILE_TYPOGRAPHY


@dataclass(frozen=True)
class SvgRegion:
    """A meaningful region of an SVG visual that can be reflowed."""

    min_x: float
    min_y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("SVG region dimensions must be positive")


@dataclass(frozen=True)
class MobileMapLayout:
    """One centered mobile composition containing a map and its siblings."""

    map_region: SvgRegion
    legend_region: SvgRegion | None = None
    map_width: float = 1570
    legend_width: float = 1472
    gap: float = 4
    map_top_bleed: float = 20
    segments: tuple[MobileMapSegment, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.map_width <= 0 or self.legend_width <= 0:
            raise ValueError("mobile map slot widths must be positive")
        if self.gap < 0 or self.map_top_bleed < 0:
            raise ValueError("mobile map gap and top bleed cannot be negative")


@dataclass(frozen=True)
class SvgComponent:
    """Trusted SVG markup with its own local coordinate system."""

    markup: str
    width: float
    height: float
    min_x: float = 0
    min_y: float = 0
    portrait_regions: tuple[SvgRegion, ...] = field(default_factory=tuple)
    portrait_margin: float | None = None
    mobile_map_layout: MobileMapLayout | None = None
    portrait_variant: SvgComponent | None = None


@dataclass(frozen=True)
class MobileMapSegment:
    """Independent content placed after a mobile map's legend."""

    name: str
    content: SvgComponent
    output_width: float = 1472

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("-", "_").isidentifier():
            raise ValueError("mobile map segment name must be a simple identifier")
        if self.output_width <= 0:
            raise ValueError("mobile map segment output width must be positive")


@dataclass(frozen=True)
class Graphic:
    """Semantic inputs for a complete static graphic."""

    title: str | tuple[str, ...]
    visual: SvgComponent
    subtitle: str = ""
    kicker: str = "STRONG TOWNS DETROIT"
    notes: tuple[str, ...] = field(default_factory=tuple)
    sources: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        lines = (self.title,) if isinstance(self.title, str) else self.title
        if not lines or not all(isinstance(line, str) and line for line in lines):
            raise ValueError("graphic title must contain one or more nonempty lines")

    @property
    def title_text(self) -> str:
        """Plain-text title used for accessibility and build metadata."""
        return self.title if isinstance(self.title, str) else " ".join(self.title)


@lru_cache(maxsize=1)
def _brand_mark_data_uri() -> str:
    asset = Path(__file__).with_name("assets") / "strong-towns-detroit-flag.png"
    encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


_LAYOUT_ATTRIBUTES = frozenset(
    {
        "x",
        "y",
        "width",
        "height",
        "transform",
        "text-anchor",
        "dominant-baseline",
    }
)


def apply_layout_sidecar(svg: str, sidecar: Mapping[str, object]) -> str:
    """Apply validated editor-owned layout attributes to semantic SVG nodes."""
    if sidecar.get("schema_version") != 1:
        raise ValueError("unsupported graphic layout sidecar schema")
    nodes = sidecar.get("nodes")
    if not isinstance(nodes, Mapping):
        raise ValueError("graphic layout sidecar must contain a nodes mapping")

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.fromstring(svg)
    applied: set[str] = set()

    def visit(element: ET.Element, parent_path: str = "") -> None:
        segment = element.attrib.get("data-layout-node")
        path = (
            f"{parent_path}.{segment}"
            if parent_path and segment
            else segment or parent_path
        )
        if segment and path in nodes:
            node = nodes[path]
            if not isinstance(node, Mapping):
                raise ValueError(f"layout node {path!r} must be a mapping")
            attributes = node.get("attributes", {})
            if not isinstance(attributes, Mapping):
                raise ValueError(
                    f"layout node {path!r} attributes must be a mapping"
                )
            unsupported = set(attributes) - _LAYOUT_ATTRIBUTES
            if unsupported:
                raise ValueError(
                    f"unsupported layout attributes for {path!r}: "
                    f"{sorted(unsupported)}"
                )
            for name, value in attributes.items():
                if value is None:
                    element.attrib.pop(name, None)
                elif isinstance(value, (str, int, float)):
                    element.set(name, str(value))
                else:
                    raise ValueError(
                        f"layout attribute {path}.{name} must be scalar or null"
                    )
            applied.add(path)
        for child in element:
            visit(child, path)

    visit(root)
    missing = set(nodes) - applied
    if missing:
        raise ValueError(f"layout sidecar references unknown nodes: {sorted(missing)}")
    return ET.tostring(root, encoding="unicode")


def _text_lines(text: str, width: int) -> list[str]:
    return textwrap.wrap(
        text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]


def _balanced_text_lines(text: str, width: int) -> list[str]:
    """Wrap into the fewest possible lines, then balance their lengths."""
    words = text.split()
    if not words:
        return [""]
    best: list[tuple[int, int, list[str]] | None] = [None] * (len(words) + 1)
    best[len(words)] = (0, 0, [])
    for start in range(len(words) - 1, -1, -1):
        line = ""
        candidates: list[tuple[int, int, list[str]]] = []
        for end in range(start, len(words)):
            line = f"{line} {words[end]}".strip()
            if len(line) > width and end > start:
                break
            remainder = best[end + 1]
            if remainder is None:
                continue
            line_count, raggedness, lines = remainder
            candidates.append(
                (
                    line_count + 1,
                    raggedness + (width - len(line)) ** 2,
                    [line, *lines],
                )
            )
        best[start] = min(candidates, key=lambda item: (item[0], item[1]))
    return best[0][2] if best[0] is not None else [text]


def _svg_text_lines(
    lines: Iterable[str],
    *,
    css_class: str,
    x: float,
    y: float,
    line_height: float,
) -> str:
    escaped = [html.escape(line) for line in lines]
    if not escaped:
        return ""
    tspans = [f'<tspan x="{x:g}" y="{y:g}">{escaped[0]}</tspan>']
    tspans.extend(
        f'<tspan x="{x:g}" dy="{line_height:g}">{line}</tspan>'
        for line in escaped[1:]
    )
    return f'<text class="{css_class}">{"".join(tspans)}</text>'


def render_graphic_svg(
    graphic: Graphic,
    *,
    aspect_ratio: AspectRatio = CONFERENCE_LANDSCAPE,
    theme: GraphicTheme = GraphicTheme(),
) -> str:
    """Render a complete SVG document from semantic graphic components."""
    canvas_width = 1600
    canvas_height = round(canvas_width * aspect_ratio.height / aspect_ratio.width)
    portrait = aspect_ratio.orientation == "portrait"
    visual = (
        graphic.visual.portrait_variant
        if portrait and graphic.visual.portrait_variant is not None
        else graphic.visual
    )
    margin = 64 if portrait else 52
    title_size = 72 if portrait else 56
    title_chars = 38 if portrait else 52
    title_line_height = title_size * 1.08
    title_lines = (
        list(graphic.title)
        if isinstance(graphic.title, tuple)
        else _balanced_text_lines(graphic.title, title_chars)
    )
    title_y = 126
    title_bottom = title_y + (len(title_lines) - 1) * title_line_height
    subtitle_y = title_bottom + (50 if portrait else 43)
    visual_y = subtitle_y + (55 if graphic.subtitle else 25)
    note_width = 100 if portrait else 190
    source_width = 112 if portrait else 210
    note_lines = [
        line for note in graphic.notes for line in _text_lines(note, note_width)
    ]
    source_lines = [
        line
        for source in graphic.sources
        for line in _text_lines(source, source_width)
    ]
    footer_line_count = len(note_lines) + len(source_lines)
    footer_line_height = 30 if portrait else 25
    footer_height = max(80, 28 + footer_line_count * footer_line_height)
    visual_bottom = canvas_height - footer_height - 30
    visual_height = max(100, visual_bottom - visual_y)
    visual_width = canvas_width - margin * 2

    if portrait and visual.mobile_map_layout is not None:
        layout = visual.mobile_map_layout
        slots = [
            ("map", layout.map_region, layout.map_width, visual.markup)
        ]
        if layout.legend_region is not None:
            slots.append(
                ("legend", layout.legend_region, layout.legend_width, visual.markup)
            )
        slots.extend(
            (
                f"segment-{segment.name}",
                SvgRegion(
                    segment.content.min_x,
                    segment.content.min_y,
                    segment.content.width,
                    segment.content.height,
                ),
                segment.output_width,
                segment.content.markup,
            )
            for segment in layout.segments
        )
        slot_heights = [
            width * region.height / region.width
            for _, region, width, _ in slots
        ]
        composition_height = sum(slot_heights) + layout.gap * max(
            0, len(slots) - 1
        )
        # Treat the map, its in-map pockets, legend, and following segments as
        # one visual object. Centering that object in the available region
        # shares unused space above and below it instead of allowing title
        # length to push the entire composition down line-for-line.
        composition_offset = max(0, (visual_height - composition_height) / 2)
        slot_y = visual_y + composition_offset
        composition_y = slot_y
        visual_parts = []
        for (
            (slot_name, region, slot_width, slot_markup),
            slot_height,
        ) in zip(slots, slot_heights):
            slot_x = (canvas_width - slot_width) / 2
            if slot_name == "map" and layout.map_top_bleed:
                bleed = layout.map_top_bleed
                clip_id = "mobile-map-top-bleed"
                slot_content = (
                    f'<defs><clipPath id="{clip_id}" '
                    'clipPathUnits="userSpaceOnUse">'
                    f'<rect x="{region.min_x:g}" '
                    f'y="{region.min_y - bleed:g}" width="{region.width:g}" '
                    f'height="{region.height + bleed:g}"/>'
                    '</clipPath></defs>'
                    f'<g clip-path="url(#{clip_id})">'
                    f'{slot_markup}</g>'
                )
                overflow = ' overflow="visible"'
            else:
                slot_content = slot_markup
                overflow = ""
            visual_parts.append(
                f'<svg class="mobile-layout-slot" data-layout-node="{slot_name}" '
                f'x="{slot_x:g}" y="{slot_y:g}" '
                f'width="{slot_width:g}" height="{slot_height:g}" '
                f'viewBox="{region.min_x:g} {region.min_y:g} '
                f'{region.width:g} {region.height:g}" '
                f'preserveAspectRatio="xMidYMin meet"{overflow}>'
                f'{slot_content}</svg>'
            )
            slot_y += slot_height + layout.gap
        clip_id = "mobile-map-layout-bounds"
        # The map is painted after the masthead and title, so its deliberate
        # top bleed can sit above them. Extend the outer composition clip by
        # the same scaled amount; otherwise this second clip shears off large
        # markers even though the map slot itself permits overflow.
        map_top_overflow = (
            layout.map_top_bleed * layout.map_width / layout.map_region.width
        )
        layout_clip_y = composition_y - map_top_overflow
        layout_clip_height = visual_bottom - layout_clip_y
        visual_markup = (
            f'<defs><clipPath id="{clip_id}"><rect x="0" '
            f'y="{layout_clip_y:g}" width="{canvas_width}" '
            f'height="{layout_clip_height:g}"/>'
            f'</clipPath></defs><g clip-path="url(#{clip_id})">'
            f'<g data-layout-node="map-composition">'
            f'{"".join(visual_parts)}</g></g>'
        )
    elif portrait and visual.portrait_regions:
        gap = 28
        regions = visual.portrait_regions
        region_margin = (
            visual.portrait_margin
            if visual.portrait_margin is not None
            else margin
        )
        region_available_width = canvas_width - region_margin * 2
        natural_heights = [
            region_available_width * region.height / region.width
            for region in regions
        ]
        available_height = visual_height - gap * (len(regions) - 1)
        scale = min(1, available_height / sum(natural_heights))
        region_y = visual_y
        visual_parts = []
        for region, natural_height in zip(regions, natural_heights):
            region_width = region_available_width * scale
            region_height = natural_height * scale
            region_x = region_margin + (region_available_width - region_width) / 2
            visual_parts.append(
                f'<svg x="{region_x:g}" y="{region_y:g}" '
                f'width="{region_width:g}" height="{region_height:g}" '
                f'viewBox="{region.min_x:g} {region.min_y:g} '
                f'{region.width:g} {region.height:g}" '
                'preserveAspectRatio="xMidYMin meet">'
                f'{visual.markup}</svg>'
            )
            region_y += region_height + gap
        visual_markup = "".join(visual_parts)
    else:
        alignment = "xMidYMid meet" if portrait else "xMidYMin meet"
        visual_markup = (
            f'<svg x="{margin}" y="{visual_y:g}" width="{visual_width}" '
            f'height="{visual_height:g}" viewBox="{visual.min_x:g} '
            f'{visual.min_y:g} {visual.width:g} '
            f'{visual.height:g}" preserveAspectRatio="{alignment}">'
            f'{visual.markup}</svg>'
        )

    title_markup = _svg_text_lines(
        title_lines,
        css_class="graphic-title",
        x=margin,
        y=title_y,
        line_height=title_line_height,
    )
    subtitle_markup = (
        f'<text class="graphic-subtitle" x="{margin}" y="{subtitle_y:g}">'
        f'{html.escape(graphic.subtitle)}</text>'
        if graphic.subtitle else ""
    )
    footer_y = visual_bottom + 38
    footer_parts = []
    for line in note_lines:
        footer_parts.append(
            f'<text class="graphic-note" x="{margin}" y="{footer_y:g}">'
            f'{html.escape(line)}</text>'
        )
        footer_y += 30 if portrait else 25
    for line in source_lines:
        footer_parts.append(
            f'<text class="graphic-source" x="{margin}" y="{footer_y:g}">'
            f'{html.escape(line)}</text>'
        )
        footer_y += 28 if portrait else 22

    description = graphic.description or graphic.title_text
    brand_size = 30 if portrait else 23
    brand_font_size = 26 if portrait else 18
    brand_gap = 12 if portrait else 9
    brand_y = 42 - brand_size
    brand_center_y = brand_y + brand_size / 2
    # Arial Bold's capital ink for this fixed phrase spans font coordinates
    # -26..1491 in a 2048-unit em. Its center is therefore 732.5 units above
    # the baseline. Place that ink center—not the baseline or em box—on the
    # flag's centerline. This is the same rule used by the forum posters.
    brand_text_y = brand_center_y + brand_font_size * 732.5 / 2048
    brand_text_x = margin + brand_size + brand_gap
    return f"""<svg xmlns="http://www.w3.org/2000/svg" data-layout-node="graphic"
viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-labelledby="title desc">
<title id="title">{html.escape(graphic.title_text)}</title>
<desc id="desc">{html.escape(description)}</desc>
<style>
.graphic-paper{{fill:{theme.background}}}
.graphic-kicker,.graphic-subtitle,.graphic-note,.graphic-source{{font-family:Arial,Helvetica,sans-serif}}
.graphic-title{{font-family:Georgia,'Times New Roman',serif;font-size:{title_size}px;font-weight:700;fill:{theme.primary}}}
.graphic-kicker{{font-size:{brand_font_size}px;font-weight:700;letter-spacing:3px;fill:{theme.accent}}}
.graphic-subtitle{{font-size:{28 if portrait else 23}px;fill:{theme.muted}}}
.graphic-note{{font-size:{MOBILE_TYPOGRAPHY.minimum if portrait else 17}px;fill:{theme.primary}}}
.graphic-source{{font-size:{MOBILE_TYPOGRAPHY.minimum if portrait else 14}px;fill:{theme.muted}}}
.mobile-layout-slot .mobile-only{{display:inline}}
</style>
<rect class="graphic-paper" width="{canvas_width}" height="{canvas_height}"/>
<g class="graphic-brand" data-layout-node="brand">
<image class="graphic-brand-mark" x="{margin}" y="{brand_y:g}"
 width="{brand_size}" height="{brand_size}" href="{_brand_mark_data_uri()}"/>
<text class="graphic-kicker" x="{brand_text_x:g}" y="{brand_text_y:g}"
>{html.escape(graphic.kicker)}</text>
</g>
<g data-layout-node="title">{title_markup}</g>
<g data-layout-node="subtitle">{subtitle_markup}</g>
<g data-layout-node="visual">{visual_markup}</g>
<line x1="{margin}" y1="{visual_bottom + 12:g}" x2="{canvas_width - margin}"
 y2="{visual_bottom + 12:g}" stroke="#e4dfd6" stroke-width="2"/>
<g data-layout-node="footer">{"".join(footer_parts)}</g>
</svg>"""


def render_graphic_canvas(
    graphic: Graphic,
    *,
    canvas_aspect_ratio: AspectRatio,
    content_aspect_ratio: AspectRatio,
    content_top_padding: float = 0,
    theme: GraphicTheme = GraphicTheme(),
) -> str:
    """Place a composed graphic inside a larger publishing canvas."""
    if not 0 <= content_top_padding < 1:
        raise ValueError("content top padding must be between 0 and 1")
    canvas_width = 1600
    canvas_height = round(
        canvas_width * canvas_aspect_ratio.height / canvas_aspect_ratio.width
    )
    content_height = (
        canvas_width * content_aspect_ratio.height / content_aspect_ratio.width
    )
    content_y = canvas_height * content_top_padding
    content = render_graphic_svg(
        graphic, aspect_ratio=content_aspect_ratio, theme=theme
    )
    description = graphic.description or graphic.title_text
    return f"""<svg xmlns="http://www.w3.org/2000/svg" data-layout-node="canvas"
viewBox="0 0 {canvas_width} {canvas_height}" role="img"
aria-labelledby="canvas-title canvas-desc">
<title id="canvas-title">{html.escape(graphic.title_text)}</title>
<desc id="canvas-desc">{html.escape(description)}</desc>
<rect width="{canvas_width}" height="{canvas_height}" fill="{theme.background}"/>
<svg x="0" y="{content_y:g}" width="{canvas_width}" height="{content_height:g}">
{content}
</svg>
</svg>"""


def html_document(title: str, svg: str, *, background: str) -> str:
    """Wrap a composed SVG in a fluid, self-contained HTML document."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        f"<style>html,body{{margin:0;background:{background}}}"
        "main{width:100%;margin:auto}svg{display:block;width:100%;height:auto}"
        "</style></head>"
        f"<body><main>{svg}</main></body></html>"
    )


def write_graphic_bundle(
    output_dir: Path,
    stem: str,
    graphic: Graphic,
    *,
    aspect_ratio: AspectRatio = CONFERENCE_LANDSCAPE,
    formats: Iterable[str] = ("html", "svg", "png"),
    png_width: int | None = None,
    theme: GraphicTheme = GraphicTheme(),
    content_aspect_ratio: AspectRatio | None = None,
    content_top_padding: float = 0,
    layout_sidecar: Mapping[str, object] | None = None,
) -> dict[str, Path]:
    """Write HTML, SVG, and/or PNG from one semantic graphic definition."""
    requested = set(formats)
    unsupported = requested - {"html", "svg", "png"}
    if unsupported:
        raise ValueError(f"unsupported graphic formats: {sorted(unsupported)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    svg = (
        render_graphic_canvas(
            graphic,
            canvas_aspect_ratio=aspect_ratio,
            content_aspect_ratio=content_aspect_ratio,
            content_top_padding=content_top_padding,
            theme=theme,
        )
        if content_aspect_ratio is not None
        else render_graphic_svg(graphic, aspect_ratio=aspect_ratio, theme=theme)
    )
    if layout_sidecar is not None:
        svg = apply_layout_sidecar(svg, layout_sidecar)
    written = {}
    svg_path = output_dir / f"{stem}.svg"
    if "svg" in requested or "png" in requested:
        svg_path.write_text(svg, encoding="utf-8")
        if "svg" in requested:
            written["svg"] = svg_path
    if "html" in requested:
        html_path = output_dir / f"{stem}.html"
        html_path.write_text(
            html_document(graphic.title_text, svg, background=theme.background),
            encoding="utf-8",
        )
        written["html"] = html_path
    if "png" in requested:
        renderer = shutil.which("rsvg-convert")
        if renderer is None:
            raise RuntimeError("rsvg-convert is required for PNG output")
        png_path = output_dir / f"{stem}.png"
        command = [renderer]
        if png_width is not None:
            command.extend(["--width", str(png_width)])
        command.extend(["--output", str(png_path), str(svg_path)])
        subprocess.run(command, check=True)
        written["png"] = png_path
    return written


def write_graphic_variants(
    output_dir: Path,
    stem: str,
    graphic: Graphic,
    variants: Mapping[str, AspectRatio],
    *,
    formats: Iterable[str] = ("html", "svg", "png"),
    png_width: int | None = None,
    theme: GraphicTheme = GraphicTheme(),
) -> dict[str, dict[str, Path]]:
    """Write named aspect-ratio variants from one semantic graphic."""
    written = {}
    for name, aspect_ratio in variants.items():
        if not name or any(character in name for character in "/\\"):
            raise ValueError(f"invalid variant name: {name!r}")
        written[name] = write_graphic_bundle(
            output_dir,
            f"{stem}-{name}",
            graphic,
            aspect_ratio=aspect_ratio,
            formats=formats,
            png_width=png_width,
            theme=theme,
        )
    return written
