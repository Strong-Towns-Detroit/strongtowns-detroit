#!/usr/bin/env python3
"""Compatibility entry point for the publishing-neutral graphics builder.

New code should run ``strongtowns-graphics build --target landuseconference``.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from projects.graphics import build as graphics_build  # noqa: E402


def run() -> None:
    graphics_build.run(targets=["landuseconference"])


if __name__ == "__main__":
    run()
