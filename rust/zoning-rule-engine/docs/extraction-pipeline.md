# Deterministic legal-source extraction

The extraction pipeline converts exact legal text into review obligations. It
does **not** create ontology declarations or legal rules.

## Coverage invariant

Every non-whitespace token receives exactly one token-level coverage record:

- structural punctuation or closed-class grammar; or
- one or more source-bound semantic candidates.

Every candidate must eventually receive an explicit disposition:

- mapped to an existing symbol;
- proposed as a new declaration;
- grammatical;
- resolved as coreference;
- resolved as a contextual synonym;
- preserved as an interpretive gap;
- delegated to an external authority;
- reviewed as legally irrelevant; or
- explicitly unresolved.

The extraction artifact reports lexical coverage and semantic-disposition
completion separately. Deterministic extraction should immediately produce
complete lexical coverage. It must not claim complete semantic disposition.

## Current deterministic pass

`deterministic-legal-v1` emits exact byte-addressed tokens and overlapping
candidates for:

- legal modalities (`shall`, `may`, `must`);
- conditions (`where`, `if`, `when`, `provided`);
- exceptions (`except`, `unless`);
- precedence (`notwithstanding`);
- coordination (`and`, `or`);
- citations;
- quantities and nearby temporal expressions;
- proper-name candidates;
- candidate subjects and predicates surrounding modal verbs; and
- conservative open-class lexical terms with noun, verb, modifier, or
  coreference implications.

The lexical hints are deliberately overinclusive. `Noun` means “may have
ontological implications,” not “must become a concept.” Reproducibility is not
semantic certainty.

Run the extractor with:

```bash
cargo run --bin zoning-dsl -- extract examples/source_50_3_10.txt
```

The JSON result includes the exact source and digest, tokens, candidates,
candidate dispositions, token-to-candidate coverage, and completion summary.

## Provider boundary

Later syntax analyzers may contribute dependency parses, constituency parses,
lemmata, or coreference candidates. They must emit the same source-addressed
candidate contract and identify their analyzer and version. Statistical or LLM
annotations remain proposals; they cannot directly mark a candidate reviewed.

The deterministic pass remains the baseline coverage audit even when richer
providers are used.

## Relationship to compilation

Extraction and compilation answer different questions:

- Extraction: has every potentially meaningful part of the source received a
  recorded disposition?
- Compilation: is the authored ontology and rule module typed, unambiguous,
  normalized, and source-traceable?

A rule may compile while its extraction artifact contains unresolved
candidates. It cannot be promoted to verified coverage until both checks pass.

The planned authoring service will expose the same extraction and incremental
compiler state to a CLI, an LLM tool interface, and eventually an LSP/visual
editor.
