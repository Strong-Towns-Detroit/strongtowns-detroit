"""Shared Strong Towns Detroit masthead for forum exhibits."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCKUP = (
    HERE / "design-system/assets/strong-towns-detroit-lockup-reference.png"
)


@lru_cache(maxsize=1)
def lockup_data_uri() -> str:
    encoded = base64.b64encode(LOCKUP.read_bytes()).decode()
    return f"data:image/png;base64,{encoded}"


def masthead_svg() -> str:
    """Use the exact flag area from the official raster lockup reference."""
    # Source flag bounds: x=64..323, y=63..321 in the 1026x386 lockup.
    # The full image is positioned behind a 27px clipping window so only the
    # flag sprite is visible; its source pixels remain untouched.
    flag_x = 53.5
    flag_y = 20
    flag_size = 27
    scale = flag_size / 258
    image_x = flag_x - 64 * scale
    # Align against the rendered capital strokes, with a half-pixel offset to
    # account for raster antialiasing at the standard 2× export resolution.
    image_y = flag_y - 63 * scale
    image_width = 1026 * scale
    image_height = 386 * scale
    return (
        '<defs><clipPath id="masthead-flag-clip">'
        f'<rect x="{flag_x}" y="{flag_y}" width="{flag_size}" '
        f'height="{flag_size}" rx="1.2"/>'
        "</clipPath></defs>"
        f'<image href="{lockup_data_uri()}" x="{image_x:.3f}" '
        f'y="{image_y:.3f}" width="{image_width:.3f}" '
        f'height="{image_height:.3f}" '
        'clip-path="url(#masthead-flag-clip)"/>'
        '<text class="kicker" x="91" y="39">'
        "STRONG TOWNS DETROIT · DETROIT LAND USE FORUM</text>"
    )
