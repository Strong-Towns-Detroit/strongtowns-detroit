# DSL Syntax Matrix

Ontology syntax and legal-rule syntax are independent choices. Each prototype
retains its own parser, while the executable matrix adapts every parser output
to a shared canonical contract. All nine row/column pairings run today against
the same semantic fixture.

## Ontology syntax candidates

| ID | Style | Character | Current source |
|---|---|---|---|
| O1 | SDML-inspired | Module-oriented, low punctuation, `relation … from … to …` | [`sdml_style/ontology.sdmlish`](sdml_style/ontology.sdmlish) |
| O2 | Manchester-inspired | Labeled frames, visually explicit domain/range/type declarations | [`manchester_style/ontology.manchester`](manchester_style/ontology.manchester) |
| O3 | RDF/SHACL-inspired compact syntax | Terse triples/shapes vocabulary, close to interchange concepts | [`rdf_datalog_style/ontology.zonto`](rdf_datalog_style/ontology.zonto) |

## Legal-rule syntax candidates

| ID | Style | Character | Current source |
|---|---|---|---|
| R1 | Module/provision + Boolean | Compact source fields, typed givens, conventional `&&`, one normalized consequence | [`sdml_style/article_iii.rules`](sdml_style/article_iii.rules) |
| R2 | Labeled provision + Boolean | Verbose source-faithful fields, explicit obligation and temporal clauses | [`manchester_style/article_iii.rule`](manchester_style/article_iii.rule) |
| R3 | Datalog derivation | Minimal relational execution syntax; provenance and legal structure require surrounding declarations | [`rdf_datalog_style/article_iii.rules`](rdf_datalog_style/article_iii.rules) |

## Cross-pairing matrix

| Ontology \ Rules | R1 module/provision | R2 labeled provision | R3 Datalog |
|---|---:|---:|---:|
| O1 SDML-inspired | Running | Running | Running |
| O2 Manchester-inspired | Running | Running | Running |
| O3 RDF/SHACL-inspired | Running | Running | Running |

All nine cells run in [`matrix_harness`](matrix_harness/README.md). Each surface
syntax is adapted into the same canonical ontology or rule contract. A failure
means either that two sources no longer express the same fixture or that a
surface-syntax assumption leaked past its adapter.

## Vibes review

Review ontology and rule sources separately before considering combinations.

For ontology syntax:

- Which one is easiest to scan without already knowing the vocabulary?
- Which one makes a reversed relation or incorrect type look visibly wrong?
- Which one will remain comfortable with inheritance, cardinality, datatypes,
  annotations, provenance, and imported GeoSPARQL terms?
- Which one produces the cleanest diffs?

For legal-rule syntax:

- Which one most clearly separates original text, interpretation, and execution?
- Which one can preserve enough ordered structure to reproduce the ordinance?
- Which one makes Boolean grouping, obligations, exceptions, priority, time,
  and uncertainty visible without becoming ceremony?
- Which one would be tolerable across thousands of provisions?

The matrix should not receive a single aggregate score. A preferred ontology
row and preferred rule column can be selected independently, and later syntax
experiments can be added without changing the semantic fixture.
