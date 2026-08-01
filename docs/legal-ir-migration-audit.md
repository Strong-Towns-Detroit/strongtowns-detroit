# Source-span legal IR migration audit

## Decision

The reviewed zoning model should be rebuilt around **atomic source spans**, not
around Python declaration modules. Each legally operative span is selected in
the canonical Municode HTML, reviewed in isolation with its necessary context,
and represented by a declarative legal-IR record. Executable rules are a
projection of those records.

The governing closed loop is:

1. enumerate and highlight one source span;
2. classify it as operative, contextual, non-operative, or unresolved;
3. hide the source span from the reconstruction;
4. render the legal-IR record back into a source-shaped reconstruction;
5. compare the reconstruction with the hidden source;
6. test the executable projection at every boundary and exception;
7. mark the span covered only when both reproductions pass.

This is stricter than the current section-level linkage. A section is not
"reviewed" merely because one rule cites it.

## Existing reviewed patterns

| Module | Pattern encoded | Important hidden assumptions |
|---|---|---|
| `detroit_code.py` | Hand-authored R1-R6 one- and two-family minima and setbacks | Values are duplicated rather than derived from table cells; a section and a general cross-reference are treated as joint authority; symbolic exceptions are asserted but not encoded or evaluated; `building_role=principal` is added without a pinpoint source. |
| `detroit_dimensions.py` | Numeric Article XIII table cells | A recognized heading identifies the district; a slugged row label is the legal use/scenario; the cell is complete despite notes and cross-references; leading-number parsing captures the legal operator and unit. |
| `detroit_compound_dimensions.py` | One side-yard cell split into individual and combined minima | Exact English shape is fixed by regex; §50-16-382 applies to every promoted cell; both derived requirements share one undifferentiated source fragment. |
| `detroit_formulas.py` | Formula A/B definitions plus table references | Formula prose is faithfully reduced to arithmetic; variables have agreed meanings; every named table reference points to the same formula; rounding rules are absent. |
| `detroit_recreational_space.py` | RSR cells projected as gross-floor-area formulas | RSR means recreational-space ratio in every matched cell; the ratio applies to the selected scenario; §50-13-239 supplies all semantics not present in the cell. |
| `detroit_filling_station_dimensions.py` | Additive lot-area formulas and ten direct standards | Fixed table cells and continuation rows are equivalent to an unbounded formula; pump/service-bay baselines are two; exclusions for Traditional Main Streets and restaurant service are complete; manually created predicates exactly represent prose. |
| `detroit_special_district_dimensions.py` | SD1/SD2 front, side, rear, height, and parking branches | Long prose is decomposed into mutually correct branches; thresholds are exhaustive; terms such as protected neighbor, mixed use, and rear street/alley have settled meanings; a shared generic source string stands in for multiple clauses. |
| `detroit_permissions.py` | R/C/L/dash and accessory-only table cells | Permission symbols have one global meaning; dash means prohibited; final-column standards are separable; a citation stored in `conditions` is a condition rather than merely authority. |
| `detroit_conditional_permissions.py` | 108 hand-authored composite permission branches | Boolean/numeric predicates are complete, mutually exclusive when intended, and use consistent units; manual use IDs match table uses; omitted branches correctly remain unknown; comments and labels substitute for pinpoint quotations. |
| `detroit_antenna_rules.py` | District branches and general antenna provisions | District lists and distance tests fully represent several sections; home/district distance is reduced to synthetic measurements; a known 120-foot textual gap remains while declarations are marked verified; paraphrases replace exact spans. |
| `detroit_overlay_rules.py` | Gateway overlay prohibition list | Paragraph order and temporary parser state reconstruct list hierarchy; `*` means all districts; two complex items can simply be skipped; source-index-based IDs remain stable; overlay applicability is stored as a string condition rather than a predicate. |
| `detroit_lexicon.py` | Definitions and Appendix A assignments | A two-column table is semantically a definition/assignment; repeated or nested content is absent; Appendix entries without numbered sections can be identified by positional candidate IDs. |
| `detroit_source_provisions.py` | Complete, non-executable source ledger | A whole paragraph or rectangularized table is a useful review atom; broad keyword classes do not imply legal effect. This is coverage infrastructure, not reviewed law. |
| `detroit_text_candidates.py` | Machine-classified prose candidates | Keywords approximate effect; one paragraph may yield several candidates; source order and nested clause structure are not semantic. These must not migrate as reviewed records. |

## Provenance lost after source parsing

`municode_source_model.py` retains `municodeNodeId`, `docOrderId`, section,
`sourceIndex`, and exact `sourceHtml`. The downstream `Source` type retains only:

- a synthetic document filename;
- one or more section numbers;
- a free-text `source_value`;
- an optional note.

Consequently, current reviewed declarations generally lack:

- snapshot/job and manifest hash;
- Municode node ID and document order;
- exact HTML span or selector;
- paragraph/list/table identity within the node;
- table row, column, logical header path, `rowspan`, and `colspan` origin;
- character offsets and an exact quote hash;
- separate spans for antecedent, exception, definition, table cell, footnote,
  and cross-referenced modifier;
- an explicit link from a machine candidate to its reviewed replacement;
- provenance for interpretive additions such as predicates, units, operators,
  slugs, and exception names.

Candidate IDs use `document:sourceIndex:type:offset`. They are positional and
can change when HTML structure or parser traversal changes. Table parsers emit
flattened items without original row/column coordinates, so a cell cannot be
reliably highlighted again from the reviewed artifact.

## Model gaps independent of provenance

- `when` supports only conjunction. Disjunction is simulated with branches;
  negation, applicability precedence, and branch exhaustiveness are implicit.
- Conditions and exceptions are often opaque strings and are not evaluated.
- Definitions, permission symbols, cross-references, and substantive rules are
  separate collections without a first-class dependency graph.
- No representation distinguishes conjunctive requirements from alternatives,
  provisos, exceptions-to-exceptions, discretionary standards, procedures,
  delegated authority, or source conflicts.
- The same legal concept has multiple manually selected IDs and field names.
- Units and denominators are declared but not anchored to the words that supply
  them; rounding, measurement, and boundary conventions are usually absent.
- `verified` is not evidence of reviewer, date, reviewed spans, interpretation
  rationale, or tests performed.
- Tests predominantly assert counts and selected evaluation examples. They do
  not prove source-span coverage, non-overlap, branch completeness, or faithful
  reconstruction.

## Minimum legal-IR record

Every record should contain, at minimum:

```json
{
  "id": "detroit:2025-10-09:node-123:table-1:r4:c7",
  "sourceSpans": [
    {
      "snapshot": "2025-10-09_job-429936",
      "manifestSha256": "...",
      "municodeNodeId": 123,
      "docOrderId": 456,
      "section": "50-13-2",
      "block": {"kind": "table", "ordinal": 1},
      "cell": {"row": 4, "column": 7, "headerPath": ["R1", "Lot area"]},
      "htmlSelector": "...",
      "exactText": "5,000",
      "exactTextSha256": "...",
      "role": "operative_value"
    }
  ],
  "subject": {},
  "effect": {},
  "conditions": [],
  "exceptions": [],
  "alternatives": [],
  "dependencies": [],
  "interpretations": [],
  "review": {
    "status": "human_verified",
    "reviewer": "...",
    "reviewedAt": "...",
    "sourceReproductionTest": "...",
    "executionTest": "..."
  }
}
```

Context spans must be explicit and role-labelled. A table cell may depend on a
row label, nested column headers, introductory prose, a footnote, a definition,
and a referenced section; citing only the cell is insufficient.

## Staged migration order

1. **Source-span substrate.** Assign stable IDs to HTML elements, list items,
   text spans, and physical/logical table cells. Preserve original span geometry
   before rectangular expansion. Produce a review page that highlights exactly
   one atom and its declared context.
2. **Non-operative accounting.** Classify headings, histories, reserved text,
   notes, and purely connective text. This establishes total-denominator
   coverage without pretending all prose is executable.
3. **Lexicon.** Migrate definitions and Appendix A assignments. These are mostly
   direct transcription and create vocabulary needed by later rules.
4. **Permission symbol definitions, then simple permission cells.** Encode the
   symbol semantics first as dependencies. Migrate R/C/L/dash cells with row,
   column, header, note, and use-standard spans attached.
5. **Simple numeric dimension cells.** Migrate one table at a time, including
   header paths, units, notes, and applicability rows. Do not bulk-promote based
   only on a parsed number.
6. **Compound cells and named formulas.** Migrate side-yard pairs, Formula A/B,
   RSR, and filling-station tables. Require a reconstruction of every component
   and formula truth-table tests.
7. **Direct prose rules.** Migrate the ten filling-station standards and other
   short requirements/prohibitions, one clause at a time.
8. **Composite permission branches.** Migrate each use-specific section; prove
   branch exclusivity, exhaustiveness or intentional unknown gaps, and exact
   threshold behavior.
9. **Long special regimes.** Migrate antenna, SD1/SD2, and Gateway overlay rules
   only after the IR supports nested exceptions, alternatives, cross-reference
   dependencies, and unresolved conflicts.
10. **Retire Python legal meaning.** Keep Python as validators, evaluators, and
    artifact generators. Remove a hand-written declaration only after its IR
    replacement has semantic-equivalence and provenance tests.

## Acceptance tests

### Per source atom

- The span resolves uniquely against the pinned snapshot and its hashes match.
- Highlighting selects the exact words/cell, not merely the section.
- Every included context span has a declared role; no undeclared prose is used.
- Occluding the atom and rendering the IR reproduces its normalized text/table
  meaning; exact typography may remain a source-renderer concern.
- The atom has exactly one disposition: encoded, contextual, non-operative,
  duplicate-with-link, or unresolved. Nothing silently disappears.

### Per legal record

- Every semantic field has one or more supporting spans or an explicit,
  reviewable interpretation note.
- Dependencies resolve to versioned records.
- Predicate branches do not overlap unless precedence is declared.
- Finite domains are exhaustive; intentional gaps produce `unknown` and are
  named in the record.
- Numeric tests cover below, exact, and above each boundary, missing inputs,
  unit conversion, and formula minima/caps.
- Exceptions are executable or explicitly reported as unevaluated; a string in
  an `exceptions` list is never treated as completed logic.

### Per section and chapter

- Source-span accounting is 100% against the pinned Municode snapshot.
- A coverage report distinguishes source encoded, legally reviewed, executable,
  contextual, non-operative, and unresolved percentages.
- Removing any reviewed record causes at least one occlusion/reconstruction or
  executable test to fail.
- Adding, deleting, or changing upstream Municode HTML produces a source-drift
  failure rather than silently re-keying positional IDs.
- Generated artifacts contain no executable rule whose supporting spans fail
  resolution, and no claim of full-section review based on partial linkage.

## First migration slice

Use one small Article XIII dimensional table as the vertical prototype. It
exercises nested table headers, scenario rows, numeric operators/units,
cross-referenced notes, highlighting, occlusion, reconstruction, and executable
parcel evaluation without first requiring the IR to solve discretionary prose.
The slice is complete only when every source atom in that section has a recorded
disposition and each numeric rule passes boundary tests.
