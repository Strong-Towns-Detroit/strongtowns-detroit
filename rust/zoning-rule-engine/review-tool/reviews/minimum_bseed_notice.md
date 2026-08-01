# Review: minimum BSEED notice

Rule: `detroit.article_iii.50_3_10.bseed_notice`

This ledger records the disposition of anchored review comments. It distinguishes
surface syntax from ontology semantics and compiler behavior so that a pleasant
phrase does not silently change the rule's meaning.

## 1. Bindings and premises are visually conflated

**Comment.** `agency`, `hearing_notice`, and `hearing` are distinct from the
four proposition lines that follow them. The current `given all` block makes
both kinds of statement look like one list. Consider syntax such as `given all
entity`, while retaining `given all` if it remains the clearest core form.

**Finding.** The first three lines declare universally quantified variables.
They are not named ontology individuals. The next four lines are relation
applications (predicates) that constrain those variables. Calling every bound
variable an `entity` would be misleading: the variables range over such types
as `PublicAgency`, `Notice`, and `PublicHearing`, while `entity` currently names
ground individuals such as `BSEED`.

**Decision.** Preserve universal quantification, but give bindings and premises
separate visible grammar. The leading candidate is:

```zdl
for every
  agency: PublicAgency
  hearing_notice: Notice
  hearing: PublicHearing

given
  Chapter50 requires publication of hearing_notice
  agency is responsible for publishing hearing_notice
  hearing_notice is notice of hearing
  BSEED is the forum for hearing
```

`for every` declares universally quantified typed bindings; `given` introduces
the propositions under which the rule applies. Any shorter spelling should be
compile-time sugar for this form, not a distinct semantic construct.

**Status.** Accepted design direction; parser and normalized-AST change pending.

## 2. `using some` is an existential scoped to the duty

**Comment.** `using some newspaper: Newspaper` both modifies the action and
declares a typed variable. The word `some` is useful and parallels `all`, but
the construct is unusual.

**Finding.** The construct is genuinely different from the universally bound
rule variables. It means that satisfying the duty requires at least one
`Newspaper` meeting the nested condition. The existential belongs to the means
of performance, not to the rule's applicability conditions.

**Decision.** Retain explicit existential language and its scope. Do not flatten
`newspaper` into the universal binding block. Continue testing whether `using
some` is the best surface phrase, but preserve the semantic shape:

```text
exists newspaper: Newspaper
such that has_general_circulation_in(newspaper, Detroit)
```

The compiler must expose this as a scoped existential rather than an ordinary
relation or an unscoped variable.

**Status.** Semantics accepted; surface wording remains open.

## 3. Relative deadlines need a general typed grammar

**Comment.** `at least` appears to begin a general construction resembling
`at least {number} {time unit} {before/after} {event}`. It is verbose but clear.

**Finding.** Correct. The phrase carries four independent semantic components:
an inclusive bound, an exact duration, a temporal direction, and a referenced
event. These must not be stored as one opaque string.

**Decision.** Keep controlled-English authoring while compiling it into typed
components. The grammar should eventually cover `at least`, `at most`, and
`exactly`; integral duration and unit; `before` and `after`; and a typed event
binding. Calendar policy remains an explicit part of duration interpretation.

**Status.** Current `at least N days before EVENT` slice is correct; symmetric
forms and explicit normalized types remain pending.

## 4. `held_before` is semantically ambiguous

**Comment.** “Held before” can be read temporally or as identifying the forum.

**Finding.** Agreed. The source phrase should remain in provenance, but the
canonical ontology relation should state the interpreted relationship without
reproducing the ambiguity.

**Decision.** Replace canonical `held_before` with a forum relation, provisionally
`forum_for`, and use the controlled phrase:

```zdl
relation forum_for
  forum: HearingForum
  hearing: PublicHearing
  phrase
    "{forum} is the forum for {hearing}"
```

The legal quotation continues to preserve “held before.” The normalized
relation will no longer look temporal.

**Status.** Accepted; ontology, fixture, and compiler-output update pending.

## 5. Department membership is not represented

**Comment.** `BSEED is CityDepartment` and `Detroit is Municipality` do not say
that BSEED is a department of Detroit.

**Finding.** Correct. Type membership cannot represent organizational
affiliation. The current model also risks conflating Detroit as geographic area
with the City of Detroit as a municipal government or corporation.

**Decision.** Introduce distinct governmental and geographic concepts before
asserting the relation. The likely shape is:

```zdl
concept MunicipalGovernment is Organization
concept CityDepartment is PublicAgency

entity CityOfDetroit
  is MunicipalGovernment

entity Detroit
  is Municipality

relation department_of
  department: CityDepartment
  government: MunicipalGovernment
  phrase
    "{department} is a department of {government}"
```

Then the ontology may assert `BSEED is a department of CityOfDetroit`. A
separate jurisdiction relation can connect `CityOfDetroit` to the geographic
area `Detroit` if a rule needs that fact. We should not overload one `Detroit`
individual with both meanings.

**Status.** Accepted ontology correction; exact government terminology and
jurisdiction relation remain to be tested against additional provisions.

## Result

The comments identify three immediate improvements without changing the legal
rule itself:

1. separate universal bindings from applicability propositions in the surface
   grammar;
2. replace the ambiguous forum relation; and
3. distinguish municipal government from geographic municipality and model
   departmental affiliation explicitly.

The existential means constraint and relative-deadline phrase are semantically
sound, but should remain explicit test cases as the grammar expands.
