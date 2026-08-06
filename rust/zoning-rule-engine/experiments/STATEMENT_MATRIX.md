# Statement experiment matrix

Each completed statement has three ontology renderings, three legal-rule
renderings, and nine executable cross-pairings. These are diagnostic one-off
models, not production IR commitments.

| Statement | Core semantic pressure | Experiment | Cells |
|---|---|---|---:|
| §50-3-10 publication notice | typed relations and inclusive duration | [`matrix_harness`](matrix_harness/README.md) | 9/9 |
| §50-2-78 concurring votes | specialization, override, fraction and rounding | [`voting_threshold`](voting_threshold/README.md) | 9/9 |
| §50-2-79 decision finality | events, business calendar, evidence-backed exception | [`decision_finality`](decision_finality/README.md) | 9/9 |
| §50-3-386 approval lapse | state transition, bounded power, precedence, history | [`approval_lapse`](approval_lapse/README.md) | 9/9 |
| §50-3-341 eligibility/spacing | independent exceptions, spatial count, waiver | [`regulated_use_eligibility`](regulated_use_eligibility/README.md) | 9/9 |
| §50-3-443 controlled-use waiver | discretion, hard constraint, unresolved coordination | [`controlled_use_waiver`](controlled_use_waiver/README.md) | 9/9 |

## Repeated requirements now supported by evidence

The examples repeatedly require:

- distinct ontology and legal-rule modules;
- object relations, exact quantities, whole-number counts, dates, and events;
- concept specialization without flattening the specialized concept;
- explicit negation and closed-world scope for executable checks;
- default/specific-rule precedence and `notwithstanding` precedence;
- obligations, prohibitions, permissions, powers, and automatic legal effects;
- named calendar and spatial-measurement policies;
- unique-entity aggregation rather than value aggregation;
- source signals preserved independently from reviewed interpretation; and
- an explicit unresolved/ambiguous state that prevents executable conclusions.

## Current syntax observations

### SDML-inspired ontology

The module form remains the most compact readable ontology. `relation`,
`measure`, and `predicate` declarations scan well. It needs a settled syntax for
multi-argument measurements, specialization axioms, cardinality, and scalar
datatypes.

### Manchester-inspired ontology

The labeled frames make domains and ranges easiest to audit and make datatype
properties visually distinct. Repetition grows quickly, but that repetition is
often useful in legal review. Facts and n-ary measurements remain awkward.

### RDF/SHACL-inspired ontology

The compact form is easiest to project into interchange and constraint
validation. It is also easiest to make cryptic, particularly for n-ary spatial
measurements and qualitative predicates.

### Provision rule style

This style best preserves legal structure: named provisions, source spans,
`overrides`, powers, prohibitions, candidate interpretations, and explicit
ambiguity. Its expression grammar still needs conventional grouping rules and
a clear separation between source-faithful and executable clauses.

### Labeled rule style

This is the easiest format for line-by-line professional review. It makes
semantic roles explicit but becomes verbose, and long expressions inside a
single labeled field partly defeat the frame structure.

### Datalog rule style

Datalog is the clearest normalized execution form for derivation, aggregation,
and stratified negation. It is the weakest authored legal source unless wrapped
in substantial metadata: exceptions, discretionary powers, precedence, source
ordering, and unresolved ambiguity do not naturally live in Horn clauses.

## Do not generalize yet

The fixtures suggest a likely direction—frame/module ontology authoring,
provision-oriented legal authoring, and Datalog-like normalized execution—but
they do not yet test district/use tables, dimensional geometry, accessory-use
inheritance, conditional approvals with enumerated criteria, or interacting
cross-references across articles. Those should be the next statement family
before freezing the canonical types.
