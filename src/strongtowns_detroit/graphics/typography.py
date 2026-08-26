"""Shared legibility standards for mobile publishing formats."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MobileTypography:
    """Font sizes in the library's 1600-unit Instagram canvas."""

    minimum: int = 24
    body: int = 26
    label: int = 26
    axis: int = 24
    legend: int = 26
    section_heading: int = 40

    def local_minimum(self, component_scale: float) -> int:
        """Convert the canvas minimum into a nested component's units."""
        if component_scale <= 0:
            raise ValueError("component scale must be positive")
        return math.ceil(self.minimum / component_scale)


MOBILE_TYPOGRAPHY = MobileTypography()
