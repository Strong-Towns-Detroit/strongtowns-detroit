"""Parse the full Detroit Zoning Ordinance into structured datasets.

Thin CLI wrapper around strongtowns_data.zoning.ordinance.
Reads .docx files from resources/ and writes JSON + CSV to output/.

Usage:
    python parse_ordinance.py [--resources-dir DIR] [--output-dir DIR]
"""

import argparse
from pathlib import Path

from strongtowns_data.zoning.ordinance import (
    export_to_csv,
    export_to_json,
    parse_ordinance,
)


def main():
    parser = argparse.ArgumentParser(description="Parse Detroit Zoning Ordinance")
    parser.add_argument(
        "--resources-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "resources",
        help="Directory containing .docx ordinance files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for output files",
    )
    args = parser.parse_args()

    print(f"Parsing ordinance from: {args.resources_dir}")
    data = parse_ordinance(args.resources_dir)

    print(f"  Sections: {sum(1 for _ in _count_sections(data['sections']))}")
    print(f"  Use permissions: {len(data['use_permissions'])}")
    print(f"  Dimensional standards: {len(data['dimensional_standards'])}")
    print(f"  Definitions: {len(data['definitions'])}")

    print(f"\nExporting to: {args.output_dir}")
    export_to_json(data, args.output_dir)
    export_to_csv(data, args.output_dir)
    print("Done.")


def _count_sections(nodes):
    """Count all nodes in section trees."""
    from strongtowns_data.zoning.document import walk_sections
    return walk_sections(nodes)


if __name__ == "__main__":
    main()
