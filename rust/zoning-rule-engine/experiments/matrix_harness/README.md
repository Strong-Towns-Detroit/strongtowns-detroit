# Executable 3 × 3 DSL matrix

This harness treats ontology syntax and legal-rule syntax as independent axes.
Each ontology parser is adapted into one `CanonicalOntology`; each rule parser
is adapted into one `CanonicalRule`. Every rule is then validated and evaluated
against every ontology.

The Manchester source deliberately uses different names and directionality for
some semantics (`LegalRegime` and `requiresPublishedNotice(regime, notice)`).
Its adapter maps meanings to the canonical contract, so this is not merely a
comparison of spelling.

```sh
cargo test --offline
cargo clippy --offline --all-targets -- -D warnings
```

The nine named cells require identical proposition identity, reviewed source
spans, strength, exceptions, relational support, and temporal behavior: 14 days
fails, while 15 and 16 days pass. Two further tests establish identical
ontology and rule normal forms.

This proves equivalence for the fixed §50-3-10 fixture. It does not prove equal
expressivity for every possible future ordinance provision.
