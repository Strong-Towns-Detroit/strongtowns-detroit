---
name: bza-minutes
description: Extract structured case records from Detroit Board of Zoning Appeals (BZA) meeting-minutes PDFs via VLM (vision), one document at a time. Use when parsing, re-parsing, or updating the BZA minutes dataset in pipelines/zoning/. Covers the scanned-vs-digital split, label drift, field layout, decision vocabulary, and the traps that broke the old OCR+regex pipeline.
---

# Parsing Detroit BZA meeting minutes

The BZA (Board of Zoning Appeals — the appeals/variance board administered under
**BSEED**) publishes meeting minutes as PDFs at
`https://detroitmi.gov/documents` filtered by department **"BZA Meeting Minutes
(5916)"**. Each meeting lists a sequence of zoning cases. Goal: one clean
structured record per case.

## Why VLM, not OCR+regex

The prior pipeline (Tesseract/RapidOCR → regex) mislabeled fields wholesale
(`case_number: "APPLICANT:"`, `petitioner: "LOCATION:"`, votes holding the
decision text) and left ~44% of cases with missing fields. **Render each page to
an image and read it visually.** A VLM reads both the clean digital pages and the
legible scans correctly, and it understands layout (which text is a *label* vs a
*value*) — the exact thing regex got wrong.

## The corpus is MIXED — treat every page as an image

- **Older minutes (≈2019–2020) are scanned images** with **zero** extractable
  text (`pdftotext` returns nothing). They are high-quality scans and read
  perfectly by VLM.
- **Newer minutes (≈2021+) are digital PDFs** with a clean text layer.
- **Do not branch on this.** Render every page with `pdftoppm -png -r 150` and
  read the image. Uniform path = uniform quality. (`render_pages.py` does this.)

## Page structure

- **Page 1** and often page 2 are boilerplate: roll call / members present /
  approval of prior minutes / a "PROCEDURAL MATTERS" block. **No cases — skip.**
- **Case pages** begin around page 2–3. Each case is a labeled block; a case can
  **span multiple pages** (long PROPOSAL text especially).

## One case's fields (the target schema)

| Field | Where / notes |
|---|---|
| `hearing_time` | left margin, e.g. `10:00 a.m.` — precedes each case |
| `case_number` | after `CASE NO.:`, format `N-YY` (case N of 20YY): `9-19`, `30-25` |
| `council_district` | **floats** — see trap below |
| `petitioner` | label is **`APPLICANT:` in old minutes, `BZA PETITIONER:` in new** — both map here |
| `location` | street address + `between X and Y` cross-streets + zone code (`R2`, `M3`, `B4`…) + often the district |
| `legal_description` | after `LEGAL DESCRIPTION OF PROPERTY:` — plat/metes-and-bounds; capture **verbatim**, do not interpret |
| `proposal` | after `PROPOSAL:` — the request; often cites BSEED case nos. (`SLU-2024-00110`) → also capture as `bseed_refs` |
| `action` | after `ACTION OF THE BOARD:` — the motion text + who **moved** and who **seconded** |
| `affirmative_votes` | names list under `Affirmative:` → also store the **count** |
| `negative_votes` | names under `Negative:` — **blank/None = 0** |
| `abstentions` | under `Abstain:` if present |
| `decision` | the **bold final line** of the case (see vocabulary) |
| `decision_status` | `decided` \| `under_advisement` \| `tabled` \| `postponed` \| `withdrawn` \| `dismissed` |

## Traps (these are what broke the old parser)

1. **Council district floats — and you WILL miss it if you only look one place.**
   It appears on the case line (`CASE NO.: 30-25 - COUNCIL DISTRICT #5`) **or**
   buried inside `LOCATION` (`…in a M3 (GENERAL INDUSTRIAL DISTRICT) City Council
   District #7`). Scan **both** for a `District #N` / `Council District #N` token.
   **Carry it consistently across every case in the meeting:** a single document
   uses one placement throughout, so if you found the district for one case,
   look in that same spot for all the others rather than leaving them null. Store
   the integer; only use `null` if `District #` truly appears nowhere for that case.
2. **Label drift:** `APPLICANT:` (old) == `BZA PETITIONER:` (new). Never treat
   the label text as a value.
3. **`LEGAL DESCRIPTION OF PROPERTY:` wraps** onto the value line — don't let the
   words "OF PROPERTY" leak into the description.
4. **Decision vocabulary varies** — capture the line verbatim, then classify:
   `DIMENSIONAL VARIANCE GRANTED/DENIED`, `USE VARIANCE GRANTED/DENIED`,
   `APPROVED WITH CONDITIONS`, `AFFIRMED …` / `REVERSED …` (appeals, e.g.
   `AFFIRMED DRUG FREE ZONE`), `WITHDRAWN`, `DISMISSED`.
5. **No-decision cases exist.** `TABLED`, `POSTPONED`, or "taken **Under
   Advisement**" cases have **no** final decision — set `decision_status`
   accordingly; do **not** invent a decision.
6. **Votes are name lists spanning lines.** Count them for the tally. `Negative:`
   blank means zero, not missing.
7. **Continued cases:** the same `case_number` can recur across meeting dates
   (under advisement → decided later). Keep each occurrence, keyed by
   `(case_number, meeting_date)`.
8. **Multi-parcel cases:** `LOCATION`/`legal_description` may list several
   addresses/parcels — keep all.
9. **OCR-era artifacts** in scans (e.g. "Buildings Safety **n** Engineering" for
   "and") — read the *intended* text; don't propagate scan noise.
10. **Do not trust the legacy `all_cases.json`** for values — it is the broken
    regex output (and its `pdf_path` points at an old repo location). Re-extract.

## Procedure (one document at a time)

1. `python render_pages.py <minutes.pdf>` → page PNGs in a work dir.
2. Read the pages in order. Skip boilerplate. For each `CASE NO.:` block, read
   through to its decision line (across pages if needed).
3. Emit one record per case with the schema above, plus `meeting_date` (from the
   filename / page header) and a per-case `confidence` (`high|medium|low`) — set
   `low` when a scan is ambiguous or a field is genuinely absent, and say why.
4. Never fabricate. A truly-absent field is `null` with a note — that beats a
   confident wrong value (the whole reason we left OCR+regex behind).
5. `python merge_cases.py` validates + merges per-doc JSON into the clean dataset
   and lists low-confidence cases for human review.
