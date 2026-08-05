#!/usr/bin/env python3
"""Find candidate BZA intake dates in Detroit's public Accela records.

This is deliberately a candidate generator, not an automatic linker.  Accela's
``openedDate`` is useful as an intake proxy only after the Accela record has
been matched to the BZA case.  The output retains all candidate records and the
evidence used to score them.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from bza_site_matching import address_candidates, clean_street

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "bza_dataset_gemini/case_histories.csv"
DEFAULT_OUTPUT = HERE / "bza_dataset_gemini/intake_date_candidates.csv"
DEFAULT_RAW = HERE / "bza_dataset_gemini/accela_raw"
DEFAULT_URL = "https://apis.accela.com/v4/search/records"

OUTPUT_FIELDS = [
    "case_history_id", "printed_case_number", "first_meeting_date",
    "minutes_location", "query_address", "accela_record_id",
    "accela_custom_id", "accela_type", "accela_status", "accela_opened_date",
    "accela_address", "address_score", "case_number_score",
    "record_type_score", "total_score", "candidate_rank",
    "suggested_disposition", "days_intake_to_first_hearing",
]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def text_value(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("value") or "")
    return "" if value is None else str(value)


def normalized_case_number(value: str) -> str:
    parts = re.findall(r"\d+", value or "")
    if len(parts) < 2:
        return ""
    return f"{int(parts[0])}-{parts[1][-2:]}"


def record_address(record: dict) -> tuple[int | None, str, str]:
    addresses = record.get("addresses") or []
    if not addresses:
        return None, "", ""
    address = addresses[0]
    number = address.get("streetStart")
    street = " ".join(filter(None, [
        text_value(address.get("streetPrefix")),
        str(address.get("streetName") or ""),
        text_value(address.get("streetSuffix")),
    ])).strip()
    display = (
        address.get("streetAddress")
        or " ".join(filter(None, [str(number or ""), street])).strip()
    )
    if number is None:
        match = re.match(r"\s*(\d{1,6})\b", str(display))
        number = int(match.group(1)) if match else None
    return int(number) if number is not None else None, clean_street(street), str(display)


def record_type(record: dict) -> str:
    item = record.get("type") or {}
    return str(item.get("value") or item.get("text") or "")


def score_candidate(
    case_number: str,
    query_number: int,
    query_street: str,
    record: dict,
) -> dict:
    number, street, display = record_address(record)
    address_score = 0
    if number == query_number:
        address_score += 45
    if street and street == clean_street(query_street):
        address_score += 35
    elif street and re.sub(r"^(?:N|S|E|W)\s+", "", street) == re.sub(
        r"^(?:N|S|E|W)\s+", "", clean_street(query_street)
    ):
        address_score += 28

    haystack = " ".join([
        str(record.get("customId") or ""),
        str(record.get("description") or ""),
        json.dumps(record.get("customForms") or {}),
        json.dumps(record.get("customTables") or {}),
    ])
    wanted_case = normalized_case_number(case_number)
    case_number_score = 15 if wanted_case and wanted_case in {
        normalized_case_number(token)
        for token in re.findall(r"\d{1,3}\s*[-/]\s*\d{2,4}", haystack)
    } else 0

    kind = record_type(record).upper()
    if "BOARD OF ZONING" in kind or re.search(r"\bBZA\b", kind):
        record_type_score = 20
    elif "APPEAL" in kind and "ZON" in kind:
        record_type_score = 18
    elif "APPEAL" in kind or "ZON" in kind:
        record_type_score = 8
    else:
        record_type_score = 0

    total = address_score + case_number_score + record_type_score
    return {
        "accela_address": display,
        "address_score": address_score,
        "case_number_score": case_number_score,
        "record_type_score": record_type_score,
        "total_score": total,
        # Even a perfect address is not enough when it could be another permit.
        "suggested_disposition": (
            "strong_candidate" if total >= 90
            else "review" if total >= 73
            else "reject"
        ),
    }


def request_records(
    url: str,
    body: dict,
    token: str,
    app_id: str,
    agency: str,
    environment: str,
    limit: int,
) -> dict:
    query = urllib.parse.urlencode({
        "offset": 0,
        "limit": limit,
        "expand": "addresses,customForms,customTables",
    })
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    else:
        # Accela calls this "No authorization required," but anonymous citizen
        # requests still require the app, agency, and environment headers.
        headers["x-accela-appid"] = app_id
        headers["x-accela-agency"] = agency
        headers["x-accela-environment"] = environment
    request = urllib.request.Request(
        f"{url}?{query}",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def opened_date(record: dict) -> str:
    return str(record.get("openedDate") or "").split(" ")[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--api-url", default=os.getenv("ACCELA_API_URL", DEFAULT_URL))
    parser.add_argument("--module", default="Planning")
    parser.add_argument("--days-before", type=int, default=730)
    parser.add_argument("--days-after", type=int, default=14)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(HERE.parents[1] / ".env")
    token = os.getenv("ACCELA_ACCESS_TOKEN", "")
    app_id = os.getenv("ACCELA_APP_ID", "")
    agency = os.getenv("ACCELA_AGENCY", "DETROIT")
    environment = os.getenv("ACCELA_ENVIRONMENT", "PROD")
    if not token and not app_id and not args.dry_run:
        raise SystemExit(
            "Accela requires either ACCELA_APP_ID for anonymous public access "
            "or ACCELA_ACCESS_TOKEN for authenticated access. Add one to .env."
        )

    with args.input.open(newline="", encoding="utf-8") as handle:
        cases = list(csv.DictReader(handle))
    if args.case_limit is not None:
        cases = cases[:args.case_limit]

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    output_rows: list[dict] = []
    query_count = 0
    for index, case in enumerate(cases, 1):
        addresses = address_candidates(case.get("location", ""))
        if not addresses:
            continue
        first_hearing = date.fromisoformat(case["first_meeting_date"])
        for number, street in addresses:
            cache_key = re.sub(
                r"[^a-z0-9]+", "-", f"{case['case_history_id']}-{number}-{street}".lower()
            ).strip("-")
            raw_path = args.raw_dir / f"{cache_key}.json"
            body = {
                "module": args.module,
                "openedDateFrom": str(first_hearing - timedelta(days=args.days_before)),
                "openedDateTo": str(first_hearing + timedelta(days=args.days_after)),
                "address": {"streetStart": number, "streetName": street},
            }
            if args.dry_run:
                print(json.dumps(body))
                return 0
            try:
                if raw_path.exists() and not args.force:
                    payload = json.loads(raw_path.read_text(encoding="utf-8"))
                else:
                    payload = request_records(
                        args.api_url, body, token, app_id, agency, environment,
                        args.limit,
                    )
                    raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    query_count += 1
                    time.sleep(args.delay)
            except urllib.error.HTTPError as exc:
                response_body = exc.read().decode("utf-8", errors="replace").strip()
                raise SystemExit(
                    f"Accela request failed for {number} {street}: {exc}\n"
                    f"Response: {response_body or '(empty response body)'}\n"
                    "The response was not treated as data."
                ) from exc
            except (urllib.error.URLError, json.JSONDecodeError) as exc:
                raise SystemExit(
                    f"Accela request failed for {number} {street}: {exc}\n"
                    "The response was not treated as data."
                ) from exc

            candidates = []
            for record in payload.get("result", []):
                scored = score_candidate(
                    case.get("printed_case_number", ""), number, street, record
                )
                intake = opened_date(record)
                elapsed = ""
                if intake:
                    elapsed = (first_hearing - date.fromisoformat(intake)).days
                candidates.append({
                    "case_history_id": case["case_history_id"],
                    "printed_case_number": case.get("printed_case_number", ""),
                    "first_meeting_date": case["first_meeting_date"],
                    "minutes_location": case.get("location", ""),
                    "query_address": f"{number} {street}",
                    "accela_record_id": record.get("id", ""),
                    "accela_custom_id": record.get("customId", ""),
                    "accela_type": record_type(record),
                    "accela_status": text_value(record.get("status")),
                    "accela_opened_date": intake,
                    "days_intake_to_first_hearing": elapsed,
                    **scored,
                })
            candidates.sort(key=lambda row: row["total_score"], reverse=True)
            for rank, row in enumerate(candidates, 1):
                row["candidate_rank"] = rank
                output_rows.append(row)
        print(f"[{index}/{len(cases)}] {case['printed_case_number']}: "
              f"{len(addresses)} address query/queries")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    strong = sum(row["suggested_disposition"] == "strong_candidate" for row in output_rows)
    print(f"{query_count} network queries; {len(output_rows)} candidates; "
          f"{strong} strong candidates -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
