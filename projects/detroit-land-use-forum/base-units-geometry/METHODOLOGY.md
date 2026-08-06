# Methodology and decision record

## Why this layer is useful

The dimensional-standard exhibit presently treats one assessor parcel as the
unit of analysis. Detroit's own parcel-service description cautions that
parcels are ownership units. That makes them appropriate for assessment and
ownership analysis, but not automatically equivalent to a platted lot, a lot
of record, a development site, or a zoning lot.

Base Units supplies two useful cross-checks:

- a building footprint carries a stable `building_id` and a linked
  `parcel_id`;
- an address can link parcels and buildings to a City `street_id`, whose
  centerline has authoritative name and address-range attributes.

These links let us describe how the administrative units relate without
pretending they are interchangeable.

## Building-to-parcel analysis

The pipeline reports two distinct facts:

1. **Administrative link:** whether the building's Base Units `parcel_id`
   matches a current assessor parcel after punctuation-insensitive ID
   normalization.
2. **Spatial overlap:** every current assessor parcel materially intersected
   by the footprint.

An intersection is "material" when it covers at least 10 square feet and at
least 2% of the building footprint. This prevents tiny boundary slivers caused
by precision or vintage differences from creating false multi-parcel
buildings. Both thresholds are parameters and should receive a sensitivity
check before publication.

When one footprint materially overlaps two parcels, those parcels become a
high-value **candidate site** for research. Connected components are used so
multiple footprints can join a larger group. The output is deliberately named
`building_linked_candidate_sites`, not `zoning_lots`.

### What this cannot establish

- A footprint crossing an assessor line may reflect a geometry error.
- Separate assessor parcels may already be legally combined for zoning.
- Adjacent parcels in common ownership are not necessarily one zoning lot.
- A Base Units parcel link is a database relationship, not title evidence.

A legally defensible zoning-lot determination needs recorded instruments,
plats, deeds, permit/zoning records, and sometimes a City determination.

## Street-facing-edge analysis

The preferred route is:

1. use the Base Units address record attached to the parcel;
2. follow its `street_id` to the corresponding Base Units street centerline;
3. split the parcel exterior into individual straight edges;
4. select the closest edge reasonably parallel to that street;
5. compare its length with assessor `frontage`.

If a parcel has no usable address-to-street link, the nearest Base Units street
is used and the source is recorded. Confidence is:

- **high:** a parallel edge within 80 feet and within 15 degrees;
- **medium:** a parallel edge meeting the broader 35-degree test;
- **low:** no reasonably parallel edge, so only the nearest edge is returned;
- **not evaluated:** missing or invalid geometry.

All distance and length calculations use Michigan State Plane South,
EPSG:2898, whose units are US survey feet.

### Why this is validation, not a replacement width field

The ordinance's "lot width" is not universally identical to street frontage.
Corner lots have multiple street-facing edges; curved, flag, through, and
irregular lots require special treatment; and the applicable measurement line
can differ from the front boundary. The geometry estimate is therefore useful
for testing whether assessor frontage behaves plausibly at scale. It should not
silently replace the assessor field in the forum model.

## Publication gate

Before a forum graphic is promoted from draft:

1. report the building-to-parcel ID join rate;
2. inspect a stratified sample of unmatched buildings;
3. run overlap-threshold sensitivity at 5/10/25 square feet and 1%/2%/5%;
4. report median absolute frontage error and the shares within 2 and 5 feet;
5. inspect at least 50 large frontage disagreements, including corner lots;
6. separate address-linked estimates from nearest-street fallbacks;
7. label all multi-parcel groupings as inferred candidates.

## Official sources

- City of Detroit, **BaseUnitFeatures FeatureServer**, item
  `2b9ab7687289457c9793a4a92d7c4eb9`, layers 0–2.
- City of Detroit Office of the Assessor, **Parcels Current** FeatureServer,
  item `9ca25373d4f747be85850344186dda3c`.

The BaseUnitFeatures metadata observed July 26, 2026 reports building edits
through June 25, 2026, street edits through June 9, 2025, and address edits
through July 2, 2026. The fetch script preserves local snapshots so results can
be reproduced against an identified vintage.
