#!/usr/bin/env python3
"""Compare a Gemini BZA extraction with a visually validated per-doc record."""

from __future__ import annotations

import argparse
import json
from difflib import SequenceMatcher
from pathlib import Path

FIELDS = [
    "petitioner", "location", "legal_description", "proposal", "action",
    "decision",
]


def normalized(value) -> str:
    return " ".join(str(value or "").lower().split())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())
    candidate = json.loads(args.candidate.read_text())
    expected = {str(case.get("case_number")): case for case in reference}
    actual = {str(case.get("case_number")): case for case in candidate}
    common = sorted(expected.keys() & actual.keys())
    print(f"case recall: {len(common)}/{len(expected)}; "
          f"unexpected: {sorted(actual.keys() - expected.keys())}")
    scores = []
    for number in common:
        print(f"\nCase {number}")
        for field in FIELDS:
            score = SequenceMatcher(
                None, normalized(expected[number].get(field)),
                normalized(actual[number].get(field)),
            ).ratio()
            scores.append(score)
            print(f"  {field:18} {score:.1%}")
    if scores:
        print(f"\nmean field-text similarity: {sum(scores) / len(scores):.1%}")
    return 0 if len(common) == len(expected) else 1


if __name__ == "__main__":
    raise SystemExit(main())

