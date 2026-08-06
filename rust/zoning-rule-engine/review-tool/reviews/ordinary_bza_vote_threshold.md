# Review: ordinary BZA vote threshold

Rule: `detroit.article_ii.50_2_78.ordinary_threshold`

This ledger resolves the submitted comments on the second reviewed rule. The
comments reveal both a useful rule-as-function intuition and an important
boundary violation between ontology vocabulary and procedural rules.

## 1. The BZA/BSEED relationship is absent

**Comment.** The ontology types `DetroitBZA` and `BSEED`, but does not explain
their relationship. This resembles the missing relationship between BSEED and
Detroit in the first review.

**Finding.** Correct. Shared membership in `PublicAgency` or
`ExtensionAuthority` says nothing about organizational position, jurisdiction,
or appellate review. Those are separate possible relations. We must also avoid
assuming that the BZA is organizationally subordinate to BSEED merely because
the BZA reviews some BSEED decisions.

**Decision.** Model at least two distinctions when supported by source:

1. each body belongs to or is constituted by the City government; and
2. the BZA has appellate jurisdiction over specified decisions made by BSEED
   or its officials.

The second relationship should arise from the jurisdiction provisions, not
from a generic organizational hierarchy. It is relevant to the chapter-wide
ontology but is not an additional premise required to calculate this rule's
vote threshold.

**Status.** Accepted ontology gap; exact relations await the traced BZA
jurisdiction and organization provisions.

## 2. Bindings resemble function parameters

**Comment.** `decision: BoardDecision` feels like a function parameter.

**Finding.** This is a productive analogy. It is a typed universally quantified
input to the rule. It is not necessarily a single runtime object passed through
an imperative call; the declarative engine may match every decision satisfying
the premises.

**Decision.** Adopt the function-signature intuition in presentation and editor
tooling while preserving declarative semantics. This reinforces the first
review's proposed structure:

```zdl
for every
  decision: BoardDecision
```

The compiler should expose these bindings as the rule's typed input signature.

**Status.** Accepted; aligned with first-rule syntax direction.

## 3. Premises resemble a function body

**Comment.** `decision is decided by DetroitBZA` and `decision concerns an
ordinary BZA matter` feel like the function body.

**Finding.** They are closer to guards or a pattern match than to the entire
body: they decide whether the rule applies to a bound input. They do not perform
ordered computations or mutate the decision.

**Decision.** Present them under `given` or `when`, separated from the input
signature. Do not imply evaluation order. In software terms the rule is a typed
partial mapping whose domain is restricted by these propositions.

**Status.** Accepted with terminology refinement: applicability conditions,
not imperative statements.

## 4. Conclusions resemble returned values

**Comment.** The constitutive conclusion feels like a return value; rules may
be viewed as multi-parameter, multi-return functions.

**Finding.** This analogy is also useful, subject to three qualifications:

- one rule may derive multiple conclusions;
- multiple rules may derive facts about the same object; and
- exceptions and precedence may defeat an otherwise derivable conclusion.

There is therefore no assumption of a unique function result. The closest
formal analogy is a typed relation or a set-valued partial function.

**Decision.** Preserve explicit conclusion modality and allow multiple typed
outputs. Editor presentation may show inputs, applicability, and effects as a
signature/body/result sequence without changing the declarative core.

**Status.** Accepted presentation model; no uniqueness semantics implied.

## 5. The vote ratios are not themselves interpretive

**Comments.** Two-thirds should be represented quantitatively as `>= 2/3`, and
ordinary majority as approximately `>= 1/2`; it is strange to mark such
quantities interpretive.

**Finding.** Correct in principle, with one mathematical correction. “A
majority” ordinarily means strictly more than one half, not greater than or
equal to one half. The exact integer tests are:

```text
ordinary majority:  2 * concurring_votes > member_count
two-thirds:          3 * concurring_votes >= 2 * member_count
```

No floating point and no discretionary rounding rule are required. For an
integer member count, the inequalities determine the minimum whole number of
votes exactly. What may remain interpretive is the denominator: whether
“members of the Board” means authorized seats, currently filled seats, members
eligible to vote, or another legally defined count. That question must be
resolved from other provisions or retained as a narrowly stated gap.

**Decision.** Remove `requires_ordinary_concurrence` and
`requires_two_thirds_concurrence` as opaque interpretive relations. Encode an
exact, dimensionless threshold in the rule conclusion and isolate any
unresolved definition of `member_count` separately.

**Status.** Accepted semantic correction; quantitative conclusion syntax and
typed vote-count operands pending.

## 6. Variance needs an explicit concept hierarchy

**Comment.** A hardship use variance is a kind of variance, but `Variance` is
not declared.

**Finding.** Correct. The current unary phrase `hardship_use_variance(decision)`
collapses the requested legal remedy, the petition, and the decision about it.

**Decision.** Introduce explicit concepts, provisionally:

```zdl
concept Variance is LegalMatter
concept UseVariance is Variance
concept DimensionalVariance is Variance
concept HardshipReliefPetition is Application
```

Then relate a decision to the variance or petition it decides. Whether
“hardship relief” is itself a subtype of variance or a petition pathway must
follow the exact statutory language rather than the present convenience phrase.

**Status.** Accepted ontology correction; exact hierarchy awaits the relevant
definitions and Michigan enabling-act provision.

## 7. Procedural consequences belong in rules

**Comments.** `final_after_three_business_days` and `final_immediately` are
procedural, not ontological. The former resembles the earlier 15-day deadline.
Procedure should be expressed by chained rules rather than relations standing
in for rules.

**Finding.** Correct. A generic ontology relation may describe a state such as
`final_at(decision, instant)`. It should not bake the complete legal derivation
“4:00 p.m. on the third business day after its vote” into the predicate name.
That derivation belongs in a traced rule. Likewise, “immediately after its vote”
is a temporal effect of a rule, not a special unary property of every decision.

This does **not** make all procedural vocabulary invalid in the ontology. A
relation can describe a fact used or produced by a procedure. The boundary is:

- ontology: generic types, states, and relations that propositions may use;
- rules: the legal conditions that derive, change, require, permit, or prohibit
  those states and relations.

The first notice rule mostly respects this boundary: `notice_of`, `forum_for`,
and `responsible_for` describe facts, while the publication duty is the rule's
effect. Its relative deadline is correctly attached to that effect. The flaw in
the reviewed-rules ontology is more direct because an entire transition and
calendar calculation has been compressed into a relation.

**Decision.** Replace the specialized finality predicates with generic state or
transition vocabulary plus typed temporal rule effects. The ordinary and
exceptional finality provisions should be separate rules connected through
explicit precedence. Apply the same audit to `lacks_timely_permit`: absence of a
permit after six months requires a temporal rule and an explicit evidence or
closed-world policy, not an interpretive unary relation.

**Status.** Accepted architectural correction; requires a systematic audit of
all reviewed ontology relations before further grammar generalization.

## Result

The second review establishes four durable principles:

1. present rules as typed inputs, applicability guards, and one or more effects;
2. keep the semantics declarative and non-functional where outputs are not
   unique or may be defeated;
3. represent exact legal ratios with exact integer or rational constraints,
   reserving interpretive gaps for genuinely undefined terms; and
4. never encode a complete legal procedure or temporal derivation as an
   ontology predicate.

These corrections should be applied to the shared ontology and compiler model
before the later reviewed rules are treated as stable language fixtures.

## 8. Atomic propositions need explicit declaration kinds

**Comments.** The review identifies several declarations that are genuine
relations (`extension_for`, `filed_by`, `concerns_property`,
`new_application_for`) and many that are not (`extension_expired`,
`applicant_eligible`, `authority_may_extend`, and procedural timing results).
The reviewer asks whether predicates are intentionally being defined as
relations and proposes an explicit predicate type.

**Finding.** The prototype currently uses `relation` as a catch-all for every
atomic proposition. That is too weak. At least three semantic roles are being
collapsed:

1. structural associations among typed things;
2. externally supplied, truth-valued factual predicates; and
3. legal statuses, permissions, prohibitions, and transitions derived by rules.

Arity does not settle the distinction. A binary or ternary claim may still be
a derived legal result, while a historical event may require more than two
participants. The controlling question is whether the declaration describes
the domain, supplies evidence to a rule, or states a legal effect produced by a
rule.

**Decision.** Add an explicit factual-predicate declaration kind rather than
using `relation` universally. Keep normative and procedural determinations in
rule conclusions. Preserve typed relations for durable domain structure.
Determine final surface keywords only after applying this classification to
several more provisions.

**Status.** Accepted architectural requirement; grammar pending comparative
examples.

## 9. Neighboring provisions must become independent rules

**Comment.** The ontology is massive while the displayed vote-threshold rule
is narrow; dozens of additional rules appear to be hiding behind ontology
declarations.

**Finding.** Correct. The artifact currently combines the full vocabulary
extracted from neighboring Article II provisions with one presented rule. This
is useful for exposing the vocabulary audit, but it is not valid rule coverage.
Provisions governing finality, permit deadlines, extensions, application
eligibility, hearings, and spacing each require independently sourced rules.

**Decision.** Keep the complete ontology available in its independent review
window, but split legal derivations into separately versioned rules. Each rule
must identify the exact source span and the ontology declarations, factual
predicates, and prior rule conclusions it consumes. Chapter coverage must count
those rules, not the presence of vocabulary names.

**Status.** Accepted. The current artifact is a diagnostic prototype, not a
claim that all of its ontology vocabulary has been legally encoded.

## 10. Specific classifications from this review

The submitted comments establish the following provisional audit table:

- retain as structural relations: `extension_for`, `new_application_for`,
  `filed_by`, `concerns_property`, `delinquent_on_blight_obligation`;
- remodel acquisition through a typed acquisition event or explicitly
  qualified predicate rather than allowing applicant/property association to
  imply foreclosure;
- treat permit timeliness, finality, expiration, spacing thresholds, waiver
  applicability, correction sufficiency, and hearing requirements as rule
  evaluations over evidence;
- treat eligibility, extension permission, extension prohibition, and route
  permission as typed normative conclusions;
- distinguish an asserted proposal-to-violation relationship from the legal
  determination that the proposal sufficiently corrects the violation.

This table is provisional vocabulary design, but the ontology/rule boundary it
applies is now a durable review decision.
