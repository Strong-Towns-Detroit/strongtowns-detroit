# Manchester/OWL-inspired experiment

This executable spike keeps two authored modules separate:

- [`ontology.manchester`](ontology.manchester) declares the domain vocabulary.
- [`article_iii.rule`](article_iii.rule) preserves a cited legal provision and imports that ontology.

Run it with:

```sh
cargo run --manifest-path experiments/manchester_style/Cargo.toml
cargo test --manifest-path experiments/manchester_style/Cargo.toml
```

The ontology syntax borrows Manchester OWL's labeled declarations (`Class`,
`ObjectProperty`, `Domain`, `Range`, `Individual`, and `Types`). The legal module
does **not** pretend to be OWL. It uses a source-faithful `Provision` plus a
conventional, explicitly parenthesized Boolean condition. The experiment only
accepts conjunction today; adding `||` requires an actual expression tree rather
than silently changing the grammar.

## What works

- Runtime-defined ontology vocabularies compile into the engine's checked ontology.
- Rule modules name and verify their ontology import.
- The stable proposition ID, two source roles, strict status, and explicit
  absence of exceptions survive parsing as distinct fields.
- Relation arguments are statically checked against declared domain/range concepts.
- The cited provision, source sentence, obligation, and temporal clause remain distinct.
- The exact 15-day inclusive boundary executes through the engine's integer duration and refinement predicate.
- Facts remain separate from both ontology schema and law.
- The executable fixture tests 14, 15, and 16 days and rejects both an invalid
  fact and a rule whose variable types violate an imported relation contract.

## Strengths

Manchester's labeled records are unusually readable for ontology declarations.
Domain and range are visually obvious, and multiple types on `BSEED` are compact.
The separate rule file also makes it impossible to mistake `BSEED is a
HearingForum` for a legal obligation.

## Losses and open questions

- This is Manchester-inspired, not an OWL parser; it has no subclass inference,
  equivalence, restrictions, open-world reasoner, or RDF identity semantics.
- The rule condition repeats low-level relation names and is less readable than
  the ontology declarations.
- `Source` is stored as text, but exact corpus offsets/digests are not yet parsed
  by this experiment.
- `Then` and `Temporal` encode only the tested obligation shape. Permissions,
  prohibitions, exceptions, priorities, and alternate consequences remain open.
- Boolean syntax is intentionally conventional, but a real parser must preserve
  `&&`, `||`, `!`, grouping, and a separately sourced exception structure in the AST.
- Generated prose cannot yet reproduce punctuation or the trailing statutory
  `or`; the source-faithful layer needs ordered fragments, not merely one quote.

The main conclusion is mixed: Manchester-style ontology authoring is promising,
but it does not make the legal-rule surface readable by itself. The two-module
boundary is nevertheless clean and worth retaining.
