# Zoning rule engine and parcel web contract

## Purpose

This workstream turns reviewed Detroit zoning provisions into executable,
cited rules and applies them to named building scenarios. It supports both a
citywide explorer and exact parcel views without asking the browser to
interpret the ordinance.

The layers are intentionally separate:

```text
raw Municode snapshot → lossless HTML/node model → reviewed normalized rules
                      → parcel/scenario evaluation → generated web contract

DOCX export → comparison/regression adapter (not canonical legal source)
```

The canonical build is:

```bash
python pipelines/zoning/compile_ordinance.py
python pipelines/zoning/audit_chapter50.py
```

It writes three artifacts under `data/zoning-ordinance/`:

- `source-corpus.json` — all 18 Municode article/appendix payloads as 2,224
  source nodes and 17,334 derived paragraph/table blocks, retaining raw HTML,
  Municode node IDs, order, amendment metadata, and 1,982 numbered nodes;
- `executable-rules.json` — reviewed declarations compiled by the code-first
  DSL in `zoning/codebook.py` and `zoning/detroit_code.py`;
- `coverage.json` — explicit accounting of source, extracted candidates, and
  the much smaller reviewed executable scope.
- `chapter-50-package.json` — a section-by-section provision ledger joining
  every source block to broad provision classes, citations, review state, and
  any reviewed executable rules derived from that section.
- `candidate-provisions.json` — provenance-preserving permission, dimensional,
  definition, and Appendix A use-assignment candidates. The 29 antenna-table
  directives are retained as delegated-rule candidates rather than rejected
  as malformed permission codes; Appendix A mappings are not mislabeled as
  legal definitions.
- `cross-references.json` — every detected internal, contextual, and external
  citation with a resolution state, including reserved-range targets and
  apparent missing/incorrect source references.
- `applicability-scopes.json` — Article XI’s 12 special-purpose district
  divisions and six overlay-area subdivisions, with their numbered sections
  assigned by source heading order.

The first reviewed overlay rules are 61 explicit Gateway Radial Thoroughfare
prohibitions from §50-11-364. The B2/B4 list retains its underlying-district
scope; the all-district list uses a wildcard plus the Gateway overlay
condition. Two items with Woodward-only or Gratiot exceptions remain prose
candidates rather than being overgeneralized.

Unambiguous use-table codes are normalized according to §§50-12-3 through
50-12-5 and the explicit legends in §§50-12-108 and 50-12-109: `R` is
by-right, `C` requires conditional-use approval, `L` requires legislative
approval, and a blank cell is not allowed. Nine farmers-market asterisks are
compiled as accessory-only under §50-12-521. Composite `C/R` and `R/C` cells
and cross-reference text otherwise remain interpretation work unless their
operative prose has been reviewed; the compiler does not guess which branch
applies.

Section 50-12-162 now supplies six reviewed permission branches. In R3, a
multiple-family dwelling is by right below a 50-percent efficiency-unit share
and conditional at or above 50 percent. In B5 and PCA, it is by right with
ground-floor commercial or pedestrian-oriented space and conditional without
that space. The JSON evaluator reports `unknown` when the deciding project
fact is absent.

The reviewed permission layer now also contains decision trees for selected
composite cells covering brewpubs and micro-producers, lofts, mixed-use
residential projects, MKT offices, parking structures, rental halls, printing
shops, theaters, trade services, poultry processing, warehousing, B5/PCA
carry-out and fast-food restaurants, and B4 parking. Branch predicates retain
the facts named by the ordinance—such as floor area, retail share, project
form, overlay location, and ground-floor pedestrian space.

Article XII's antenna delegation is represented as an antenna rule system
rather than 29 copied permission values. The first reviewed tranche contains
41 Category D/general permission branches and six general provisions. Where
the ordinance says both “more than 120 feet” and “less than 120 feet,” the
exact 120-foot case remains unresolved instead of being assigned silently.

Unambiguous permission cells are also emitted into the executable package as
`structurally_verified`. This certifies deterministic transcription and the
source-defined meaning of the table code. It is weaker than `verified`:
use-specific regulations, final-column notes, overlays, and other applicable
provisions must still be evaluated before answering whether a project may
proceed.

The same structural tier contains 467 nonempty Article XVI definitions and
478 Appendix A assignments. They remain distinct types: a use-category
assignment is not a definition. Appendix A records cite their source document
without inventing section numbers that the appendix does not contain.

The 29 district dimensional tables contribute 728 simple numeric cells to the
same structural tier. Compound side-yard rules, formulas, textual values,
additional-regulation cells, and cross-references are not reduced to a single
number. The original combined row label is retained as the applicability
scenario until a reviewed use-specific declaration replaces it.

The remaining dimensional cells are typed rather than left as generic parse
failures: cross-references, Formula A/B references, compound standards,
ratio formulas, explicit no-minimum statements, inapplicable cells, table
structure, and genuinely unparsed text. Named formula candidates link to their
promoted computed rules after operative prose establishes precedence.

Formula precedence is now resolved by the operative text of §50-13-229, which
states that the resulting sum is divided by 15 (Formula A) or six (Formula B),
and that Formula B has a five-foot minimum. Both are expression ASTs, and the
80 district-table references are computed requirements evaluated from building
length along the adjoining lot line, building height, and measured side
setback. Missing inputs produce `unknown`.

The filling-station schedules in §§50-13-174 and 50-13-175 are represented by
two additive formulas plus four computed lot-width/lot-area branches, rather
than duplicating the displayed examples as 40 fixed rules. Applicability
retains pump-island count, service-bay count, gross floor area, restaurant
service, and Traditional Main Street status, and continues correctly beyond
the largest example shown in the table. Section 50-13-176 is intentionally withheld: its heading
says the station exceeds 600 square feet while its introductory sentence says
it does not exceed 600 square feet. That conflict requires source/legal
resolution rather than a parser guess.

The repeated `4 ft. minimum / 14 ft. combined` side-yard cells are split into
34 individual and combined-side-yard rules. Twelve values labeled `RSR` are
not treated as lot coverage: §50-13-239 establishes them as minimum
recreational-space formulas, evaluated as gross floor area multiplied by the
applicable recreational-space ratio. Direct filling-station references in
§§50-13-173 and 50-13-177 through 50-13-179 add ten more reviewed dimensional
rules for Traditional Main Street lots, lot coverage, buildings, pumps, and
other equipment.

Finally, all 17,334 Municode-derived paragraph and table blocks are emitted as DSL
`sourceProvisions` with `source_encoded` status. This closes representational
coverage of Chapter 50: no source block sits outside the DSL package. It does
not close legal normalization coverage; source provisions remain inert until
promoted to a typed permission, definition, requirement, procedure, exception,
or another reviewed declaration.

Paragraphs with recognizable legal effects are additionally emitted as typed
`machine_classified` candidates. A paragraph may yield more than one candidate
(for example, both a requirement and an exception). These declarations carry
their citations but remain inert until their subject, conditions, consequence,
and cross-reference semantics are reviewed.

The chapter package uses `source_encoded` to mean that the provision is
present and traceable—not that its legal effect has been normalized. A
section becomes `partially_reviewed_executable` when one or more named rules
have been reviewed from it; that status never implies the rest of the section
has been certified.

## Canonical Municode snapshot and export loop

The canonical upstream source is the immutable snapshot under
`resources/municode/<date>_job-<id>/`. Its manifest hashes the raw API response
bytes and every embedded figure. Build or verify a fresh version with:

```bash
python pipelines/zoning/snapshot_municode_chapter50.py
python pipelines/zoning/audit_municode_corpus.py
```

`compile_ordinance.py` uses the latest verified snapshot by default. Pass
`--source docx` only for legacy export comparison. The current snapshot is
Municode Supplement 4/job 429936, updated October 9, 2025. OrdBank ordinances
reported after that publication remain a separate amendment corpus until each
is reviewed for Chapter 50 applicability.

The Municode HTML tables corrected three DOCX-layout artifacts: the `35` in
§50-13-127 and `80` in §50-13-129 are height values, not lot coverage, and the
two-acre junkyard standard in §50-13-86 is lot area, not lot width.

### Closed DOCX/JSON comparison loop

The inspectable `source-corpus.json` records checksums and ordered source
blocks but deliberately does not duplicate 111 MB of source archives. Build a
separate lossless JSON package when exact recovery is needed:

```bash
python pipelines/zoning/roundtrip_ordinance.py pack
python pipelines/zoning/roundtrip_ordinance.py loop
```

The first command writes `source-corpus.lossless.json`. Each document entry
contains the original DOCX archive as base64 plus its byte count and SHA-256.
The second command decodes every document into a temporary directory and
checks two invariants:

1. the restored DOCX is byte-for-byte identical to its source archive;
2. re-extracting it produces exactly the same ordered paragraph/table model.

To recover editable copies without touching `resources/`:

```bash
python pipelines/zoning/roundtrip_ordinance.py restore \
  --output-dir data/zoning-ordinance/restored
```

Exact byte identity applies to a no-op round trip. An intentional source edit
necessarily changes the DOCX bytes; automatic iteration should instead
require the edited DOCX to reopen successfully and re-extract to the intended
semantic block model. Reviewed executable rules remain a separate package so
changing a hypothetical never mutates or misrepresents the source ordinance.

The evaluator in `zoning/json_engine.py` consumes the compiled JSON. It does
not import Detroit declarations. A hypothetical is represented by another
package (or a changed copy of a package), while the evaluation engine remains
unchanged.

The audit fails on lost source blocks, duplicate candidate identities, or
reviewed rules without source-section links. Its status totals are the honest
progress measure for the full-chapter conversion.

The current full-corpus scan contains 17,334 derived source blocks, including
224 tables. Automated extraction finds thousands of candidate permission and
dimensional cells, but those candidates must not be called executable until
their applicability, conditions, cross-references, and exceptions are
normalized and reviewed.

## First reviewed scope

The first rule set covers principal one- and two-family dwellings in R1–R6:

- minimum lot area;
- minimum lot width;
- front setback;
- minimum individual side setback;
- combined side setback;
- rear setback.

One-family table values are 5,000 square feet and 50 feet in R1–R6.
Two-family values are 6,000 square feet in R2–R6, with a 60-foot width in R3
and 55 feet in the other supported districts. The R1 table does not contain a
two-family row; the engine therefore returns `not_applicable` instead of
borrowing a rule from another scenario.

The reviewed rules live in `src/strongtowns_detroit/zoning/rules.py`. Tests
compare area and width values directly against the six tables in the
repository's Article XIII source document, guarding against silent source
drift.

The R1–R6 tables are §§50-13-2 through 50-13-7. Section 50-13-1 introduces
the residential tables but is not itself the R1 table.

## Result states

Every evaluation returns one of four states:

- `meets`
- `fails`
- `unknown`
- `not_applicable`

The legal threshold remains exact in the rule record. Any tolerance appears
only in the measurement/evaluation call. Missing measurements never become a
pass.

## Representative parcel contract

Run:

```bash
python pipelines/zoning/build_zoning_parcel_fixture.py
```

This generates:

`sites/land-forum/public/data/zoning/parcels/18007150.json`

The representative parcel is 1573 Livernois:

- assessor parcel `18007150.`;
- R2;
- recorded single-family use;
- one current City Base Units building footprint;
- high-confidence front edge linked through a Base Units address/street;
- 4,095 recorded square feet;
- 30 feet of recorded frontage;
- 1,082.23-square-foot principal footprint;
- 546.15 square feet outside the best ordinary setback alternative.

The fixture contains WGS84 geometry for:

- the parcel;
- the current principal footprint;
- the identified front edge;
- both permissible 4/10-foot side-yard envelope alternatives;
- the portion of the footprint outside the selected alternative.

It also contains cited area/width evaluations, the composite setback result,
measurement sources, tolerances, and limitations. This is enough to build the
first parcel-detail prototype without embedding legal calculations in React.

## Interpretation boundary

`fails` means that the recorded measurement or geometry fails the current
dimensional standard under the named scenario. It does not establish that an
existing structure is unlawful. The contract explicitly states that it has
not researched:

- lawful nonconforming status;
- variances or administrative adjustments;
- lot-of-record treatment;
- combined zoning lots;
- other parcel-specific approvals.

## Next analytical steps

1. Move the validated setback-envelope implementation into the shared package
   while retaining compatibility with the conference pipeline.
2. Add a first-class composite setback evaluation rather than composing its
   web representation inside the fixture builder.
3. Select fixtures representing `meets`, `unknown`, two-family, irregular,
   and possible multi-parcel cases.
4. Emit a small manifest and schema test for the website.
5. Design a scalable citywide classification artifact, retaining full
   geometry only for selected parcels and nearby context.
