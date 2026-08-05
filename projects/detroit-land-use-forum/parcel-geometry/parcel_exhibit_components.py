"""Shared SVG components for Detroit parcel-geometry exhibits."""

from __future__ import annotations

import html

import pandas as pd


PARKS_TAXPAYER_PATTERN = (
    r"^(?:(?:CITY OF )?DETROIT[- ]*)?"
    r"PARKS?(?: AND | & )(?:RECREATION|REC)"
    r"(?: (?:DEPT|DEPARTMENT|DIVISION))?\.?$"
    r"|^CITY OF DETROIT[- ]RECREATION DEPT\.?$"
)


def is_detroit_parks_taxpayer(frame: pd.DataFrame) -> pd.Series:
    """Match observed municipal Parks & Recreation taxpayer-name variants."""
    matched = pd.Series(False, index=frame.index)
    for column in ("taxpayer_1", "taxpayer_2"):
        if column not in frame:
            continue
        normalized = (
            frame[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )
        matched |= normalized.str.match(
            PARKS_TAXPAYER_PATTERN, case=False, na=False
        )
    return matched


def bza_case_stat(
    count: int,
    case_label: str,
    history_label: str,
    *,
    x: int = 1120,
    y: int = 510,
) -> str:
    """Render the standard BZA case-history block used beside parcel maps."""
    case_label = html.escape(case_label)
    history_label = html.escape(history_label)
    return (
        f'<text class="section-title" x="{x}" y="{y}">'
        f"{count} {case_label} cases at the BZA</text>"
        f'<text class="source" x="{x}" y="{y + 33}">'
        f"From {history_label} histories</text>"
        f'<text class="source" x="{x}" y="{y + 51}">'
        "identified in the 2019–2026 BZA minutes</text>"
    )
