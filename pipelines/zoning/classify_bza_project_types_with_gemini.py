#!/usr/bin/env python3
"""Classify the real-world projects behind Detroit BZA cases with Gemini.

This is deliberately separate from the legal-relief classifier. It asks what
the applicant proposed to build, open, expand, retain, or alter—not which
internally inconsistent zoning-code category brought the matter to the Board.

Safe defaults select at most one batch of denied cases. Use --all only after
reviewing the pilot output and accepting API cost.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field, model_validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "bza_dataset_gemini"
HISTORIES = DATA / "case_histories.csv"
OUTPUT_DIR = DATA / "project_type_enrichment"
PER_CASE_DIR = OUTPUT_DIR / "per_case"
RAW_DIR = OUTPUT_DIR / "raw"
MERGED = OUTPUT_DIR / "project_types.csv"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
WRITE_LOCK = threading.Lock()


class ProjectClassification(BaseModel):
    case_history_id: str
    project_type_family: Literal[
        "housing",
        "mixed_use",
        "retail_or_personal_service",
        "food_or_beverage",
        "office_or_medical",
        "industrial_or_logistics",
        "vehicle_oriented",
        "cannabis_or_controlled_use",
        "institutional_or_civic",
        "religious",
        "recreation_or_open_space",
        "signage",
        "parking_only",
        "other",
        "unclear",
    ]
    project_type_label: str = Field(
        description=(
            "Concise ordinary-language type, e.g. duplex, apartment building, "
            "restaurant, daycare, trucking yard, or digital billboard."
        )
    )
    proposed_action: Literal[
        "new_construction",
        "change_of_use",
        "expansion",
        "site_or_building_alteration",
        "continue_or_legalize_existing_condition",
        "signage_installation",
        "demolition",
        "other",
        "unclear",
    ]
    intensity_direction: Literal[
        "adds_homes_or_activity",
        "maintains_existing_activity",
        "reduces_homes_or_activity",
        "unclear_or_not_applicable",
    ]
    urban_form_orientation: Literal[
        "pedestrian_or_transit_supportive",
        "mixed_or_neutral",
        "automobile_oriented",
        "industrial_or_freight_oriented",
        "unclear_or_not_applicable",
    ]
    proposal_language_tone: Literal[
        "favorable",
        "neutral",
        "adverse",
        "mixed",
        "insufficient_text",
    ] = Field(
        description=(
            "Tone of the minutes' language about the proposed project—not a "
            "judgment of whether the project is socially desirable."
        )
    )
    housing_units: int | None = Field(default=None, ge=0)
    summary: str
    evidence: list[str] = Field(
        default_factory=list,
        description="One to three short phrases copied from the supplied text.",
    )
    confidence: Literal["high", "medium", "low"]
    alternative_type: str | None = Field(
        default=None,
        description="A plausible competing project type when ambiguity matters.",
    )


class BatchResult(BaseModel):
    classifications: list[ProjectClassification]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [item.case_history_id for item in self.classifications]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate case_history_id in response")
        return self


PROMPT = """You are classifying proposed real-world land uses in Detroit Board
of Zoning Appeals case summaries.

This is NOT a zoning-code classification task. Ignore the formal variance,
appeal, district, section number, and legal-relief label except where they help
you understand the physical proposal. Detroit's code categories are not the
taxonomy. Classify what the proposal would create, operate, expand, retain, or
alter in ordinary civic and urban-development language.

Important distinctions:
- project_type_family is a broad analytic family; project_type_label is the
  specific ordinary-language use.
- parking_only means parking is itself the project. Do not classify an
  apartment, store, or restaurant as parking_only merely because its case
  requests parking relief.
- proposal_language_tone describes how the supplied minutes characterize the
  project. It is not your opinion of the project and not the Board outcome.
- Use adverse only where the text itself alleges harms, incompatibility,
  nuisance, danger, or similar concerns; use neutral for ordinary procedural
  description.
- Do not infer housing-unit counts or facts absent from the supplied text.
- Evidence must quote only short phrases present in the supplied record.
- The output must contain exactly one classification for every supplied
  case_history_id and no others.

Cases:
{cases_json}
"""


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def case_payload(row: pd.Series) -> dict:
    return {
        "case_history_id": row["case_history_id"],
        "case_number": row.get("printed_case_number"),
        "petitioner": row.get("petitioner"),
        "location": row.get("location"),
        "proposal": str(row.get("proposal") or "")[:9000],
        "recorded_outcome": row.get("final_outcome"),
    }


def classify_batch(
    rows: list[dict],
    model: str,
    attempts: int,
) -> list[ProjectClassification]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    expected = {row["case_history_id"] for row in rows}
    prompt = PROMPT.format(
        cases_json=json.dumps(rows, ensure_ascii=False, indent=2)
    )
    for attempt in range(1, attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BatchResult,
                    temperature=0,
                ),
            )
            parsed = BatchResult.model_validate_json(response.text)
            returned = {
                item.case_history_id for item in parsed.classifications
            }
            if returned != expected:
                raise ValueError(
                    f"ID mismatch; missing={sorted(expected-returned)}, "
                    f"unexpected={sorted(returned-expected)}"
                )
            digest = rows[0]["case_history_id"].replace("/", "_")
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            with WRITE_LOCK:
                (RAW_DIR / f"{digest}.json").write_text(
                    response.text, encoding="utf-8"
                )
            return parsed.classifications
        except Exception:
            if attempt == attempts:
                raise
            time.sleep((2**attempt) + random.random())
    raise RuntimeError("unreachable")


def write_results(items: list[ProjectClassification]) -> None:
    PER_CASE_DIR.mkdir(parents=True, exist_ok=True)
    with WRITE_LOCK:
        for item in items:
            path = PER_CASE_DIR / f"{item.case_history_id}.json"
            path.write_text(
                json.dumps(item.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def merge_results() -> None:
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(PER_CASE_DIR.glob("*.json"))
    ]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(MERGED, index=False)
    print(f"Merged {len(records)} classifications -> {MERGED}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outcomes",
        default="denied_upheld",
        help=(
            "Comma-separated normalized outcomes. Default analyzes requests "
            "the Board denied or upheld against the applicant."
        ),
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Maximum cases selected unless --all is supplied.",
    )
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    model = args.model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    outcomes = {
        value.strip() for value in args.outcomes.split(",") if value.strip()
    }
    histories = pd.read_csv(HISTORIES)
    selected = histories[histories["final_outcome"].isin(outcomes)].copy()
    if not args.force:
        selected = selected[
            ~selected["case_history_id"].map(
                lambda case_id: (PER_CASE_DIR / f"{case_id}.json").exists()
            )
        ]
    selected = selected.sort_values(
        ["first_meeting_date", "case_history_id"]
    )
    if not args.all:
        selected = selected.head(max(args.limit, 0))
    payloads = [case_payload(row) for _, row in selected.iterrows()]
    batches = [
        payloads[index:index + args.batch_size]
        for index in range(0, len(payloads), args.batch_size)
    ]
    print(
        f"{len(payloads)} case(s) in {len(batches)} batch(es); "
        f"model={model}; outcomes={sorted(outcomes)}"
    )
    if args.dry_run:
        for payload in payloads:
            print(
                f"  {payload['case_history_id']} · "
                f"{payload['case_number']} · {payload['location']}"
            )
        return 0
    if not batches:
        merge_results()
        return 0
    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set in .env or environment")

    failures = 0
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, args.workers)
    ) as executor:
        futures = {
            executor.submit(
                classify_batch, batch, model, args.attempts
            ): batch
            for batch in batches
        }
        for future in concurrent.futures.as_completed(futures):
            batch = futures[future]
            try:
                results = future.result()
                write_results(results)
                print(
                    f"{len(results)} classified: "
                    f"{batch[0]['case_history_id']} …"
                )
            except Exception as exc:
                failures += 1
                print(
                    f"FAILED batch beginning {batch[0]['case_history_id']}: "
                    f"{type(exc).__name__}: {exc}"
                )
    merge_results()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
