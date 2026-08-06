# Parcel geometry map: methodological review

## What the previous map actually did

The earlier artifact assigned each parcel a binary “buildable / not buildable”
label by comparing assessor parcel area and, in one version of the pipeline,
frontage against a district lookup table. It then mapped that result as green or
red. That is a useful exploratory screen, but the display made a much stronger
claim than the model could support.

## Critique

1. **The outcome was mislabeled.** Area and frontage alone cannot establish
   legality or buildability. Permitted use, lot-of-record status, setbacks,
   access, utilities, easements, overlays, site conditions, administrative
   adjustments, variances, and many other rules can change the answer.
2. **Unknowns silently became passes.** Missing area or width and districts
   absent from the lookup did not fail a check, so the derived binary could call
   them buildable.
3. **The lookup obscured why this pair of thresholds was selected.**
   Detroit’s dimensional standards vary by use, but the project’s ordinance
   table identifies 5,000 square feet and 50 feet as the lowest lot-area and
   lot-width pair in every R1–R6 district. Those are the single-family dwelling
   requirements and therefore serve here as the dimensional floor, rather than
   limiting the analysis to a proposed single-family use.
4. **The width measurement needs a qualification.** The assessor dataset calls
   its measurement `frontage`, while the ordinance regulates lot width. In the
   absence of contrary field documentation, frontage is retained as the best
   available proxy rather than discarded, but the visualization names the proxy
   and does not imply survey-grade precision.
5. **The parcel is not always the zoning lot.** Related or combined parcels can
   function as one zoning lot. The data does not resolve every such case.
6. **No allowance was made for measurement precision.** Exact comparisons to
   rounded assessor values create false precision near a threshold.
7. **Existing undersized lots were visually treated as defects.** Detroit Code
   §50-13-21 expressly permits a detached single-family dwelling on an R1–R6 lot
   of record on December 22, 1968, regardless of lot size, when other
   requirements are met. The parcel dataset does not establish that record date.
8. **The map lacked a denominator and uncertainty category.** A red parcel
   looked conclusive even when the observation was incomplete.

## Revised question and model

The forum artifact asks a narrower question:

> Where do assessed R1–R6 parcel dimensions fall below the 5,000-square-foot
> area or 50-foot width floor for development in those districts?

It covers R1–R6 parcels, uses `total_square_footage` and assessor `frontage`,
preserves missing or invalid measurements as “not evaluated,” and uses a uniform
1% tolerance—50 square feet and 0.5 feet—for rounded values. Frontage is described as the
best available proxy for regulated lot width; parcel-level confirmation would
still require authoritative lot records or a survey.

The 5,000-square-foot and 50-foot figures originate in the single-family
dwelling row of the dimensional table, but they are used because they are the
minimum—not because the map assumes that every parcel is proposed for a detached
house. Uses with larger requirements would produce additional mismatches that
this minimum-floor screen does not attempt to identify.

The result is described as a **dimensional mismatch**, never as an illegal or
unbuildable parcel. Improved and vacant parcels are reported separately. The
visualization also states the lot-of-record protection prominently.

## What this still does not establish

- Whether a parcel existed as a lot of record on December 22, 1968
- Whether adjacent or related parcels form one zoning lot
- Whether a particular use is allowed
- Compliance with width, setbacks, coverage, access, utilities, or other rules
- Whether an adjustment, variance, overlay, or other exception applies
- Whether a permit would be approved

Accordingly, this is a city-pattern exhibit and hypothesis generator—not a
parcel-level legal determination.

## Sources

- Detroit Code of Ordinances, Chapter 50, Article XIII, especially §§50-13-1
  through 50-13-7 and §50-13-21:
  https://library.municode.com/mi/detroit/codes/code_of_ordinances?nodeId=COCH50_CH50ZO_ARTXIIIINDIST
- City of Detroit parcel assessment dataset contained in this repository:
  `pipelines/parcel-data/parcels_with_compliance.gpkg`
