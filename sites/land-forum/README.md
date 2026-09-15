# Land Forum

Detroit BZA minutes, mapped and explained. Land Forum is a project of Strong
Towns Detroit. The public site contains the home page, atlas, methods, and the
secondary chart studio. Other exhibits are preserved in Git history.

## Run and verify

```sh
npm ci
npm run dev
npm test
npm run typecheck
npm run tokens:check
NEXT_PUBLIC_SITE_URL=https://land-forum.example npm run build
node scripts/check_worker_assets.mjs
npm run test:browser
```

Install Playwright Chromium if needed (`npx playwright install chromium`). Browser
tests start the production server unless `CIVIC_TEST_ORIGIN` is set. The example
origin is for testing only; deployment rejects placeholder or localhost origins.

## Map publishing

The atlas and Instagram preview use the same prepared vector scene, rendered by
`@strongtowns/graphics-browser`. The scene is derived from the relief-map definition
in `projects/graphics/src/graphics/bza_cases_map.py`, including its original
basemap, EPSG:3857 transform, symbol areas, and deterministic displacement.

Explore by zooming, panning, selecting cases, or filtering. **Create graphic**
opens a modal and animates the whole-Detroit map into a 1080 × 1350 composition
in 500 ms (no animation with reduced motion). Zoom/pan does not affect export.
Filters preserve symbol positions and sizes. Headline and explanation are
editable; sources, legend, and Land Forum attribution are automatic. Preview
and PNG share the exact SVG and embedded Inter font.

Copy graphic link or save settings to preserve the data version, filters, and
text. Version 2 map recipes reference an immutable map, which references an
immutable case bundle. Version 1 chart recipes remain supported. Preserve
historical assets when publishing updates. Geographic subsets and drawn
boundaries are not part of this release.

For automated local map publishing, use the same browser export path:

```sh
node scripts/export_bza_map.mjs http://localhost:3000 latest /tmp/bza-map.png
node scripts/export_bza_map.mjs http://localhost:3000 saved-settings.json /tmp/bza-map.png
```

The older Python graphic command remains available to reproduce historical
locked exhibits. Use the browser export above for current Land Forum maps.

## Offline data preparation

`bza-release.lock.json` pins the BZA 1.1.0 release manifest by SHA-256. Restore
that release through the data repository first. This consumer never downloads
or rebuilds BZA evidence. From the Detroit repository root:

```sh
python sites/land-forum/scripts/build_bza_publication.py \
  --release-directory /path/to/verified/bza/1.1.0
```

Install the project's pinned data and graphics SDKs first. The builder verifies
all release files, resolves the existing boundary/water/street snapshots through
`strongtowns-data.lock.json`, reconciles 417 cases / 509 hearings / 408 mapped
cases, and writes immutable map and case bundles. It joins PDF links only using
explicit prepared-filename matches in the verified release provenance; missing
links are labeled. Changing release versions requires updating the reviewed
expected totals in the builder and tests as well as the pin.

Do not modify existing hashed files. Commit new public JSON bundles and their
latest pointers together. Do not commit generated PNG/SVG files or screenshots.

## Deploy

Authenticate Cloudflare, determine the actual custom or account-assigned
`workers.dev` hostname, then run:

```sh
NEXT_PUBLIC_SITE_URL=https://YOUR-ACTUAL-HOST npm run deploy:vinext
```

Deployment rebuilds with the supplied public origin, checks asset limits, and
uses the existing `land-forum` Worker configuration. The BZA deployment omits
parcel archives, frozen exhibits, and MapLibre workers; it needs no separate
parcel archive host. Verify the public atlas, export, direct case links, methods,
and social metadata before announcing launch. Keep the previous Worker version
available for rollback. Posting to Instagram is a separate editorial action.
