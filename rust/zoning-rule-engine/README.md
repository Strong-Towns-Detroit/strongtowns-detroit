# Zoning Rule Engine

A strongly typed, source-traceable engine for executable land-use law.

The current semantic core also supports concept specialization, typed data
properties, exact whole-count thresholds, explicit legal modalities and state
transitions, acyclic rule precedence, scoped closed-world assumptions, named
calendar/spatial policies, identity-aware aggregation, and unresolved
interpretations that are prohibited from execution. See
[`docs/semantic-core-requirements.md`](docs/semantic-core-requirements.md).

The project is municipality-neutral. Detroit Chapter 50 is its first corpus,
not a hard-coded domain model.

## Authored legal language

The first unified ontology-and-rule syntax is implemented in Rust. Concepts,
individuals, actions, n-ary relations, controlled phrases, interpretive gaps,
and legal rules compile in one typed module graph. See
[`docs/language-design.md`](docs/language-design.md) for the language contract
and its design rationale.

The deterministic source-coverage pass is documented in
[`docs/extraction-pipeline.md`](docs/extraction-pipeline.md). It inventories
legal markers, quantities, possible subjects and predicates, and conservative
lexical implications without promoting them into ontology declarations.

Compile the first complete fixture to normalized JSON:

```bash
cargo run --bin zoning-dsl -- compile examples/minimum_bseed_notice.zdl
cargo run --bin zoning-dsl -- diagnose examples/minimum_bseed_notice.zdl
cargo run --bin zoning-dsl -- extract examples/source_50_3_10.txt
cargo run --bin zoning-dsl -- compile-all \
  examples/minimum_bseed_notice.zdl \
  examples/reviewed_rules.zdl
```

`diagnose` exposes stable, line-addressed compiler failures for editor and
language-server clients. The review bundle also writes each module's complete
ontology from an independent `examples/ontologies/*.ontology.zdl` source file.
The ontology window displays that full file rather than a rule-specific
dependency slice.

The compiler currently:

- builds and checks the concept-specialization graph;
- checks individual and action memberships;
- resolves controlled phrases to canonical n-ary relation declarations;
- resolves action forms such as `publication` and `publishing`;
- checks every relation argument against its named type bound;
- preserves the authored phrase, canonical symbol references, inferred types,
  source line, exact quotation, and quotation digest;
- compiles an inclusive `at least N days before EVENT` deadline; and
- preserves open interpretive relations as visible, non-executable gaps.

This is deliberately a vertical language slice, not a claim that the complete
Chapter 50 grammar is frozen. Exceptions, overrides, alternatives, additional
normative effects, imports, and richer temporal syntax will be added against
traced provisions.

## Principles

- Untyped numbers and unqualified geometries are not legal values.
- Every executable proposition traces to exact immutable source spans.
- Source coverage does not imply executable semantics.
- Exceptions, precedence, time, authority, and uncertainty are explicit.
- GeoSPARQL and OGC terminology define spatial predicates.
- JSON, LegalRuleML, RDF, and document formats are projections from the typed
  core rather than canonical authoring formats.

## Initial type boundary

```rust
let width = Length::feet(50);
let depth = Length::feet(100);
let area: Area = width * depth;
```

`Length + Area` cannot compile.

Lengths are stored as integer counts of `1/32,000,000 m`, matching the Belle
Isle/Bonsai lattice. Areas use squared lattice units and ratios use reduced
integer fractions. The legal core contains no floating-point quantities;
lossy conversion belongs to presentation and external-system adapters.

Geometry likewise carries both shape and CRS:

```rust
let parcel = Geometry::<Polygon, Epsg2898>::new(coordinates);
```

An EPSG:4326 geometry cannot be passed where EPSG:2898 is required without an
explicit transformation.

## Custom ontologies

The engine supplies ontology mechanics without fixing a municipal vocabulary.
A corpus declares concepts, individuals, and relations with explicit domains
and ranges. Facts become executable inputs only after schema validation:

```rust
ontology.declare_relation(RelationDefinition {
    id: RelationId::from("responsibleFor"),
    domain: ConceptId::from("Agency"),
    range: ConceptId::from("PublishedNotice"),
})?;

ontology.assert_fact(Fact {
    subject: IndividualId::from("detroit:BSEED"),
    relation: RelationId::from("responsibleFor"),
    object: IndividualId::from("case:notice"),
})?;
```

The rule layer will consume patterns over these validated facts. Ontology
identifiers are data-defined and stable; they are not hard-coded Rust enums.

## Refinement predicates

Legal constraints denote typed sets. Endpoints independently encode inclusion,
exclusion, or the absence of a bound, and predicates compose through union,
intersection, and complement:

```rust
let minimum = Constraint::Interval(Interval::new(
    Bound::Included(Area::square_feet(5_000)),
    Bound::Unbounded,
)?);

let proof = Refined::verify(recorded_area, minimum)?;
```

`Refined` cannot be deserialized or directly constructed. Claims crossing a
trust boundary must be checked again. The predicate AST is intentionally
solver-neutral so the same constraints can later be lowered to SMT.

## Development

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-features
cargo run --example article_iii_notice
```

## Status

The package establishes the type and provenance boundary and now includes the
first end-to-end authored-language compiler. The syntax remains versioned and
evidence-driven while additional Chapter 50 proposition families are brought
through the same parse, normalize, and test loop.
