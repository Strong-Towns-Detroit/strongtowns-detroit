# Graphiti ontology assistant

This is a local, non-authoritative semantic memory for constructing the typed
Chapter 50 ontology. Graphiti and OpenAI propose entities and subject–predicate–
object edges from exact ordinance source spans. The proposals remain candidates;
only reviewed ZDL accepted by the Rust compiler is canonical.

## Architecture

```text
exact Municode source span
  -> Graphiti/OpenAI candidate extraction
  -> Neo4j candidate graph + local ingestion receipt
  -> human/agent review
  -> typed ZDL ontology and legal rules
  -> Rust compiler diagnostics
```

The initial Pydantic types deliberately distinguish structural relations,
factual predicates, and possible rule derivations. They are broad scaffolding.
The next integration will generate progressively narrower Graphiti types from
the compiled ZDL ontology.

## Setup

Put the OpenAI key in the repository-root `.env`:

```dotenv
OPENAI_API_KEY=...
```

The local Neo4j credentials live in this directory's ignored `.env`; a working
development-only password has been created during setup. The remaining Graphiti
defaults are documented in the repository `.env.example`. Telemetry is disabled
there by default.

The wrapper explicitly uses `GRAPHITI_REASONING_EFFORT=low`; Graphiti 0.29.3's
automatic fallback otherwise sends the obsolete `minimal` value to newer GPT
models.

Then run:

```sh
cd rust/zoning-rule-engine/graphiti-assist
docker compose up -d
uv sync
uv run python graphiti_assist.py init
```

Neo4j Browser is available at <http://localhost:7474>.

## Pilot ingestion

Ingest the exact source for the first reviewed rule:

```sh
uv run python graphiti_assist.py ingest \
  --file ../examples/source_50_3_10.txt \
  --source-id 'Detroit §50-3-10'
```

Search the resulting candidate facts:

```sh
uv run python graphiti_assist.py search 'Who must publish notice of a hearing?'
```

Each ingestion writes a regenerable receipt beneath `data/`, including the
source identifier and SHA-256 digest. Graphiti preserves episode provenance in
Neo4j. Neither store is accepted ontology.

## Control boundary

Graphiti may emit a linguistically plausible edge such as:

```text
BZA -- adjusts --> administrative order
```

Review may accept, normalize, replace, reject, reify, or convert that candidate
into a legal rule. The extraction is never silently written into an ontology
file. The future promotion ledger will retain the raw candidate, replacement,
reason, source span, ontology version, and reviewer.
