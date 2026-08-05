# Land Forum

Public website for Land Forum and the Detroit Board of Zoning Appeals atlas.

## Develop

```bash
python scripts/build_bza_data.py
npm install
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
