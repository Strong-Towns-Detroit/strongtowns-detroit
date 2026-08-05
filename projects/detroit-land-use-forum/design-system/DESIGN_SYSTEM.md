# Strong Towns Detroit data graphics

This is an analytical design system, not an event-promotion template.

## Authority and interpretation

1. The June 2022 Strong Towns quick-reference guide controls the parent identity.
2. The Strong Towns Detroit flag sprite supplies a restrained local extension.
3. The current Strong Towns Detroit website demonstrates tone and subject matter.
4. Social-event graphics are useful references but do not control analytical graphics.

The parent guide specifies:

- navy `#0C2340`;
- light blue `#A7C6ED`;
- accessible blue for web text `#5790DB`;
- yellow `#FFB549`;
- Mixta Sharp and Synthese for editorial display/accent use;
- FreightText for body text;
- Georgia and Arial as approved substitutes when brand fonts are unavailable.

The local extension adds a civic red, civic gold, and the quadrant/stripe rhythm suggested
by the Detroit mark. These should appear as small structural accents. They do not replace
the Strong Towns palette.

## Required original assets

Do not trace or approximate the Strong Towns Detroit lockup. The raster reference confirms
its appearance but does not contain the original curves, kerning, or construction.

Before branded publication, obtain:

- the Strong Towns RGB logo pack referenced in the brand guide;
- the Strong Towns Detroit lockup as AI, SVG, EPS, or an outlined vector PDF;
- the Detroit heraldic tile as its own vector asset;
- licensed Mixta Sharp, Synthese, and FreightText webfonts, or an approved Adobe Fonts
  project/configuration;
- written guidance on whether the local lockup colors supersede the parent palette in
  non-logo analytical material.

Until those arrive, the reference page uses an explicitly provisional text label and the
approved Georgia/Arial fallback system. The supplied clean raster reference remains under
`assets/` for later pixel validation against the genuine source export.

## Typography presets

Typography is configured through named library presets rather than hard-coded per chart.

### `brand-safe`

The quick-reference guide's explicit portable fallback:

- display and body: Georgia;
- data labels and interface: Arial.

### `open-editorial`

Self-hostable/open-source candidates for a more distinctive analytical voice:

- display: Fraunces;
- body: Source Serif 4;
- data labels and interface: Source Sans 3.

The prototype loads these candidates from Google Fonts for evaluation. Before production,
download the upstream font releases, retain their SIL Open Font License files, subset only
if the license metadata is preserved, and self-host WOFF2 assets.

Configure the library before creating charts:

```html
<script src="config.js"></script>
<script>
  STDetroitGraphics.configure({ typography: "open-editorial" });
</script>
```

Or set the preset through the reference-page URL:

```text
index.html?typography=open-editorial
```

The live selector stores the preference locally. The public API rejects unknown preset
names rather than silently falling back:

```js
STDetroitGraphics.configure({ typography: "brand-safe" });
STDetroitGraphics.getConfig();
STDetroitGraphics.presets;
```

## Chart grammar

### Hierarchy

Every graphic should contain, in this order:

1. a short domain kicker;
2. a finding-led headline;
3. an optional one-sentence qualification;
4. the chart;
5. direct annotations;
6. source, method, geography/time period, author/update date.

### Color roles

| Role | Default |
|---|---|
| Type, axes, outlines, primary structure | Strong Towns navy |
| Focal value or selected series | Strong Towns yellow |
| Comparison, range, secondary series | Strong Towns light blue |
| Blue text on a light field | Accessible blue |
| Warning, loss, negative divergence | Detroit red |
| Secondary civic accent | Detroit gold |
| Background | Warm paper or white |
| Secondary copy | Muted navy-gray |

Do not assign a different saturated brand color to every series. If a chart has many
categories, use a sequential palette or neutral values and highlight only the subject.

### Typography

- Use Georgia for editorial display typography in the portable system.
- Use Arial for chart labels, axes, notes, interface controls, and dense explanatory copy.
- If properly licensed webfonts are later supplied, map Mixta Sharp to display, Synthese to
  sans/editorial accents, and FreightText to body copy.
- Never fetch or redistribute the formal brand fonts without license confirmation.
- Use sentence case for findings; reserve uppercase and tracking for short kickers/metadata.

### Accessibility

- Minimum body contrast is WCAG AA.
- Never place `#A7C6ED` text on white; use `#5790DB`.
- Never encode meaning with color alone. Add direct labels, line dash, marker shape, pattern,
  or explicit annotation.
- SVG charts receive a concise accessible name; complex production charts should also have
  a visible data table or long description.
- Avoid animation by default and honor reduced-motion preferences.

### Maps

- Geographic context: warm neutral.
- Water: light blue.
- Street/network context: muted navy-gray at low visual weight.
- Selected geography/reach: yellow or accessible blue depending on contrast.
- Boundaries: navy.
- Alerts or adverse areas: Detroit red.
- Provide scale, north orientation when useful, projection, source, and method.
- Do not use administrative boundaries as visual decoration if they do not bear on the claim.

### Print

- Author charts in responsive SVG inside HTML.
- Use the browser print stylesheet for PDF output.
- Inspect at final physical size; browser zoom is not a substitute.
- Prefer vector text/marks and attached raster images at sufficient effective resolution.
- Preserve color backgrounds explicitly (`print-color-adjust: exact`) but still inspect the
  printer proof.

## Files

- `index.html` — living reference page and example compositions.
- `styles.css` — tokens, layouts, responsive rules, and print rules.
- `config.js` — validated typography presets and public configuration API.
- `charts.js` — dependency-free SVG examples and starter helpers.

Run locally from this directory:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.
