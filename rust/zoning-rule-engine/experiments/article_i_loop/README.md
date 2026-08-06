# Article I source-to-test loop (first pass)

This experiment inventories **all 15 enacted sections and the reserved range**
in Article I of the local Municode snapshot. It is an attempt at the loop, not
a claim that Article I has complete semantic coverage.

Source: `resources/municode/2025-10-09_job-429936/raw/article-01-COCH50_CH50ZO_ARTIINPR.json`

## Artifacts

- `semantic_inventory.tsv` decomposes the source into 46 substantive
  proposition spans plus one reserved-range record.
- `source_manifest.tsv` binds each section to its Municode node and a SHA-256
  digest of the exact source HTML, making source drift detectable.
- `article_i.ontology` and `article_i.rules` are a deliberately provisional
  first authoring pass over the recurring concepts and executable families.
- `src/lib.rs` implements the first executable competency loop for recurring
  Article I families: applicability, precedence, continued violations and
  nonconformities, approval extension, and pending applications.
- Every inventory row has a stable span ID, exact section reference,
  disposition, proposition, ontology terms, and a proposed competency test.

## Measured status

| Disposition | Count | Meaning |
|---|---:|---|
| Executable | 23 | Deterministic rule shape identified; 12 boundary cases currently execute |
| Interpretive | 18 | Purpose or interpretive directive preserved, not treated as parcel compliance |
| Declarative | 4 | Naming, authority/intent, or legislative counterfactual |
| Unresolved | 1 | §50-1-7(3) delegates a discretionary map interpretation |
| Reserved | 1 | No substantive proposition |

The inventory totals 47 because the reserved range is tracked in addition to
the 46 substantive proposition spans.

## Important gaps

- The exact HTML text remains in the corpus; this inventory currently stores
  normalized propositions rather than verbatim quotations or source hashes.
- §50-1-7 boundary rules need geometry concepts but no geometry evaluator in
  the legal-rule library.
- “More restrictive” is represented as a typed input, not inferred.
- §50-1-7(3) cannot be deterministically executed without a Planning and
  Development Department interpretation.
- §§50-1-13 and 50-1-14 need full civil-date and legal-state models beyond the
  boundary predicates in this first harness.
- Purpose clauses are traceable but intentionally do not produce compliance
  outcomes.
- No surface-syntax comparison has yet been authored for Article I.

Run:

```sh
cargo test --offline --manifest-path rust/zoning-rule-engine/experiments/article_i_loop/Cargo.toml
cargo clippy --offline --manifest-path rust/zoning-rule-engine/experiments/article_i_loop/Cargo.toml --all-targets -- -D warnings
```
