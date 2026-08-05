# Base Units geometry research track

This is a separate, reproducible companion to the parcel dimensional-standard
exhibit. It asks three narrower questions:

1. How often does a City of Detroit Base Units building footprint occupy more
   than one assessor parcel?
2. How well does a geometry-derived street-facing edge agree with the
   assessor's `frontage` field?
3. Which parcel groupings are plausible *development-site candidates* for
   follow-up research?

It does **not** identify legal zoning lots. Tax parcels, Base Units links, and
spatial overlap are administrative/geometric evidence, not a substitute for a
recorded plat, deed, zoning determination, or title research.

## Official inputs

- City of Detroit `BaseUnitFeatures` feature service:
  - addresses: layer 0
  - streets: layer 1
  - buildings: layer 2
- City of Detroit current assessor parcels, represented in this repository by
  `pipelines/parcel-data/Parcels.geojson`

The Base Units service is maintained by Detroit DoIT. The current service
advertises data updates through June/July 2026. Buildings include a City
`building_id`, linked `parcel_id`, status, and footprint polygon. Streets
include `street_id`, names, address ranges, and centerline geometry.

## Run

```bash
python projects/detroit-land-use-forum/base-units-geometry/analyze_base_units.py fetch
python projects/detroit-land-use-forum/base-units-geometry/analyze_base_units.py analyze
```

The first command requires internet access. ArcGIS responses are downloaded in
2,000-record pages and cached in `data/`. The second command writes tables and
GeoPackages into `output/`. Add `--sample 10000` for a quick frontage
validation run.

The frontage estimator uses the edge of a parcel closest to its linked street
centerline, rather than the length of every parcel boundary inside an arbitrary
road buffer. It is a validation proxy. Detroit's ordinance definition of lot
width and corner-lot rules still require separate legal implementation.

