# Formal validation of ontology candidates

This experiment defines what can—and cannot—be proved when three surface
syntaxes claim to encode the same zoning ontology. It keeps the ontology and
legal-rule axes independent. An ontology parser emits a canonical signature;
a rule parser imports that signature and separately emits a rule certificate.

## The proof ladder

“Covers everything needed for an ontology” is not one property. We can require
and certify the following, from narrowest to strongest:

| Property | Precise obligation | Suitable checker | Strength and limit |
|---|---|---|---|
| Parse/IR equivalence | O1, O2, and O3 compile to equal canonical IR modulo ordering and alpha-renaming | Rust differential tests; Lean theorem over compiler output | Proves equal representation, not that the representation matches the ordinance |
| Well-formedness | Unique stable IDs, resolved references/imports, valid source spans, no malformed terms | Rust validator | Decidable structural property |
| Static typing | Every fact and rule atom respects concept, relation domain/range, quantity dimension, and cardinality | Rust type checker; Lean metatheory | Decidable for the deliberately restricted DSL |
| Consistency/satisfiability | There is a model satisfying the ontology axioms | OWL 2 DL reasoner or Alloy/Z3 model finder | Depends on logic/profile; satisfiable does not mean factually or legally correct |
| Conservative extension | Adding vocabulary does not change conclusions stated solely in the old vocabulary | OWL module/reasoner checks; theorem prover for restricted IR | Generally expensive or undecidable in expressive logics; tractable fragments exist |
| Competency-question coverage | Every reviewed question has a typed query and expected answer/counterexample | Fixture suite generated from a competency-question registry | Corpus-relative evidence, not absolute completeness |
| Corpus-relative completeness | Every legally material source span is linked to at least one semantic proposition, and every proposition has tests/proof obligations | Coverage ledger plus occlusion/mutation tests | The strongest practical completeness claim; depends on human-reviewed segmentation |
| Rule soundness | Any conclusion returned by the evaluator follows from the formal semantics | Lean proof of evaluator/compiler; differential SMT checks | Says nothing about whether formalization faithfully captures legal meaning |
| Decidability/termination | Every accepted program type-checks/evaluates in finite time | Restrict ontology to OWL profile/finite relational IR and rules to stratified, range-restricted Datalog | A language-design theorem, lost if unrestricted recursion, functions, negation, or first-order arithmetic are admitted |

The canonical acceptance criterion should therefore be:

> For a versioned and human-reviewed ordinance corpus, every legally material
> span has a trace to typed canonical IR; all registered competency questions
> pass; independent surface syntaxes compile to equivalent IR; the ontology is
> satisfiable; and the evaluator is proved sound for the accepted fragment.

That is strong, repeatable, and honest. It does not claim that software has
discovered every legally relevant concept without human judgment.

## Why there is no absolute completeness proof

Gödel's first incompleteness theorem applies to consistent, effectively
axiomatized systems expressive enough for arithmetic: some true statements
will be unprovable inside the system. It is not the immediate practical problem
for a small finite zoning vocabulary. The closer limitation is specification:
no theorem prover can prove that our chosen symbols capture every intended
meaning in natural-language law unless “intended meaning” is itself supplied as
a formal specification. A proof relates two formal objects; it cannot close the
gap between ordinance prose and its formalization by itself.

Other important boundaries:

- Unrestricted first-order logic is only semidecidable, and OWL 2 under
  RDF-based semantics has undecidable standard reasoning problems. We should
  target OWL 2 DL or a suitable OWL profile for ontology reasoning, and a
  stratified/range-restricted rule fragment.
- OWL normally uses the open-world assumption. Failure to prove that a parcel
  has a use is not proof that it lacks that use. Operational validation such as
  “every parcel must have exactly one known zoning district” is a closed-world
  data-quality constraint and belongs in SHACL/the Rust validator, not an OWL
  negation inference.
- Consistency is weak evidence: an empty or underspecified ontology may be
  perfectly consistent. Competency questions, mutation tests, and source-span
  coverage are required alongside a reasoner.
- Alloy checks bounded scopes. It is excellent for finding small
  counterexamples, but “no counterexample within 8 objects” is not an unbounded
  proof.
- SMT solvers are highly effective over supported decidable theories, but
  quantifier-heavy or unrestricted encodings may return `unknown` or become
  brittle. Solver output should supplement, not replace, kernel-checked proofs.

## Tool recommendation

Use a layered verification stack:

1. **Rust validator in every build.** Normalize all ontology syntaxes into one
   `CompiledOntology`, enforce structural and type invariants, and generate the
   traceability ledger. This is the fastest feedback loop.
2. **OWL 2 DL/profile export plus an OWL reasoner.** Check ontology
   satisfiability, class satisfiability, subsumption, and instance entailments.
   Use SHACL (or equivalent Rust checks) for closed-world dataset constraints.
3. **Lean 4 as the proof authority.** Define the canonical IR and evaluator
   semantics in Lean; prove type preservation, compiler equivalence, and
   evaluator soundness. Lean's automation produces proof terms checked by a
   small kernel, which is the important trust boundary.
4. **Alloy during schema design.** Search bounded models for counterexamples to
   cardinality, identity, extension, and provenance invariants. Do not label a
   bounded Alloy check an unbounded proof.
5. **Z3 for generated arithmetic and spatial obligations.** Exact rational or
   integer-unit constraints fit SMT well. Require deterministic encodings,
   record solver/version/assumptions, and keep a Lean proof for critical generic
   theorems where feasible.

Rocq/Coq would also provide kernel-checked proofs, but Lean is the recommended
single proof assistant here: it has a clean Rust-adjacent programming feel,
strong dependent types, good automation, and a small checkable artifact. The
project should not maintain two proof assistants unless a needed library forces
that cost.

Primary references:

- [OWL 2 structural specification](https://www.w3.org/TR/owl-syntax/) — a
  syntax-independent normative abstract representation, directly analogous to
  our canonical ontology IR.
- [OWL 2 profiles](https://www.w3.org/TR/owl2-profiles/) — reasoning problems,
  restrictions, decidability, and complexity.
- [Lean language reference](https://lean-lang.org/doc/reference/latest/) —
  dependent type theory and kernel checking of proof terms.
- [Alloy commands and scopes](https://alloy.readthedocs.io/en/latest/language/commands.html)
  — bounded instance and counterexample search.
- [Z3 guide](https://microsoft.github.io/z3guide/) — SMT-LIB and supported
  solver workflows.

## Current executable certificate

`src/lib.rs` proves the narrow, shared §50-3-10 fixture at the executable-test
level:

- all required concepts and exact relation signatures exist;
- BSEED has both required types;
- a reversed `responsible_for` fact is rejected;
- 14 days fails while 15 and 16 pass;
- deleting a required relation fails corpus-relative adequacy;
- changing non-behavioral legal metadata breaks certificate equivalence.

The optional `lean/ArticleIII.lean` contains kernel-checkable versions of the
typing, threshold, and syntax-independence propositions. It deliberately proves
only the small theorem stated there; it does **not** yet prove the Rust parsers
correct.

Run the available checks:

```sh
cargo test --manifest-path rust/zoning-rule-engine/experiments/formal_verification/Cargo.toml
cargo clippy --manifest-path rust/zoning-rule-engine/experiments/formal_verification/Cargo.toml --all-targets -- -D warnings
```

After installing Lean 4:

```sh
cd rust/zoning-rule-engine/experiments/formal_verification
lean lean/ArticleIII.lean
```

## Traceability and next proof obligations

`traceability.tsv` is the seed ledger:

```text
ordinance source span
  -> human-reviewed proposition ID
  -> ontology terms and rule fields
  -> generated competency questions
  -> checker/proof theorem
  -> tool version + source/IR hashes + result
```

The next implementation step is for every ontology parser to emit the same
canonical serialized signature and a compiler certificate containing source
hash, parser version, term-to-span map, and diagnostics. Differential tests then
compare all three outputs. Mutation/occlusion testing should remove one source
span, ontology term, relation, rule premise, or exception at a time and require
at least one named obligation to fail. A span whose removal changes no
obligation is an explicit coverage gap for human review.

The proof boundary must remain visible: Lean can establish that a compiler
preserves a formal AST and that evaluation is sound; reviewers establish that
the AST is a faithful interpretation of the ordinance text.
