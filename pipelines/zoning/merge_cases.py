"""Validate and merge VLM-extracted BZA cases into the clean v2 dataset.

Input:  bza_dataset_v2/per_doc/*.json   — one file per meeting, a list of case
        records emitted by the VLM extraction (schema in
        .claude/skills/bza-minutes/SKILL.md).
Output: bza_dataset_v2/all_cases_v2.json
        bza_dataset_v2/all_cases_v2.csv
        bza_dataset_v2/review_low_confidence.json   — cases needing human eyes

Merge key is (case_number, meeting_date): a case continued across meetings keeps
one row per occurrence. Records are never fabricated here — this only validates,
normalizes the decision field, dedupes, and flags.

Usage: python merge_cases.py [--dir bza_dataset_v2]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

FIELDS = [
    "case_number", "meeting_date", "hearing_time", "council_district",
    "petitioner", "location", "legal_description", "proposal", "bseed_refs",
    "action", "affirmative_votes", "affirmative_count", "negative_votes",
    "negative_count", "abstentions", "decision", "decision_status",
    "confidence", "confidence_note", "source_file",
]

# Decision line -> normalized status. Order matters (specific first).
_STATUS_RULES = [
    (r"under advisement", "under_advisement"),
    (r"\btabled\b", "tabled"),
    (r"postpon", "postponed"),
    (r"withdraw", "withdrawn"),
    (r"dismiss", "dismissed"),
    (r"grant|approv|affirm|revers|den", "decided"),
]


def classify(decision: str | None, given: str | None) -> str:
    if given:
        return given
    if not decision:
        return "unknown"
    low = decision.lower()
    for pat, status in _STATUS_RULES:
        if re.search(pat, low):
            return status
    return "unknown"


def norm(rec: dict, source_file: str) -> dict:
    out = {k: rec.get(k) for k in FIELDS}
    out["source_file"] = source_file
    # vote counts from name lists if not supplied
    for side in ("affirmative", "negative"):
        names = rec.get(f"{side}_votes")
        cnt = rec.get(f"{side}_count")
        if cnt is None and isinstance(names, list):
            cnt = len(names)
        elif cnt is None and isinstance(names, str) and names.strip() and \
                names.strip().lower() not in ("none", "n/a", "-"):
            cnt = len([n for n in re.split(r"[,\n]", names) if n.strip()])
        out[f"{side}_count"] = cnt
    out["decision_status"] = classify(out.get("decision"), rec.get("decision_status"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=HERE / "bza_dataset_v2")
    a = ap.parse_args()
    per_doc = a.dir / "per_doc"
    if not per_doc.is_dir():
        print(f"no per-doc dir: {per_doc}")
        return 2

    seen: dict[tuple, dict] = {}
    low: list[dict] = []
    n_files = n_cases = 0
    for jf in sorted(per_doc.glob("*.json")):
        n_files += 1
        try:
            cases = json.loads(jf.read_text())
        except json.JSONDecodeError as e:
            print(f"! {jf.name}: bad JSON ({e}) — skipped")
            continue
        for rec in cases:
            r = norm(rec, jf.stem.replace("_cases", "") + ".pdf")
            key = (str(r.get("case_number")), str(r.get("meeting_date")))
            seen[key] = r  # last write wins (re-extraction supersedes)
            n_cases += 1
            if (r.get("confidence") == "low") or not r.get("case_number") \
                    or not r.get("decision") and r.get("decision_status") == "unknown":
                low.append(r)

    rows = list(seen.values())
    rows.sort(key=lambda r: (str(r.get("meeting_date")), str(r.get("case_number"))))
    a.dir.mkdir(parents=True, exist_ok=True)
    (a.dir / "all_cases_v2.json").write_text(json.dumps(rows, indent=2))
    with (a.dir / "all_cases_v2.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, list) else v)
                        for k, v in r.items()})
    (a.dir / "review_low_confidence.json").write_text(json.dumps(low, indent=2))

    print(f"merged {n_files} docs, {n_cases} case records -> "
          f"{len(rows)} unique (case,date)")
    print(f"  {len(low)} flagged for review -> review_low_confidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
