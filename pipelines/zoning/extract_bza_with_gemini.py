#!/usr/bin/env python3
"""Extract Detroit BZA case records from PDFs with Gemini native PDF vision.

Safe defaults process one unextracted document. Use --all only after reviewing a
pilot and accepting API cost. Every response is schema-validated and written per
document; existing outputs are never overwritten unless --force is supplied.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "bza_minutes"
DATASET_DIR = HERE / "bza_dataset_gemini"
OUTPUT_DIR = DATASET_DIR / "per_doc"
RAW_DIR = DATASET_DIR / "gemini_raw"
MANIFEST = DATASET_DIR / "gemini_manifest.jsonl"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
MANIFEST_LOCK = threading.Lock()


class BzaCase(BaseModel):
    case_number: str | None
    meeting_date: str
    hearing_time: str | None
    council_district: int | None = Field(default=None, ge=1, le=7)
    petitioner: str | None
    location: str | None
    legal_description: str | None
    proposal: str | None
    bseed_refs: list[str] = Field(default_factory=list)
    action: str | None
    affirmative_votes: list[str] = Field(default_factory=list)
    affirmative_count: int = Field(ge=0)
    negative_votes: list[str] = Field(default_factory=list)
    negative_count: int = Field(ge=0)
    abstentions: list[str] = Field(default_factory=list)
    decision: str | None
    decision_status: Literal[
        "decided", "under_advisement", "tabled", "postponed",
        "withdrawn", "dismissed", "not_recorded", "no_action", "unknown",
    ]
    confidence: Literal["high", "medium", "low"]
    confidence_note: str | None

    @model_validator(mode="after")
    def check_counts(self):
        if self.affirmative_count != len(self.affirmative_votes):
            raise ValueError("affirmative_count does not match names")
        if self.negative_count != len(self.negative_votes):
            raise ValueError("negative_count does not match names")
        return self


class Extraction(BaseModel):
    meeting_date: str
    cases: list[BzaCase]
    document_notes: str | None = None


PROMPT = """You are extracting official Detroit Board of Zoning Appeals meeting
minutes. Read the PDF visually, respecting its two-column and labeled layout.
Return every CASE NO. block, including cases continued, adjourned, dismissed, or
taken under advisement. Skip roll call, procedural boilerplate, and approval of
prior minutes.

Critical rules:
- APPLICANT and BZA PETITIONER both map to petitioner.
- Never return a printed label such as APPLICANT, LOCATION, or BZA as a value.
- Council district may appear beside CASE NO. or inside LOCATION; check both.
- Preserve legal description, proposal, action, and final decision faithfully.
- A blank Negative line means an empty list and count 0.
- Count vote-name lists exactly. Do not include mover/seconder as votes unless
  they appear in the vote list.
- Keep each case occurrence in this meeting, even if it appeared previously.
- Do not invent absent values. Use null and lower confidence, explaining why.
- The final bold/capitalized disposition is decision. Classify it using the
  supplied decision_status enum.
- meeting_date must be {meeting_date}, derived from the source filename.

Perform a second pass before answering: enumerate visible CASE NO. blocks and
ensure the output has exactly one record for each."""


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def date_from_name(path: Path) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
    if not match:
        raise ValueError(f"no ISO date prefix: {path.name}")
    return match.group(1)


def candidates(pdf_dir: Path, output_dir: Path, force: bool) -> list[Path]:
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if force:
        return pdfs
    return [
        pdf for pdf in pdfs
        if not (output_dir / f"{pdf.stem}_cases.json").exists()
    ]


def append_manifest(record: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_LOCK:
        with MANIFEST.open("a") as handle:
            handle.write(json.dumps(record) + "\n")


def extract_one(client, pdf: Path, model: str, attempts: int) -> Extraction:
    from google.genai import types

    uploaded = client.files.upload(
        file=pdf,
        config={"mime_type": "application/pdf", "display_name": pdf.name},
    )
    try:
        for attempt in range(1, attempts + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_uri(
                            file_uri=uploaded.uri, mime_type="application/pdf"
                        ),
                        PROMPT.format(meeting_date=date_from_name(pdf)),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=Extraction,
                        temperature=0,
                    ),
                )
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                (RAW_DIR / f"{pdf.stem}.json").write_text(response.text)
                return Extraction.model_validate_json(response.text)
            except Exception:
                if attempt == attempts:
                    raise
                time.sleep((2 ** attempt) + random.random())
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, default=PDF_DIR)
    parser.add_argument("--pdf", type=Path, default=None,
                        help="Process one explicit PDF (useful for benchmarking).")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--all", action="store_true",
                        help="Process every missing PDF; incurs API charges.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing per-document extractions.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1,
                        help="Concurrent document requests (default: 1).")
    parser.add_argument("--no-merge", action="store_true",
                        help="Do not run merge_cases.py after extraction.")
    args = parser.parse_args()

    load_dotenv(HERE.parents[1] / ".env")
    model = args.model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    queue = (
        [args.pdf]
        if args.pdf is not None
        else candidates(args.pdf_dir, args.output_dir, args.force)
    )
    if args.pdf is not None and not args.pdf.exists():
        raise SystemExit(f"PDF does not exist: {args.pdf}")
    if not args.all:
        queue = queue[: max(args.limit, 0)]
    print(f"{len(queue)} document(s) selected with model {model}")
    for pdf in queue:
        print(pdf)
    if args.dry_run or not queue:
        return 0
    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set in .env or the environment")

    from google import genai

    args.output_dir.mkdir(parents=True, exist_ok=True)

    def process(pdf: Path) -> tuple[Path, bool, str]:
        started = datetime.now(timezone.utc)
        # One client per task avoids relying on undocumented client thread safety.
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        try:
            extraction = extract_one(client, pdf, model, args.attempts)
            output = args.output_dir / f"{pdf.stem}_cases.json"
            output.write_text(json.dumps(
                [case.model_dump() for case in extraction.cases], indent=2
            ))
            append_manifest({
                "source_file": pdf.name,
                "model": model,
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "case_count": len(extraction.cases),
                "status": "success",
                "document_notes": extraction.document_notes,
            })
            return pdf, True, f"{len(extraction.cases)} cases -> {output}"
        except Exception as exc:
            append_manifest({
                "source_file": pdf.name,
                "model": model,
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "error": repr(exc),
            })
            return pdf, False, f"FAILED: {exc}"

    failures = 0
    workers = max(1, args.workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process, pdf): pdf for pdf in queue}
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            pdf, ok, message = future.result()
            failures += not ok
            print(f"[{completed}/{len(queue)}] {pdf.name}: {message}")

    if not failures and not args.no_merge:
        subprocess.run(
            ["python", str(HERE / "merge_cases.py"), "--dir",
             str(args.output_dir.parent)],
            check=True,
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
