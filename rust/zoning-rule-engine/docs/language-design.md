# Zoning language design

Status: working language contract, 2026-08-01.

This document records the decisions behind the first authored syntax for the
zoning rule engine. The syntax is intentionally small. New constructs should be
added when an enacted provision requires them, and existing distinctions should
only be collapsed after tests establish that they are semantically equivalent.

## One language, one typed module graph

The ontology is the type system of the legal language. Concepts, individuals,
relations, interpretive gaps, and rules are different declaration kinds in one
language. They may live beside one another or in imported modules; file layout
does not change their semantics.

```text
module detroit.article_iii.notice

concept LegalEntity
concept Organization is LegalEntity
concept PublicAgency is Organization

relation responsible_for
  bearer: LegalEntity
  action: LegalAction
  subject: LegalMatter

  phrase
    "{bearer} is responsible for {action:gerund} {subject}"

rule minimum_bseed_notice
  ...
```

Rules cannot be compiled without their type environment. Conversely, ontology
declarations are useful because rules and facts refer to them; they are not a
separate abstract exercise.

## Concepts, specialization, and bounded relations

`is` declares conceptual specialization or individual membership:

```text
concept LegalEntity
concept Organization is LegalEntity
concept PublicAgency is Organization

entity BSEED
  is CityDepartment
  is HearingForum
```

A relation declares named roles with type bounds:

```text
relation responsible_for
  bearer: LegalEntity
  action: LegalAction
  subject: LegalMatter
```

This is bounded polymorphism at relation-definition time. Any subtype of the
declared role type may fill that role. It is not an untyped relation over every
concept, and it is not a function: it does not imply a unique output for an
input. Cardinality or uniqueness must be stated separately when the law
actually establishes it.

The first implementation uses concept specialization. Trait-like roles,
unions, and additional polymorphism remain possible, but should not be added
until a provision demonstrates the need.

## Controlled phrases are typed symbol references

Relations may declare a readable phrase. Placeholders refer to named relation
roles, and optional selectors such as `:noun` and `:gerund` select a declared
surface form of an individual:

```text
relation requires_action
  authority: LegalInstrument
  action: LegalAction
  subject: LegalMatter

  phrase
    "{authority} requires {action:noun} of {subject}"
```

Given an action declaration with `noun "publication"`, the authored phrase:

```text
Chapter50 requires publication of hearing_notice
```

resolves to the canonical relation application:

```text
requires_action(
  authority: Chapter50,
  action: publish,
  subject: hearing_notice
)
```

Every phrase occurrence must resolve to exactly one canonical typed
proposition. A `relation` records durable domain structure among independently
typed things. A `predicate` names a truth-valued proposition that may be
supplied as evidence or derived by a rule. Legal force comes from the rule
conclusion, not from the predicate declaration.
The compiled form preserves:

- the proposition identity and whether it is a relation or predicate;
- argument-role identities;
- local bindings or individual identities;
- declared and inferred types;
- source position; and
- the authored phrase.

Phrase collisions are compile errors. The canonical proposition, not its English
rendering, is the semantic identity. Tooling should provide hover information,
go-to-definition, references, inferred types, and the normalized proposition.

The phrase language is controlled syntax, not unrestricted natural language.

## `for every` binds inputs; `given` states applicability

`for every` introduces the rule's universally quantified typed input
signature. `given` contains only propositions that must all match. It does not
assert those propositions and it does not create legal effects. Rev1's
`given all` remains accepted temporarily for old artifacts.

```text
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

Here `responsible_for` is necessary because §50-3-10 does not identify the
responsible agency. The relation binds whichever agency has been assigned that
responsibility elsewhere. Multiple `given` entries are conjunctive;
alternatives require an explicit alternative construct when one is introduced.

## Rules produce normative effects

The initial consequence is a duty with a typed bearer, action, subject, and
deadline:

```text
require duty
  bearer: agency
  action: publish
  subject: hearing_notice
  deadline: at least 15 days before hearing
```

The action does not contain its subject. `action: publish` and
`subject: hearing_notice` are distinct typed roles.

Provisions may impose additional typed performance constraints:

```text
using some newspaper: Newspaper
  satisfying
    newspaper has general circulation in Detroit
```

These are not free-form manner strings. Their concepts and relations must be
declared in the same type environment.

The duty is sourced by its containing rule, so source provenance is not copied
into every conclusion field.

Vote requirements use a dedicated effect rather than an opaque English
predicate:

```text
require concurrence
  decision: decision
  threshold: majority
```

The compiler normalizes `majority` to
`2 * concurring_votes > member_count` and `two_thirds` to
`3 * concurring_votes >= 2 * member_count`. These are exact integer
inequalities. The legal meaning of `member_count` may still require a separate
sourced definition, but the arithmetic itself is not interpretive.

## Interpretive gaps are first-class

An ordinance may use an open-textured standard without defining a decision
procedure:

```text
interpretive relation has_general_circulation_in
  publication: Newspaper
  area: GeographicArea

  phrase
    "{publication} has general circulation in {area}"

  resolution
    status: open
    method: not defined by Chapter 50
```

This is an **interpretive relation** containing an **interpretive gap**. The
source has been captured and typed, but the relation is not operationally
derivable from Chapter 50 alone. This is different from unfinished extraction.

Interpretive relations use open-world, three-valued reasoning: true, false, or
unresolved. Absence of a supporting fact is not false. A later judicial,
administrative, or incorporated definition should be added as a sourced,
jurisdictional, and temporal interpretation rather than overwriting the
ordinance declaration.

Operational-resolution categories currently anticipated are `defined`,
`externally_defined`, `authoritative_determination`, `interpretive`, and
`unresolved`. The initial parser implements explicit open interpretive
relations; the broader taxonomy will be added as source examples require it.

## Defeasibility and related constructs remain distinct

- **Defeasible rule:** its conclusion may be defeated by another applicable
  rule.
- **Exception:** circumstances that stop or alter an ordinary rule.
- **Override:** an explicit priority relation between rules.
- **Alternative:** a different legal procedure or result, not merely negation.
- **Strict rule:** its conclusion necessarily follows when its premises hold.

An explicit exception may be compiled into a negated condition, but doing so
can obscure the source structure. The language therefore preserves exceptions,
alternatives, and overrides separately. Rule strength is omitted when it has
not been classified; omission means unknown, not `false`.

## Provenance and round-trip traceability

Every rule and interpretation retains its exact source spans. Every semantic
phrase retains a reference to its canonical declaration. Compiled output is a
projection of the typed AST, not a replacement source format.

The long-term closed loop is:

1. inventory every source proposition;
2. bind each proposition to exact immutable source spans;
3. encode its typed legal meaning;
4. compile controlled phrases to canonical relations;
5. test the normalized result and identified interpretive gaps;
6. occlude each source proposition in turn and verify that the model exposes
   the missing coverage; and
7. render a review form that links every normalized construct back to source
   and declaration.

## First complete example

The executable fixture lives at
`examples/minimum_bseed_notice.zdl`. Its intended reading is:

> For any agency responsible for publishing a notice of a public hearing held
> before BSEED, where Chapter 50 requires that publication, the agency has a
> duty to publish the notice at least 15 days before the hearing using some
> newspaper that has general circulation in Detroit.

Whether a particular newspaper has general circulation in Detroit remains an
explicit interpretive gap.
