# Adversarial ordinance fixtures

All five fixtures below now have complete 3 × 3 executable experiments. See
[`STATEMENT_MATRIX.md`](STATEMENT_MATRIX.md) for results and cross-fixture
observations.

These fixtures are for comparing ontology and rule syntax before extending the
canonical IR. They are not yet normalized requirements. Each candidate must
first preserve the source structure, then state its interpretation separately.

Source corpus: `resources/municode/2025-10-09_job-429936/raw/`.

## F1 — Voting threshold with a specific override

**Source:** §50-2-78, “Limitations on power; concurring vote required.”

The ordinary threshold is a majority of all BZA members for a reversal,
adjustment, applicant-favorable decision, or variance. A use variance through a
hardship-relief petition instead requires a two-thirds majority of all members.

This fixture tests:

- a default rule and a more-specific override;
- fractions and rounding over a changing integer membership count;
- action classification;
- an external statutory authority and an internal cross-reference; and
- whether “members” means authorized membership rather than members present.

Competency cases for a nine-member board:

| Matter | Concurring votes | Result |
|---|---:|---|
| Ordinary dimensional variance | 4 | insufficient |
| Ordinary dimensional variance | 5 | sufficient |
| Hardship-relief use variance | 5 | insufficient |
| Hardship-relief use variance | 6 | sufficient |

## F2 — Delayed legal effect with a certified exception

**Source:** §50-2-79, “Date of decision.”

A BZA decision ordinarily becomes final at 4:00 p.m. on the third business day
after the vote. It may take immediate effect when the Board makes the required
necessity finding and certifies it on the record.

This fixture tests:

- business-day calendar arithmetic and a clock time;
- the distinction between rendering and legal finality;
- an exception requiring two affirmative predicates, not merely urgency;
- authority to make a finding; and
- documentary evidence (“on the record”).

## F3 — Ineligibility, two exceptions, and a spatial prohibition

**Source:** §50-3-341, “Generally; ineligibility for application; exceptions.”

Subsection (b) makes a delinquent person ineligible to apply, but independently
excepts qualifying foreclosure/deed-in-lieu owners and authorizations that will
correct the underlying violation. Subsection (c) prohibits approval where at
least two existing regulated uses are within 1,000 feet of the proposed site's
boundary, subject to a separately defined waiver process.

This fixture tests:

- two independent exceptions to one prohibition;
- provenance from state law and another City Code chapter;
- applicant, owner, property, debt, violation, and authorization roles;
- cardinality within a spatial predicate;
- boundary-to-feature distance rather than centroid distance; and
- a cross-referenced waiver whose content lives elsewhere.

## F4 — Waiver with alternatives, embedded conjunctions, and a hard limit

**Source:** §50-3-443, “Waiver of distance from other controlled uses.”

This section allows waiver of a controlled-use spacing prohibition upon stated
findings, while forbidding the waiver from establishing the use in a district
where it is neither permitted by right nor conditionally permitted.

This fixture tests:

- a discretionary power rather than an entitlement;
- an absolute constraint that survives the waiver;
- `any one` alternatives whose first alternative contains several conjuncts;
- exact area and parking-ratio quantities;
- a qualitative finding made and documented by a named official; and
- a textual ambiguity: the lead-in says “any one,” while the numbered list is
  joined typographically by “and.” The source AST must preserve both signals;
  executable interpretation requires an explicit reviewed resolution.

## F5 — Approval lapse, bounded extension, and exception to extension

**Source:** §50-3-386, “Lapse of approval.”

A regulated-use grant lapses if a permit is not obtained within six months. An
authorized body may extend the deadline no more than 12 months beyond the first
expiration, without another hearing. No further extension is allowed without a
new application and hearing, and an unlawfully established or expanded use that
was later legalized cannot receive the extension at all.

This fixture tests:

- automatic legal-state transition without agency action;
- calendar months rather than a fixed number of days;
- discretionary extension power and maximum duration;
- a prohibition with conjunctive prerequisites for proceeding anew;
- precedence introduced by “notwithstanding”; and
- event and state history, not merely current parcel attributes.

## Proposed order

1. F1 exposes override and rational-number semantics with a small state space.
2. F2 adds events, business calendars, evidence, and a conjunctive exception.
3. F5 adds lifecycle state and precedence.
4. F3 combines eligibility and geospatial/cardinality reasoning.
5. F4 is last because its source contains genuine coordination ambiguity that
   should remain unresolved until the languages can represent ambiguity itself.

For every fixture, author the ontology vocabulary and legal rule independently
in each candidate syntax. Only after all six sources are readable should we add
new canonical-IR types. That keeps the examples diagnostic rather than forcing
them into the abstractions we already happen to have.
