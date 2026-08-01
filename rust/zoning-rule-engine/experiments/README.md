# Ontology and Legal-Rule DSL Experiments

These experiments compare authoring approaches; they do not select the final
language. Every candidate keeps ontology declarations and legal provisions in
separate modules and encodes the same reviewed proposition from Detroit Zoning
Ordinance § 50-3-10.

## Fixed semantic fixture

The ontology must be capable of representing:

- `Agency`, `HearingForum`, `PublishedNotice`, and `PublicHearing` concepts;
- BSEED as both an agency and a hearing forum;
- responsibility for a notice;
- the forum of a hearing;
- the relationship between a notice and its hearing; and
- a temporal relationship between publication and hearing events.

The rule module must preserve:

- the stable proposition ID;
- both exact reviewed source spans;
- applicability to published notice required by Chapter 50;
- BSEED as the hearing forum;
- the responsible agency as the obligated actor;
- publication as the required action;
- an inclusive minimum of exactly 15 days before the hearing;
- strict/non-defeasible status in the current interpretation; and
- the absence of an encoded exception in this proposition.

Every executable prototype must demonstrate:

- 14 days fails;
- 15 days passes;
- 16 days passes;
- a domain/range-invalid ontology fact is rejected; and
- ontology and legal-rule sources can change independently unless an imported
  ontology contract is broken.

## Evaluation rubric

Each candidate will be reviewed for:

1. **Source fidelity** — can it retain hierarchy, ordering, exact spans, and
   distinctions between applicability, obligation, constraint, and exception?
2. **Semantic precision** — are conjunction, disjunction, negation, precedence,
   knowledge assumptions, units, time, and spatial relations unambiguous?
3. **Ontology modularity** — can vocabularies be imported, versioned, extended,
   and reused without embedding municipal terms into Rust?
4. **Rule modularity** — can different legal regimes act on the same ontology?
5. **Type safety** — are domain/range errors and quantity mismatches rejected
   before execution?
6. **Reviewability** — can legal and planning professionals follow the authored
   representation, and can programmers diagnose it?
7. **Traceability** — can every semantic subexpression and derived conclusion
   report its legal and factual support?
8. **Round-trip behavior** — can the source-faithful AST reproduce the ordinance
   structure while a normalized IR supports execution?
9. **Tooling and interoperability** — parser quality, editor support, Rust
   libraries, OWL/RDF/SHACL/GeoSPARQL projection, and stable diagnostics.
10. **Operational behavior** — deterministic evaluation, performance, testing,
    dependency maturity, licensing, and long-term maintainability.

Compactness is not an independent goal. Additional syntax is favorable when it
preserves legally material structure, and unfavorable when it merely exposes
compiler mechanics.
