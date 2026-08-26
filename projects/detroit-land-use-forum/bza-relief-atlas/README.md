# Detroit BZA relief atlas

This atlas maps one BZA **case history** per site and relief category. Continued
hearings and rehearings do not inflate the count. A case can appear in more than
one map when it requested more than one kind of relief.

The build consumes the normalized tables in
`pipelines/zoning/bza_dataset_gemini/`. A standalone category must have at least
10 case histories and at least 80% of those histories matched to an assessor
parcel. Quality-assurance categories are never published as relief maps.

Reviewed case-level classifications live in
`pipelines/zoning/bza_relief_case_reviews.csv`. They are applied by the case
history builder, so regenerate the normalized inputs in this order after
editing that ledger:

```bash
python pipelines/zoning/build_bza_case_histories.py
python pipelines/zoning/normalize_bza_outcomes.py
python pipelines/zoning/build_bza_atlas_dataset.py
```

The analytical tables distinguish `parking_supply` from `parking_layout`.
Primary-request overview maps roll both up to the parent display category
`Parking`; the generic `parking` value is reserved for cases whose subtype is
not stated in the minutes.

Build the complete eligible series:

```bash
python pipelines/zoning/build_bza_atlas_dataset.py
python projects/detroit-land-use-forum/bza-relief-atlas/build_atlas.py
```

Build one eligible category:

```bash
python projects/detroit-land-use-forum/bza-relief-atlas/build_atlas.py \
  --category parking_supply
```

Case locations render as fixed-size dots by default so citywide maps remain
legible. The renderer also retains parcel geometry as an option:

```bash
python projects/detroit-land-use-forum/bza-relief-atlas/build_atlas.py \
  --site-render-mode parcels

python projects/detroit-land-use-forum/bza-relief-atlas/build_atlas.py \
  --site-render-mode both
```

Supported modes are `dots`, `parcels`, and `both`. The selected mode is written
to `output/manifest.json`.

Each map is exported as self-contained HTML and SVG plus a 3200-pixel PNG when
`rsvg-convert` is installed. `output/index.html` is the series contact sheet.

The current geographic encoding answers **where was this relief requested?**
Final board outcomes appear as a compact count, not as map colors. The dataset
retains normalized outcomes so a paired or outcome-colored edition can be
generated later without reclassification.
