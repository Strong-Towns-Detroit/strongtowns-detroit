# BZA requested-relief classification

Last updated: July 26, 2026

## Result

All 496 `minutes_case` occurrences now have a classification state:

- 407 state at least one specific relief category;
- 76 identify a dimensional-variance route but do not name the requested
  dimension in that occurrence;
- 13 do not restate either the route or requested relief, almost entirely
  procedural dismissals, withdrawals, or lack-of-progress entries.

The classifier is multi-label. A case requesting a front-setback waiver,
additional lot coverage, and fewer parking spaces receives all three labels.
There are 122 multi-relief occurrences.

## Most frequent labels

These counts are meeting occurrences, not deduplicated applications:

| Requested relief or appeal | Occurrences |
|---|---:|
| Administrative or community appeal | 151 |
| Dimensional relief, detail not stated | 76 |
| Parking supply | 74 |
| Use spacing or separation | 62 |
| Setbacks or yards | 57 |
| Nonconforming use or structure | 47 |
| Lot coverage | 32 |
| Lot dimensions | 28 |
| Hardship relief | 20 |
| Height | 19 |
| Open or recreation space | 15 |
| Request not stated | 13 |
| Signs or billboards | 12 |
| Parking layout | 12 |
| Floor area or bulk | 11 |
| Screening or landscaping | 10 |
| Multiple principal buildings | 7 |
| Fences or walls | 1 |
| Loading | 1 |

The independently classified procedural routes are:

| Route | Occurrences |
|---|---:|
| Dimensional variance | 286 |
| Administrative appeal | 150 |
| Nonconforming review | 39 |
| Hardship petition | 20 |
| Use or spacing variance | 10 |

## Method

`../classify_bza_relief.py` removes known BZA boilerplate before applying
evidence-bearing regular-expression rules. This matters because the standard
jurisdiction paragraph mentions “minimum setbacks” even when the actual request
has nothing to do with a setback.

The output retains:

- pipe-separated `relief_categories`;
- pipe-separated `case_routes`;
- the exact matched phrases in `relief_evidence` and `route_evidence`;
- `classification_source`, distinguishing direct text, inheritance from
  another occurrence of the same case number, route-only classification, and
  requests not stated.

A classification may be inherited from another meeting occurrence with the
same case number when the later record only reports a postponement or dismissal.
Printed case numbers that collide within one meeting are excluded from this
inheritance rule.

## Outputs

- `classified_cases.csv`
- `classified_cases.json`
- `classification_summary.csv`
- `classification_audit.json`

## Publication cautions

The table above counts appearances in minutes. A matter heard on three dates
appears three times. It therefore describes **board workload and appearances**,
not the number of unique applications. A public graphic about the composition
of applications should first collapse continuances and rehearings into stable
case histories while preserving the known duplicate printed-number exception.

Proposed uses are not requested relief. For example, an accessory parking lot
is not classified as a parking-supply waiver unless the text actually requests
relief from required parking. Similarly, generic numeric distances are not
treated as use-spacing cases unless the text refers to spacing, locational,
drug-free-zone, radial-distance, or separation rules.

Four regression tests cover boilerplate suppression, short-distance false
positives, genuine radial spacing, and multi-label classification.
