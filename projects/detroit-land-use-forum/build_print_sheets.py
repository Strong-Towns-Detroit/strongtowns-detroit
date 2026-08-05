#!/usr/bin/env python3
"""Place canonical SVG exhibits on exact-size, print-ready sheets."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANONICAL = HERE / "conference-canonical"
VIEWBOX_RE = re.compile(
    r"""viewBox\s*=\s*["']\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*["']"""
)
SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE | re.DOTALL)


def dimensions(svg: str) -> tuple[float, float]:
    match = VIEWBOX_RE.search(svg)
    if not match:
        raise ValueError("SVG has no viewBox")
    return float(match.group(3)), float(match.group(4))


def wrapper(
    source: Path,
    *,
    sheet_width: float,
    sheet_height: float,
    margin: float,
) -> str:
    source_svg = source.read_text(encoding="utf-8")
    source_width, source_height = dimensions(source_svg)
    available_width = sheet_width - 2 * margin
    available_height = sheet_height - 2 * margin
    scale = min(
        available_width / source_width,
        available_height / source_height,
    )
    placed_width = source_width * scale
    placed_height = source_height * scale
    x = (sheet_width - placed_width) / 2
    y = (sheet_height - placed_height) / 2
    opening = SVG_OPEN_RE.search(source_svg)
    if not opening:
        raise ValueError("SVG has no root element")
    inner = source_svg[opening.end():]
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.IGNORECASE)
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
width="{sheet_width}in" height="{sheet_height}in"
viewBox="0 0 {sheet_width} {sheet_height}"
role="img" aria-label="Print sheet for {source.stem}">
<rect width="{sheet_width}" height="{sheet_height}" fill="#fffaf0"/>
<g transform="translate({x:.5f} {y:.5f}) scale({scale:.9f})">
{inner}
</g>
</svg>"""


def run(width: float, height: float, margin: float, dpi: int) -> None:
    orientation = "landscape" if width >= height else "portrait"
    # Match the short-side × long-side convention used by photo/poster retailers.
    # Width and height still describe the actual page geometry passed to this script.
    retail_size = sorted((width, height))
    size_slug = f"{retail_size[0]:g}x{retail_size[1]:g}-{orientation}"
    output = HERE / "conference-print" / size_slug
    output.mkdir(parents=True, exist_ok=True)
    sources = sorted(CANONICAL.glob("*.svg"))
    if not sources:
        raise FileNotFoundError("Build the canonical conference bundle first")
    for source in sources:
        sheet_svg = output / source.name
        sheet_svg.write_text(
            wrapper(
                source,
                sheet_width=width,
                sheet_height=height,
                margin=margin,
            ),
            encoding="utf-8",
        )
        subprocess.run(
            [
                "rsvg-convert",
                "--format", "pdf",
                "--output", str(sheet_svg.with_suffix(".pdf")),
                str(sheet_svg),
            ],
            check=True,
        )
        subprocess.run(
            [
                "rsvg-convert",
                "--format", "png",
                "--width", str(round(width * dpi)),
                "--height", str(round(height * dpi)),
                "--output", str(sheet_svg.with_suffix(".png")),
                str(sheet_svg),
            ],
            check=True,
        )
        print(sheet_svg.with_suffix(".pdf"))
    readme = output / "README.md"
    readme.write_text(
        f"""# {retail_size[0]:g} × {retail_size[1]:g} inch conference prints

- Orientation: {orientation} ({width:g} inches wide × {height:g} inches high)
- Safe border: {margin:g} inch
- PNG resolution: {dpi} DPI ({round(width * dpi)} × {round(height * dpi)} pixels)
- PDF and SVG remain vector-based.
- Every exhibit is scaled proportionally and centered; nothing is stretched.
- Ask the printer to use **actual size / 100%**, not fill or crop.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=float, default=20)
    parser.add_argument("--height", type=float, default=16)
    parser.add_argument("--margin", type=float, default=0.5)
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()
    run(args.width, args.height, args.margin, args.dpi)
