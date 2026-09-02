"""Locations of repositories consumed by Detroit-specific projects."""

from __future__ import annotations

import os
from pathlib import Path


def data_repository() -> Path:
    """Return the external data repository checkout.

    Set ``STRONGTOWNS_DATA_REPOSITORY`` in unusual checkout layouts. Adjacent
    clones work without configuration, which is also the documented setup.
    """
    configured = os.environ.get("STRONGTOWNS_DATA_REPOSITORY")
    if configured:
        return Path(configured).expanduser().resolve()
    detroit_repository = Path(__file__).resolve().parents[2]
    return detroit_repository.parent / "strongtowns-data"
