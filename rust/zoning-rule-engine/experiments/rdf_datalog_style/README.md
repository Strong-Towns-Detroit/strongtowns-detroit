# RDF/SHACL ontology + Datalog legal rules

This runnable experiment keeps the two modules separate:

- [`ontology.zonto`](ontology.zonto) declares concepts, individuals, object
  properties, domains, ranges, and minimum cardinalities in a compact
  RDF/SHACL-inspired form.
- [`article_iii.rules`](article_iii.rules) imports that vocabulary and states
  Detroit §50-3-10 as a Datalog-style derivation.

Run it with:

```sh
cargo run --manifest-path rust/zoning-rule-engine/experiments/rdf_datalog_style/Cargo.toml
cargo test --manifest-path rust/zoning-rule-engine/experiments/rdf_datalog_style/Cargo.toml
```

The executable parses both source files, checks rule predicates against the
ontology, and prints normalized JSON. The legal duration is compiled to the
parent engine's exact `Constraint<Duration>` rather than retained as an
untyped integer. The normalized rule also retains the stable proposition ID,
both exact reviewed quotations, the obligated actor and action, strict and
non-defeasible status, and the explicit absence of encoded exceptions.

## Assessment

### Readability

The ontology is concise and its domain/range declarations are easy to audit.
The rule makes conjunction and direction explicit through Datalog's comma and
`:-`, but it reads like an implementation language rather than an ordinance.
Variables and predicate names are especially costly for a non-programmer.
This is a credible normalized rule language; it is a weak source-faithful
authoring language.

### Provenance

The rule retains two exact quotations and citations, but this prototype
attaches them only to the rule as a whole. Exact reproduction requires source
spans on each atom, comparison, actor, action, and temporal relation. RDF-star
quoted triples or explicit statement nodes could carry those spans in an RDF
projection.

### Open and closed worlds

The ontology graph is open-world: an absent type or relation is not thereby
false. The small evaluator deliberately uses a local closed-world policy for
the named rule: if a required premise is missing, it does not derive
`compliant_notice`. It does **not** derive noncompliance. A production query
must distinguish `derived`, `disproved`, and `unknown`.

### Exceptions and ordering

Plain positive Datalog has no source-order semantics and no defeasible
exceptions. An exception could be normalized as an explicit predicate plus
stratified negation, but that alone loses why one provision defeats another.
The legal-rule module therefore needs explicit `overrides`/`excepts` edges and
provenance before compilation to Datalog strata. File order must never decide
legal priority.

### What this validates

- Ontology and law can be independently authored and connected by an import.
- Domain/range shapes reject a reversed `notice_for` assertion.
- Unknown legal predicates fail compilation rather than becoming loose strings.
- Chapter 50 applicability, the responsible agency, BSEED forum, notice/hearing
  linkage, and explicit `precedes` relation are all premises rather than prose.
- The exact inclusive boundary rejects 14 days and accepts 15 and 16 days.
- RDF/SHACL is useful for schema and interchange; Datalog is useful as a compact
  execution IR. Neither alone preserves enough structure to reproduce Chapter
  50 exactly.
