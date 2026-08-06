"""Render a BZA minutes PDF to per-page PNGs for VLM reading.

Uniform path for the mixed corpus: older minutes are scanned images (no text
layer), newer are digital — rendering every page to an image treats both the
same. See .claude/skills/bza-minutes/SKILL.md.

Usage:
    python render_pages.py <minutes.pdf> [--dpi 150] [--out DIR]

Prints the list of PNG paths (one per line) to stdout; the VLM reads them in
order. Requires `pdftoppm` (poppler) on PATH.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def render(pdf: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = pdf.stem
    prefix = out_dir / stem
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(prefix)],
        check=True, capture_output=True,
    )
    pages = sorted(out_dir.glob(f"{stem}-*.png"))
    if not pages:
        raise RuntimeError(f"no pages rendered for {pdf}")
    return pages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--out", type=Path, default=None,
                    help="output dir (default: <pdf-parent>/_pages/<stem>/)")
    a = ap.parse_args()
    if not a.pdf.exists():
        print(f"no such file: {a.pdf}", file=sys.stderr)
        return 2
    out = a.out or (a.pdf.parent / "_pages" / a.pdf.stem)
    for p in render(a.pdf, out, a.dpi):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
