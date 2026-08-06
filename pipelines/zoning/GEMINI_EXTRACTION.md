# Gemini BZA extraction

The batch extractor sends each original PDF to Gemini native document vision and
requires schema-constrained JSON. It defaults to `gemini-3.1-pro-preview`, the
highest-quality current Gemini model for complex multimodal reasoning. The model
is configurable through `GEMINI_MODEL` or `--model`.

All outputs live in `bza_dataset_gemini`. The superseded v2 dataset is not used
by this pipeline.

## Setup

```bash
pip install -e '.[minutes]'
```

Put `GEMINI_API_KEY` in the repository `.env`.

## Pilot

Review one known document before scaling:

```bash
python pipelines/zoning/extract_bza_with_gemini.py \
  --force --limit 1
```

Selection without spending:

```bash
python pipelines/zoning/extract_bza_with_gemini.py --all --dry-run
```

After comparing Gemini output with the validated v2 record, process missing
documents:

```bash
python pipelines/zoning/extract_bza_with_gemini.py --all
```

Documents are independent and may be processed concurrently:

```bash
python pipelines/zoning/extract_bza_with_gemini.py --all --workers 4
```

Start with four workers. Higher values may encounter account-specific request or
token rate limits; transient failures are retried and permanent failures remain
in the manifest for a later rerun.

The script:

- never overwrites an existing extraction unless `--force` is passed;
- uploads one PDF at a time and deletes the remote file after extraction;
- validates output and vote counts with Pydantic;
- retries transient failures;
- preserves raw model JSON and an append-only run manifest;
- runs `merge_cases.py` after a failure-free batch.

Gemini's structured output guarantees JSON shape, not factual correctness.
Benchmark recall and field accuracy against the visually validated documents
before accepting the corpus.
