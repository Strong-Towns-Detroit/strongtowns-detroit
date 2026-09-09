# Land Forum

Public website for Land Forum and the Detroit Board of Zoning Appeals atlas.

## Develop

```bash
../../.venv/bin/python scripts/build_bza_data.py --check
../../.venv/bin/python scripts/build_bza_data.py
npm ci
npm run dev
```

The public atlas data is generated from the repository’s normalized BZA case
histories and matched assessor parcels. Do not edit `public/data/bza-cases.json`
by hand.

Production builds use vinext and include the Sites metadata inside `dist/`.

## Public origin

Anything needing an absolute URL — the canonical link, Open Graph tags,
`sitemap.xml`, `robots.txt` — reads the origin from `NEXT_PUBLIC_SITE_URL`:

```bash
NEXT_PUBLIC_SITE_URL=https://your-domain.org npm run build
```

It is defined once in `app/site.ts`. With the variable unset, absolute URLs
fall back to `http://localhost:3000`, so link previews will not resolve — that
is deliberate, and preferable to baking a wrong hostname into shipped metadata.
An unparseable value fails the build rather than emitting a malformed tag.

## Typography

Two self-hosted variable families, in `public/fonts`, declared by hand in
`app/fonts.css`:

| Family | Axes | Used for |
| --- | --- | --- |
| Source Serif 4 | `wght 200..900`, `opsz 8..60` | headlines, dek, prose, data |
| Inter | `wght 100..900`, `opsz 14..32` | labels, controls, eyebrows |

Both are SIL Open Font License 1.1. Nothing is fetched from a third party at
runtime.

Three things are worth preserving if this is ever reworked:

- **No manual tracking on display headings.** Both families carry an optical
  size axis and `font-optical-sizing: auto` is the browser default, so large
  text already gets the cut drawn for that size. The previous
  `letter-spacing: -.065em` was compensating for a text face used at 130px, and
  it fought the fonts' own kerning pairs.
- **All-caps takes positive tracking** (`--track-caps`), lowercase display type
  slightly negative (`--track-display`). Mixing these up is what made the
  wordmark read as broken.
- **Stat figures need `font-variant-numeric: lining-nums tabular-nums`.**
  Source Serif 4 defaults to lining figures; the tabular variant keeps columns
  aligned and stops ranges like `2019–26` breaking across lines.

The declarations are written by hand rather than through `next/font` because
`npm run dev` runs real `next dev` while `npm run build` runs `vinext build`,
and vinext's `next/font` shim resolves `src` paths verbatim, emits no
`unicode-range`, and generates no fallback metrics. Plain `@font-face` behaves
identically under both.

To regenerate or add a subset, download the variable `woff2` from the Google
Fonts CSS API and copy its `unicode-range` into `app/fonts.css` alongside it.
Font filenames are not content-hashed, which is why `public/_headers` caps
`/fonts/*` at 30 days rather than marking it immutable.

## Headers

`public/_headers` **replaces** the file vinext generates — it is not merged.
It therefore has to carry vinext's own `/_next/static/*` immutable rule as well
as the security and cache headers; removing that block silently drops immutable
caching on every hashed build asset.

## Icons and social card

`public/icon.svg` is the master mark, with the "LF" converted to outlines so it
cannot be affected by font substitution. The raster icons, `favicon.ico`, and
the 1200×630 `og-default.png` are generated from it and from the live hero
styles. Regenerate them if the palette or wordmark changes.

## Reproducible atlas builds

Run from this directory with the Detroit Python environment and installed SDKs:

```bash
../../.venv/bin/python scripts/build_bza_data.py --check
../../.venv/bin/python scripts/build_bza_data.py
../../.venv/bin/python scripts/build_parcel_tiles.py --check
../../.venv/bin/python scripts/build_parcel_tiles.py
```

Both builders resolve declared artifacts through the consumer's
`strongtowns-data.lock.json`. `--lock` and `--repository` support other layouts.
Preflight verifies snapshots without generating output, fetching, or updating
locks. Case generation accepts `--output DIRECTORY` for an isolated preview.
Reusable inputs already belong to registered datasets; there is no fallback
to legacy output directories.

The parcel builder emits `parcel-index.json` and small ID-prefix shards in
`parcel-index/` from the same pinned geometries used for tiles. Lookup fetches
only the needed shard. `--output-directory DIRECTORY` creates an isolated
parcel preview. Rebuild tiles, index, figures, and provenance together before
publishing. Preserve parcel IDs as strings. Provenance JSON records snapshot
creation dates and identities; creation dates do not imply observation dates.
Case source links are emitted only when the input records supply an HTTP(S)
`source_url`. A filename alone is not turned into a guessed URL.

## Verification and hosting

```bash
npm test
npm run typecheck
npm run tokens:check
npm run build
npx playwright install chromium
npm run test:browser
```

`typecheck` regenerates Next route declarations while preserving vinext's
ambient types. Browser checks run the built application with `vinext start`,
using fixture responses for case data. They use installed Chrome on macOS when
available; `CIVIC_BROWSER_PATH` selects another executable and
`CIVIC_TEST_ORIGIN` selects an already-running production server.

Cloudflare Workers limits individual static assets to 25 MiB. The full parcel
archive exceeds that limit. For a Workers deployment, serve that archive on
an HTTPS host with HTTP Range and CORS support, then set
`NEXT_PUBLIC_PARCEL_ARCHIVE_URL` to its immutable URL **at build time**. The
build omits the local full-archive duplicate from `dist/client`; source files
in `public` remain intact. Overview tiles, index, and metadata stay with the
site. The deployment command now checks asset sizes before any upload.
Local `npm start` (vinext) supports the default same-origin archive and serves
the output of `npm run build`.

This repository does not upload the archive automatically. The hosting URL
must point to the same archive produced with the published index and figures.

## BZA graphics studio

Members can open `/graphics/bza/`, choose records, inspect the summary, customize
one of three reviewed templates, and download PNG, SVG, CSV, alt text, or saved
settings. The atlas's **Create a graphic from these cases** action transfers its
search, category, outcome, and first-hearing-year filters with mapped-only scope.
The atlas and studio share the same pinned classifications and filtering code.

The studio counts case-history IDs once, including unmapped records by default.
Year filters refer to the first recorded hearing; undated cases are included only
when years are unrestricted. Primary-request classifications come from the
existing pinned-input publication helper, including its combined parking group.
Missing classifications remain visible. Outcomes describe the available record,
not an independently verified complete history of every Detroit BZA case.

Build a new studio publication without changing the existing atlas assets:

```sh
python scripts/build_bza_data.py --check
python scripts/build_bza_data.py --studio-only
```

Run these with the consumer project's Python environment and configured data
repository. Inputs must already exist in the lock; the builder never fetches,
reclassifies, or changes the lock. Review `public/data/bza-studio/comparison.json`
before releasing a new publication. The initial bundle has 405 cases, 397 mapped,
8 unmapped, and no missing first-hearing dates. Mapped IDs and outcome counts
match the previous atlas; category assignments differ. The local atlas case and
marker files are updated with the same classifications for exact filter handoff. There are 23 unspecified
primary requests in the full bundle. Parking is a combined category with 64 cases.
The comparison contains every category and outcome count for all three scopes.

`latest.json` points to a SHA-256-named bundle. Include **all released bundles**
in subsequent deployments; never prune or edit them. Keep these publication JSON
files in version control with the existing public case data. Saved links and
settings refer to the original bundle, and the browser verifies its byte hash.
Missing or invalid historical data causes an explicit error, never a substitution.
Links store wording and filters in their fragment and require no server storage
or account. Anyone receiving a link can read those choices. Recipe version 1
supports the initial templates; incompatible template/methodology changes require
an explicit recipe-version migration, not silent reinterpretation.

Reusable rendering is supplied by `@strongtowns/graphics-browser`, packaged from
the sibling graphics repository and pinned as a vendored npm archive. See
`../../projects/graphics/vendor/README.md` for updates. Detroit editorial defaults
live in `../../projects/graphics/src/graphics/bza-studio.json`; browser filtering
and recipe handling live in `lib/graphics/bza.ts`. No Python runtime or map tiles
are needed for graphic generation. Fonts are self-hosted and embedded in SVGs.

Browser tests exercise actual exports and source failures. To run each engine:

```sh
npx playwright install chromium firefox webkit
npm run build
CIVIC_BROWSER_ENGINE=chromium npm run test:browser
CIVIC_BROWSER_ENGINE=firefox npm run test:browser
CIVIC_BROWSER_ENGINE=webkit npm run test:browser
```

Before public release, run a short pilot with three ST members. Give each the
same task: find a meaningful subset, explain what its count includes, create a
readable graphic, download it, and reopen the saved settings. Aim for five minutes
without terminal use or developer guidance. Record task time, help needed,
count/scope misunderstandings, unreadable text, and download/reopen failures;
fix blocking issues before launch. Automated browser tests do not replace this
member pilot. No public deployment is performed by the implementation scripts.

### Implementation verification

The initial studio implementation passed 114 consumer Python tests, 45 graphics
Python tests, 25 website unit tests, 5 browser-renderer unit tests, and all 10
production browser scenarios in each of Chromium, Firefox, and WebKit (30 runs).
Type checking, design-token verification, production build, package integrity,
and studio asset-size checks passed. Exported PNGs and the mobile layout were
visually inspected. The existing full parcel archive still exceeds the Workers
asset limit; configure its separately hosted URL before deployment as described
above. This work did not deploy or conduct the three-member pilot.

On this development Mac (macOS 26.0.1), Playwright's native macOS 26 WebKit build
crashed in native window creation before loading any page. The same WebKit 26.5
revision passed using its macOS 15 build in a temporary test directory:

```sh
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=mac15-arm64 \
  PLAYWRIGHT_BROWSERS_PATH=/tmp/civic-webkit-compat \
  npx playwright install webkit
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=mac15-arm64 \
  PLAYWRIGHT_BROWSERS_PATH=/tmp/civic-webkit-compat \
  CIVIC_BROWSER_ENGINE=webkit npm run test:browser
```

This is a local test workaround; CI uses the normal Linux browser distributions.
