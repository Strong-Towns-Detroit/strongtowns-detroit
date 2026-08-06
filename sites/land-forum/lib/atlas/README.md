# Atlas — the mapping library

One renderer, two outputs: an interactive map and a frozen exhibit board, from
the same components and the same `MapSpec`.

Published so far:

- Four-state rules: **minimum lot area**, **minimum lot width**, **setback envelope**
- Quantity choropleths: **assessed value per acre**

## Why it exists

The project had two mapping stacks that had already drifted:

- **Python/matplotlib** produced the conference boards. The parcel maps are not
  vector — `03-minimum-lot-area.svg` contains **zero `<path>` elements** and one
  embedded **3.62 MB JPEG** rendered at `dpi=435`.
- **TypeScript/MapLibre** produced the BZA atlas.

The drift was measurable: 71 distinct hex colours in the Python exhibits, 29 on
the web, only 22 shared, and **two different reds in production** — `#c83a3a` in
the flagship parcel exhibits, `#c8102e` on the website. A poster and a page
built from separate code will always diverge. So they no longer are.

## Two kinds of publication

A **rule** asks a yes/no question and answers it in four states — meets, fails,
not enough information, out of scope. A **quantity** does not: nothing passes or
fails assessed value per acre. It carries a band per parcel and reports a
distribution statistic. They share `MapSpec`, `MapCanvas`, and `ExhibitFrame`,
and diverge only in their config shape (`ParcelRuleConfig` vs
`QuantityMapConfig`) and their explorer/poster components.

### Binning stays in Python

`ColorRule` has a `threshold` variant and the assessed-value map does not use
it. The exhibit's bands are exclusive at the lower edge and inclusive at the
upper (`> lower && <= upper`); MapLibre's `step` is inclusive-lower, and the two
disagree at exact boundaries. Rounding the value so the edges line up would move
parcels across bands. So the published classifier assigns the band, the tiles
carry a band key, and the browser paints a category — which is also just the
architecture's own rule about who owns classification.

## Adding a rule

A parcel dimensional standard is configuration, not code:

1. Add a classifier to `scripts/build_parcel_tiles.py` `RULES` — importing the
   published test from its exhibit builder, never restating it.
2. Add a `ParcelRuleConfig` to `specs/rules.ts`.
3. Add two five-line route files under `app/publications/<slug>/`.

That is the whole diff. `ParcelRuleExplorer`, `ParcelRulePoster`,
`ParcelRulePage`, and `parcelRuleSpec()` are shared.

Routes are static directories rather than one `[rule]` segment on purpose:
vinext's prerenderer probes dynamic routes without a trailing slash, and
`trailingSlash: true` answers 308, which it reports as `RSC handler returned
308` and refuses to export. `next build` handles it; `npm run build` does not.

## Files

| File | Role |
| --- | --- |
| `types.ts` | `MapSpec`, `LayerSpec`, `ColorRule` — a map is data, not code |
| `paint.ts` | What a `ColorRule` means, as a MapLibre expression *and* in JS |
| `paint.test.ts` | Asserts those two readings agree — they once did not |
| `tiles.ts` | Decodes a single tile for click inspection (not the paint path) |
| `MapCanvas.tsx` | MapLibre painting MVT straight from PMTiles; sets `data-map-ready` |
| `ExhibitFrame.tsx` | Frozen board at 1600×1100, matching the printed geometry |
| `specs/parcel-rule.ts` | The shared spec factory for every dimensional standard |
| `specs/rules.ts` | One config object per published rule |

## Renderer

MapLibre paints MVT directly out of the PMTiles archive via the `pmtiles://`
protocol. Tiles are parsed in MapLibre's worker pool and turned into GPU buckets
without ever materialising hundreds of thousands of GeoJSON objects on the main
thread. Colour, draw order, and zoom ranges are all expressed as style
expressions built in `paint.ts`.

An earlier version drove deck.gl over the same archive. That was replaced, and
the replacement is better on both axes that matter here: it does not decode
tiles on the main thread, and it agrees far more closely with the printed
boards (95.6% vs 86.0% — see below).

Inspection is deliberately separate from painting. A click is converted to a
tile coordinate, that one tile is decoded, and point-in-polygon finds the
parcel; candidates are then ranked by the same `drawOrder` the paint layer uses,
so the inspector always names the parcel the reader can actually see. This keeps
picking attributes out of the render path entirely.

three.js was considered and rejected: it has no geospatial primitives, so
projection, tile LOD, camera constraints, and label collision would all have to
be built before the first map drew.

## Data

### Two tiers, one build

| Archive | Zooms | Size | Role |
| --- | --- | --- | --- |
| `parcels-display.pmtiles` | z10 only | ~9 MB | citywide painting, and what the frozen board captures |
| `parcels.pmtiles` | z10–z15 | ~58 MB | painting when zoomed in, and every click lookup |

A single z10 tile out of the full archive is several megabytes, which is a poor
first paint for a map whose opening view is the whole city — hence the overview
tier. Both are written by one run of `build_parcel_tiles.py` from one
classification pass.

That last point is load-bearing. The display tier originally existed as a
hand-built file that nothing in the repo reproduced, so adding the setback
column to `parcels.pmtiles` left the overview a rule behind: the citywide map
painted every parcel grey while the headline still read 87%, because the paint
expression looked up `st_setback` in an archive that had never heard of it. A
generated artifact no build step owns will drift the moment the schema moves.

One archive carries every rule as its own column (`st_area`, `st_width`, …),
because all rules share the same 378,366 geometries. Two rules cost 51.1 MB;
one archive per rule would have been 104 MB and would make layer switching a
download rather than a repaint.

`tippecanoe` runs with `--drop-rate 1`, `--no-feature-limit`, and
`--no-tile-size-limit`. Deliberate: the default density thinning would silently
change the colour proportions of a citywide choropleth, and those proportions
*are* the finding. PMTiles is read over HTTP range requests, so the browser
fetches only the tiles in view and it serves from object storage with no tile
server.

Verified faithful — decoding the archive through the same loader the app uses
gives a meets:below **area** ratio of 0.99 at z10, 1.00 at z12, and 0.99 at
z14, against 1.00 measured on the source geometry.

The archive is gitignored. Rebuild with `npm run tiles:parcels`
(needs `brew install tippecanoe`).

## Freezing a board

```bash
npm run dev                                   # in one shell
npm run freeze:lot-area                       # in another
npm run freeze:lot-width
```

Three details that matter:

- **Supersampling.** matplotlib drew at ~4700px into a 2030px well. The
  exporter renders at `scale × supersample` and averages down in-page using
  Chromium's own resampler, so there is no native image dependency.
- **A failed tile must never resolve to an empty tile.** `loadTile` originally
  swallowed anything whose message was `"Failed to fetch"`, on the theory that
  deck.gl cancels in-flight tiles whenever the camera moves. But a real network
  failure says exactly the same thing, so a tile that failed to load returned
  `[]`, deck.gl cached that as a loaded tile, and the board permanently rendered
  a band containing no parcels — silently under-reporting the thing the map
  exists to count. Only `AbortError` is swallowed now; everything else
  propagates so deck.gl can retry and the exporter fails loudly.
- **Capture is verified, not predicted.** Three attempts to forecast "loading is
  finished" each failed: `data-map-ready` let a tile band through;
  frame-stability sampling moved the flake from lot-width to lot-area; adding a
  tile-network quiet check still let the first cold run differ. The exporter now
  captures repeatedly until two consecutive captures are byte-identical.

Both boards are **deterministic against a cold dev server** — three independent
renders each produce a single SHA, byte-identical to the known-settled state.

Note: on a cold Next.js dev server one tile fetch typically fails (range
requests against a 51 MB file while the server is still compiling) and the
exporter reports it and exits non-zero. The render is still correct — deck.gl
retries — but the non-zero exit is deliberate: a tile failure should be visible.
It does not occur against a warm server or a static host.

## Fidelity against the canonical boards

| | lot area | lot width |
| --- | --- | --- |
| Dimensions | 3200×2200 ✓ | 3200×2200 ✓ |
| Headline figure | 69% ✓ | 88% ✓ |
| Counts | 227,868 / 332,160 ✓ | 289,718 / 331,007 ✓ |
| BZA cases | 11 ✓ | 6 ✓ |
| Masthead, legend | identical | identical |
| Drawn map extent | 1946×1360 vs 1948×1360 | — |

### Fidelity against the canonical, measured

Per-pixel agreement between the frozen board and
`03-minimum-lot-area.png`, after aligning both to the same grid and classifying
every pixel to the nearest palette colour:

| Renderer / setting | agreement | red share of map ink |
| --- | --- | --- |
| deck.gl (previous) | 86.0% | 34.2% |
| **MapLibre, `fill-antialias: false`** | **95.6%** | **26.3%** |
| MapLibre, `fill-antialias: true` | 94.1% | 29.1% |
| canonical board | — | 26.7% |
| true share by source geometry | — | 31.6% |

Two things worth keeping in mind:

- **`fill-antialias: false` is the better setting, not a shortcut.** It agrees
  more closely with the printed board and lands within 0.4 points of its red
  share. The intuition that disabling antialiasing would worsen sub-pixel
  fidelity is wrong here — MapLibre's rasterisation of a one-pixel polygon
  mosaic simply resembles matplotlib's more than deck.gl's did.
- **Both renderers under-show the failing class relative to the source.** The
  canonical reads 26.7% and the frozen board 26.3%, against a true area share of
  31.6%. That gap is inherent to drawing 378,366 parcels into a 2030px-wide
  well, and it is shared with the printed exhibit, so the two agree with each
  other. It still means the colour *proportions* of a citywide board are not a
  quantity — the figures on the board carry the quantity (69%, 227,868 of
  332,160), computed in Python and identical in both outputs.

An earlier version of this file claimed the gap was "not recoverable by tuning"
and separately claimed a "navy deficit". Both were wrong: the first was true of
deck.gl and not of the renderer, and the second was an artefact of a
threshold-based colour mask.
