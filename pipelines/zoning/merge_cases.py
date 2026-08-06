"""Validate and merge VLM-extracted BZA cases into the clean v2 dataset.

Input:  bza_dataset_gemini/per_doc/*.json — one file per meeting, a list of case
        records emitted by the VLM extraction (schema in
        .claude/skills/bza-minutes/SKILL.md).
Output: bza_dataset_gemini/all_cases.json
        bza_dataset_gemini/all_cases.csv
        bza_dataset_gemini/review_low_confidence.json — cases needing human eyes

Merge key is (case_number, meeting_date): a case continued across meetings keeps
one row per occurrence. Records are never fabricated here — this only validates,
normalizes the decision field, dedupes, and flags.

Usage: python merge_cases.py [--dir bza_dataset_gemini]
"""

from __future__ import annotations

import argparse
import csv
from difflib import SequenceMatcher
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

FIELDS = [
    "occurrence_id", "case_number", "meeting_date", "hearing_time", "council_district",
    "petitioner", "location", "legal_description", "proposal", "bseed_refs",
    "action", "affirmative_votes", "affirmative_count", "negative_votes",
    "negative_count", "abstentions", "decision", "decision_status",
    "confidence", "confidence_note", "record_type", "decision_basis", "source_file",
]

# Decision line -> normalized status. Order matters (specific first).
_STATUS_RULES = [
    (r"no action", "no_action"),
    (r"under advisement", "under_advisement"),
    (r"\btabled\b", "tabled"),
    (r"postpon", "postponed"),
    (r"withdraw", "withdrawn"),
    (r"dismiss", "dismissed"),
    (r"grant|approv|affirm|revers|den", "decided"),
]


def classify(decision: str | None, given: str | None) -> str:
    if given and given != "unknown":
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
    note = str(out.get("confidence_note") or "")
    if rec.get("record_type"):
        out["record_type"] = rec["record_type"]
    elif re.search(r"\b(?:agenda|docket)\b", note, re.I):
        out["record_type"] = "agenda_case"
        if not out.get("decision"):
            out["decision_status"] = "not_recorded"
    else:
        out["record_type"] = "minutes_case"
    out["decision_basis"] = rec.get("decision_basis") or (
        "inferred_from_motion_and_vote"
        if out.get("decision") and re.search(r"\binferr", note, re.I)
        else "recorded_disposition" if out.get("decision") else None
    )
    # Minutes sometimes decorate the value with "BSEED", parenthetical refs,
    # or leading prose. The canonical BZA occurrence key is the N-YY token.
    raw_case_number = str(out.get("case_number") or "")
    case_match = re.search(r"\b(\d{1,3}-\d{2})\b", raw_case_number)
    if case_match:
        out["case_number"] = case_match.group(1)
    elif not raw_case_number.strip() and rec.get("bseed_refs"):
        out["case_number"] = str(rec["bseed_refs"][0])
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
    if out.get("record_type") == "agenda_case" and not out.get("decision"):
        out["decision_status"] = "not_recorded"
    return out


def _similar(left, right) -> bool:
    a = re.sub(r"\W+", " ", str(left or "")).lower().strip()
    b = re.sub(r"\W+", " ", str(right or "")).lower().strip()
    if not a or not b:
        return False
    if (a in b or b in a) and min(len(a), len(b)) / max(len(a), len(b)) >= 0.65:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.94


def _combine_text(left, right, separator=" | "):
    if not left:
        return right
    if not right or _similar(left, right):
        return left
    return f"{left}{separator}{right}"


def reconcile(left: dict, right: dict) -> dict:
    """Reconcile repeated blocks/duplicate PDF versions for one case occurrence."""
    out = dict(left)
    for field in ("hearing_time", "council_district", "petitioner", "location",
                  "legal_description", "proposal"):
        if not out.get(field):
            out[field] = right.get(field)
        elif right.get(field) and not _similar(out[field], right[field]):
            note = f"Conflicting {field} across repeated blocks/source versions."
            out["confidence_note"] = _combine_text(
                out.get("confidence_note"), note, " "
            )
            if field == "petitioner":
                out[field] = _combine_text(out[field], right[field], " / ")

    for field in ("action", "decision"):
        out[field] = _combine_text(out.get(field), right.get(field))
    for field in ("bseed_refs", "affirmative_votes", "negative_votes", "abstentions"):
        values = []
        for value in (out.get(field) or []) + (right.get(field) or []):
            if value not in values:
                values.append(value)
        out[field] = values
    out["affirmative_count"] = len(out.get("affirmative_votes") or [])
    out["negative_count"] = len(out.get("negative_votes") or [])
    out["source_file"] = _combine_text(
        out.get("source_file"), right.get("source_file"), "; "
    )
    statuses = {out.get("decision_status"), right.get("decision_status")} - {
        None, "unknown"
    }
    if len(statuses) == 1:
        out["decision_status"] = statuses.pop()
    elif "decided" in statuses:
        out["decision_status"] = "decided"
    confidence_rank = {"high": 2, "medium": 1, "low": 0, None: -1}
    out["confidence"] = min(
        (out.get("confidence"), right.get("confidence")),
        key=lambda x: confidence_rank.get(x, -1),
    )
    out["confidence_note"] = _combine_text(
        out.get("confidence_note"), right.get("confidence_note"), " "
    )
    if out.get("decision") or out.get("action"):
        out["record_type"] = "minutes_case"
    elif "agenda_case" in {out.get("record_type"), right.get("record_type")}:
        out["record_type"] = "agenda_case"
    out["decision_basis"] = (
        out.get("decision_basis") or right.get("decision_basis")
    )
    return out


def distinct_matters(left: dict, right: dict) -> bool:
    """True when a repeated printed case number clearly identifies another site."""
    if left.get("location") and right.get("location"):
        return not _similar(left["location"], right["location"])
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=HERE / "bza_dataset_gemini")
    ap.add_argument(
        "--stem", default=None,
        help="Aggregate filename stem (default: all_cases_v2 for v2, else all_cases).",
    )
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
            if key in seen and distinct_matters(seen[key], r):
                suffix = 2
                collision_key = (*key, suffix)
                while collision_key in seen:
                    suffix += 1
                    collision_key = (*key, suffix)
                seen[collision_key] = r
            elif key in seen:
                seen[key] = reconcile(seen[key], r)
            else:
                seen[key] = r
            n_cases += 1
    rows = list(seen.values())
    rows.sort(key=lambda r: (str(r.get("meeting_date")), str(r.get("case_number"))))
    occurrence_counts = {}
    for row in rows:
        base = f"{row.get('meeting_date')}:{row.get('case_number') or 'unassigned'}"
        occurrence_counts[base] = occurrence_counts.get(base, 0) + 1
        row["occurrence_id"] = f"{base}:{occurrence_counts[base]}"
        if (row.get("confidence") == "low") or not row.get("case_number") \
                or not row.get("decision") and row.get("decision_status") == "unknown":
            low.append(row)
    a.dir.mkdir(parents=True, exist_ok=True)
    stem = a.stem or "all_cases"
    (a.dir / f"{stem}.json").write_text(json.dumps(rows, indent=2))
    with (a.dir / f"{stem}.csv").open("w", newline="") as fh:
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
