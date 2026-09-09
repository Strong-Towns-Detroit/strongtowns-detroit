These two invented parcels and one road are browser-test fixtures, not Detroit
observations. IDs deliberately retain leading zeroes. `parcels.pmtiles` is the
small reviewed fixture archive used to test real MapLibre rendering and tile
inspection offline. Regenerate it from this directory with:

```sh
tippecanoe --quiet --force --output parcels.pmtiles --minimum-zoom 10 \
  --maximum-zoom 15 --full-detail 14 --no-tiny-polygon-reduction \
  --named-layer parcels:parcels.geojson --named-layer roads:roads.geojson
```
