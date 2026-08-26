"""Shared models and presets for graphics composition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class GraphicTheme:
    """Core colors used by the graphics compositor."""

    background: str = "#fffaf0"
    primary: str = "#0c2340"
    accent: str = "#c83a3a"
    muted: str = "#526276"


@dataclass(frozen=True)
class MapMarkerStyle:
    """Configurable collision and opacity policy for map dots."""

    opacity: float = 0.78
    overlap_fraction: float = 0.10
    area_per_unit: float = 100.0
    maximum_magnitude: float | None = 10.0

    def __post_init__(self) -> None:
        if not 0 < self.opacity <= 1:
            raise ValueError("map marker opacity must be greater than 0 and at most 1")
        if not 0 <= self.overlap_fraction < 1:
            raise ValueError("map marker overlap fraction must be from 0 up to 1")
        if self.area_per_unit <= 0:
            raise ValueError("map marker area per unit must be positive")
        if self.maximum_magnitude is not None and self.maximum_magnitude <= 0:
            raise ValueError("map marker maximum magnitude must be positive")


@dataclass(frozen=True)
class AspectRatio:
    """A target composition ratio, independent of pixels or physical size."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("aspect-ratio dimensions must be positive")

    @property
    def css(self) -> str:
        return f"{self.width}/{self.height}"

    @property
    def orientation(self) -> str:
        ratio = self.width / self.height
        if ratio > 1.1:
            return "landscape"
        if ratio < 0.9:
            return "portrait"
        return "square"

    @classmethod
    def parse(cls, value: str) -> "AspectRatio":
        """Parse ratios such as ``4:5``, ``4/5``, or ``1.4``."""
        normalized = value.strip().replace(":", "/")
        if "/" in normalized:
            width, height = normalized.split("/", maxsplit=1)
            return cls(int(width), int(height))
        ratio = float(normalized)
        if ratio <= 0:
            raise ValueError("aspect ratio must be positive")
        return cls(round(ratio * 1000), 1000)


INSTAGRAM_PORTRAIT = AspectRatio(4, 5)
INSTAGRAM_STORY = AspectRatio(9, 16)
INSTAGRAM_SQUARE = AspectRatio(1, 1)
CONFERENCE_LANDSCAPE = AspectRatio(16, 11)


class GraphicFormat(str, Enum):
    """Supported, intentionally designed publishing formats."""

    INSTAGRAM_POST = "instagram"
    INSTAGRAM_STORY = "instagram_story"
    LAND_USE_CONFERENCE = "landuseconference"


@dataclass(frozen=True)
class GraphicFormatSpec:
    """Rendering policy attached to a supported publishing format."""

    aspect_ratio: AspectRatio
    png_width: int
    content_aspect_ratio: AspectRatio | None = None
    content_top_padding: float = 0


GRAPHIC_FORMAT_SPECS = {
    GraphicFormat.INSTAGRAM_POST: GraphicFormatSpec(INSTAGRAM_PORTRAIT, 1080),
    GraphicFormat.INSTAGRAM_STORY: GraphicFormatSpec(
        INSTAGRAM_STORY,
        1080,
        content_aspect_ratio=INSTAGRAM_PORTRAIT,
        content_top_padding=0.14,
    ),
    GraphicFormat.LAND_USE_CONFERENCE: GraphicFormatSpec(
        CONFERENCE_LANDSCAPE, 3200
    ),
}
