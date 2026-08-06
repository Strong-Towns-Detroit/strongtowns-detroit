# BZA category exhibit opportunities

Last updated: July 27, 2026

## The important distinction

The minutes support a map of **where relief was requested** for nearly every
category. They do not, by themselves, show how many Detroit parcels or existing
buildings violate a rule.

An exhibit comparable to the minimum-lot-area graphic needs two independent
layers:

1. a citywide model applying a specific zoning rule to every eligible site; and
2. deduplicated BZA case histories showing how that rule reaches the board.

Where the first layer cannot yet be calculated, the honest alternative is a
case-location map paired with outcomes, requested-versus-required quantities,
time trends, or project types.

## Current corpus

The normalized corpus contains 405 deduplicated case histories. Categories are
multi-label: one application can request more than one form of relief.

| Category | Case histories | Mapped | Final grants | Final denials | Best exhibit form |
|---|---:|---:|---:|---:|---|
| Administrative/community appeal | 118 | 117 | 31 | 52 | Decision-review map and reversal rate |
| Parking supply | 62 | 62 | 55 | 3 | Requirements versus requested supply |
| Use spacing/separation | 45 | 45 | 18 | 22 | Required-radius map and outcome comparison |
| Setbacks/yards | 42 | 42 | 39 | 1 | Citywide buildable-envelope map |
| Nonconforming use/structure | 39 | 39 | 32 | 2 | Existing-place case map and project typology |
| Lot coverage | 30 | 30 | 27 | 1 | Citywide existing-coverage map |
| Lot dimensions | 28 | 28 | 24 | 1 | Separate lot-area and lot-width exhibits |
| Height | 18 | 17 | 15 | 0 | Requested-versus-allowed height graphic |
| Parking layout | 11 | 11 | 10 | 0 | Case map plus rule typology |
| Screening/landscaping | 9 | 9 | 8 | 1 | Small-multiple site diagrams |
| Signs/billboards | 8 | 8 | 2 | 0 | Case map; distinguish withdrawals |
| Floor area/bulk | 7 | 7 | 6 | 0 | FAR comparison once standards are encoded |
| Multiple buildings | 7 | 7 | 6 | 0 | Parcel/building-footprint diagrams |
| Open/recreation space | 6 | 6 | 6 | 0 | Required-versus-provided comparison |
| Fences/walls | 1 | 1 | 0 | 1 | Appendix only |
| Loading | 1 | 1 | 1 | 0 | Appendix only |

“Final grants” means `granted_reversed`; “final denials” means
`denied_upheld`. Dismissed, withdrawn, procedural, unresolved, and mixed
outcomes are not forced into either column.

## Strong citywide-map candidates

### 1. Lot width

**Question:** Where are recorded R1–R6 parcels narrower than the legal minimum?

This is the direct companion to minimum lot area. Assessor frontage is
available and the completed Base Units analysis provides a geometry-derived
street-facing edge for validation. The citywide run compared 367,047
frontages, with a median absolute difference of 0.13 feet and 97.1% within two
feet.

Before publication, split the 28 broad `lot_dimensions` histories into lot
area, lot width/frontage, depth, and other dimensional subtypes. Use the same
legal-boundary-plus-tolerance framing as the area exhibit.

### 2. Existing lot coverage

**Question:** How much of each parcel is covered by existing building
footprints, and where does that exceed the district maximum?

Required inputs are already local:

- assessor parcel geometry and zoning district;
- current Base Units building footprints;
- parcel/building links and material spatial overlaps.

The missing piece is a reviewed table of maximum lot coverage by district,
including use-specific and special-case rules. Multi-parcel candidate sites
must be treated separately because an assessor parcel is not always a zoning
lot. This would describe **existing physical nonconformity**, not whether a new
proposal would receive a permit.

### 3. Setback-constrained buildable envelopes

**Question:** After required front, side, and rear yards, how much land remains
available to build on?

Parcel depth, frontage, street-facing-edge estimates, and footprints make a
first model possible. The exhibit should map either:

- the share of parcel area remaining inside the legal envelope; or
- a binary result such as “no usable envelope remains.”

This requires district- and use-specific setback tables, corner/through-lot
logic, front-yard identification, and a defensible minimum usable-envelope
definition. Irregular parcels should be reported as a separate confidence
class. Existing buildings outside an envelope demonstrate inherited
nonconformity; they do not prove that a proposed addition is illegal.

## Strong exhibits requiring another dataset

### 4. Parking supply

This is the largest specific relief category and has an unusually lopsided
substantive outcome: 55 grants to 3 denials.

A true citywide map needs:

- the parking schedule by use, floor area, dwelling unit, or occupancy;
- reliable parcel/building use and intensity;
- existing off-street parking-space or parking-area inventory; and
- rules for shared parking, exemptions, reductions, and overlays.

The assessor file has `use_code`, `total_floor_area`, and building counts, so a
screening model is possible after the legal schedule is encoded. It will not
measure existing parking supply without a parking inventory. In the interim,
extract required and proposed spaces from the minutes and show the distribution
of requested reductions, alongside the case map and outcomes.

### 5. Use spacing and separation

This category has the clearest disagreement at the board: 18 grants and 22
denials, plus five non-substantive outcomes.

A strong exhibit would draw the applicable 500-, 1,000-, or other required-foot
radius around every regulated use, then show how much commercial land remains
available. That requires a dated, classified inventory of regulated and
protected uses. Current business-license, marijuana-license, school, religious
institution, park, and controlled-use data may each be needed. Because spacing
rules and businesses change, the map must state its effective date.

The immediate graphic can compare requested distance, required distance,
protected-use type, and outcome. The minutes often contain the relevant
distances, but these values need a structured extraction and audit.

### 6. Height

The BZA side is strong enough for a requested-versus-allowed height graphic,
but not yet for a citywide parcel map. Base Units does not contain building
height, and assessor `total_floor_area` cannot reliably infer it.

Possible added sources are City building-height data, LiDAR, or a reliable
3D-building dataset. Until then, extract allowed and proposed feet/stories from
the 18 histories and pair those comparisons with the 17 mapped sites.

### 7. Floor area and bulk

Parcel area and assessor total floor area permit an approximate existing FAR.
A legal comparison still requires district/use FAR standards and careful
treatment of multi-building and multi-parcel sites. With only seven histories,
this is a useful companion panel rather than a lead exhibit.

## Categories better represented by BZA activity

### Administrative or community appeals

These cases review earlier decisions; they do not share one physical rule that
can be applied citywide. Map the challenged decisions and compare reversals
with affirmances. Breakdowns by appellant type, underlying use, department,
district, and year would be more informative than coloring all ordinary
parcels “no appeal.”

### Nonconforming uses or structures

Legal nonconforming status depends on lawful establishment and continuity, not
geometry alone. Use a case-location map, outcome rate, project/use typology,
and selected before/after case studies. Do not infer nonconforming status from
assessor use versus zoning alone.

### Parking layout, screening, signs, open space, multiple buildings, fences,
and loading

These rules can produce excellent annotated site diagrams, but the current
case counts are small and the relevant facts are proposal-specific. A set of
small multiples showing the rule, the requested condition, and the outcome is
more legible and defensible than a citywide parcel binary.

## Recommended production order

1. Split `lot_dimensions` into area, width, depth, and other subcategories.
2. Build the lot-width companion to minimum lot area.
3. Encode district lot-coverage standards and build the existing-coverage
   exhibit.
4. Encode setbacks and prototype buildable envelopes with confidence flags.
5. Structure the numeric facts in parking, spacing, and height cases.
6. Build three request-versus-rule graphics from those structured facts.
7. Add selected small-multiple site diagrams for the rarer categories.

## Existing assets

The relief atlas already exports self-contained HTML, SVG, and PNG maps for all
publication-eligible categories:

- administrative/community appeals;
- parking supply;
- use spacing/separation;
- setbacks/yards;
- nonconforming uses or structures;
- lot coverage;
- lot dimensions;
- height; and
- parking layout.

Those maps answer **where did requests occur?** They should be retained as the
geographic half of future category exhibits, not presented as citywide
prevalence maps.
