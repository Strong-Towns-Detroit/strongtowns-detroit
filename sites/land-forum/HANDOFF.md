# Land Forum website handoff

Updated: 2026-07-31

## Product direction

Land Forum is not a website for one BZA visualization. It should become a
home for many public land-use investigations, presented in a consistent,
beautiful, interactive, and easily shareable native format.

The Detroit BZA Atlas is the first publication, not the site's organizing
identity. The next major body of work is to codify Detroit's zoning ordinance
as executable, cited rules and apply those rules to City Base Units and parcel
geometry. A visitor should eventually be able to:

1. explore a citywide map of current dimensional standards and measured
   parcel/building conditions;
2. search for an address or select a parcel;
3. see the exact assessor parcel and City Base Units building footprints;
4. see the applicable zoning district, use/building scenario, and rules;
5. see which measured conditions satisfy or fail the current dimensional
   standards;
6. understand the result visually on the parcel itself;
7. inspect the source section, assumptions, missing evidence, and calculation;
8. share or download a polished artifact representing that parcel or the
   wider finding.

## Important language boundary

A geometric rule failure does **not**, by itself, prove that an existing
building is unlawful. Existing structures may be lawful nonconformities, may
have variances or administrative adjustments, may rely on lot-of-record
protection, may occupy a combined zoning lot, or may have other approvals.

The data model and UI should distinguish:

- **Meets the current dimensional standard**
- **Fails the current dimensional standard as measured**
- **Not enough information to evaluate**
- **Not evaluated for this scenario**

For punchier explanatory copy, “Would require relief under today’s standard”
is supportable when the relevant rule and scenario have been established.
Avoid labeling an existing structure simply “illegal” unless independent
legal-status evidence supports that conclusion.

## Current site

The website lives in `sites/land-forum` and uses:

- Next.js 16 / React 19;
- MapLibre GL for the interactive atlas;
- vinext and Cloudflare deployment tooling;
- generated static JSON and GeoJSON under `public/data`.

Run it with:

```bash
cd sites/land-forum
npm run dev
```

The current local URL is `http://localhost:3000` when the server is running.

Primary files:

- `app/page.tsx` — current homepage
- `app/atlas/page.tsx` — BZA publication page
- `components/AtlasExplorer.tsx` — current MapLibre experience
- `app/styles.css` — site-wide visual language
- `scripts/build_bza_data.py` — generated BZA web data
- `public/data/bza-cases.json`
- `public/data/bza-map.json`
- `public/data/detroit-context.geojson`

Do not edit generated public data by hand. Change its source pipeline and
regenerate it.

The working tree contains extensive user work. Preserve unrelated changes.

## Immediate UI work versus structural work

Small homepage and typography fixes can proceed independently, including the
currently noted LAND FORUM/hero kerning adjustment. Keep those edits narrow.

Do not hard-code every investigation into the homepage. The structural work
should introduce a publication model so the BZA Atlas, isochrones, zoning
geometry, parking, assessed land value, and later economic simulations can
share the same presentation system.

## Publication system

The intended information architecture is:

```text
Land Forum
├── Publications / investigations index
├── Individual publication
│   ├── title, dek, and key finding
│   ├── interactive visualization
│   ├── explanatory narrative
│   ├── methodology and limitations
│   ├── sources and ordinance citations
│   ├── data/artifact downloads
│   └── shareable image and canonical URL
└── Specialized explorers
    ├── BZA Atlas
    └── Zoning / parcel explorer
```

Prefer a typed publication registry over copy-pasted pages. A publication
record will likely need:

```ts
type Publication = {
  slug: string;
  title: string;
  dek: string;
  eyebrow: string;
  summary: string;
  kind: "map" | "chart" | "atlas" | "essay" | "simulation";
  publishedAt?: string;
  updatedAt?: string;
  topics: string[];
  heroAsset?: string;
  interactivePath?: string;
  methodologyPath?: string;
  downloads?: { label: string; href: string; format: string }[];
};
```

This is a starting contract, not a requirement to implement a CMS. Keep the
first version local, typed, and static.

## Existing zoning-code foundation

The ordinance parsing code is under `src/strongtowns_detroit/zoning`:

- `ordinance.py` orchestrates full-document parsing and JSON/CSV export;
- `document.py` extracts the section hierarchy;
- `use_tables.py` extracts district/use permission matrices;
- `dimensional.py` extracts dimensional tables;
- `definitions.py` extracts defined terms;
- `citations.py` extracts cross-references;
- `models.py` contains the current records;
- `table_parser.py` expands and classifies ordinance tables.

The current `DimensionalStandard` stores values as strings. That is useful as
source evidence but is not yet an executable rule representation. Do not
discard the raw value. Add a normalized layer beside it.

The old generic checker in
`src/strongtowns_detroit/parcels/compliance.py` is insufficient as the final
legal engine. It handles basic area/width thresholds but does not express the
full scenario, geometry, exceptions, provenance, or indeterminate results.

## Existing geometry foundation

Official inputs and methodology are documented in:

- `projects/detroit-land-use-forum/base-units-geometry/README.md`
- `projects/detroit-land-use-forum/base-units-geometry/METHODOLOGY.md`

The cached City Base Units inputs include:

- `data/base_units_buildings.geojson`
- `data/base_units_addresses.geojson`
- `data/base_units_streets.geojson`

The official layers provide stable building IDs, parcel links, addresses,
street links, building status, and building-footprint polygons. Current
assessor parcels are represented by `pipelines/parcel-data/Parcels.geojson`.

Important: assessor parcels and Base Units links are evidence, not necessarily
legal zoning lots. A footprint crossing multiple assessor parcels does not
prove that the parcels form one zoning lot. Preserve this uncertainty.

Existing analytical implementations include:

- `projects/detroit-land-use-forum/parcel-geometry/setback_envelope_model.py`
- `projects/detroit-land-use-forum/parcel-geometry/lot_coverage_model.py`
- `projects/detroit-land-use-forum/parcel-geometry/build_minimum_lot_size_asset.py`
- `projects/detroit-land-use-forum/parcel-geometry/build_minimum_lot_width_asset.py`
- `projects/detroit-land-use-forum/parcel-geometry/build_residential_setback_asset.py`
- `projects/detroit-land-use-forum/base-units-geometry/geometry_model.py`

The conference outputs are validated visual references, not web data APIs:

- `projects/detroit-land-use-forum/conference-canonical/03-minimum-lot-area.*`
- `projects/detroit-land-use-forum/conference-canonical/04-minimum-lot-width.*`
- `projects/detroit-land-use-forum/conference-canonical/05-residential-setback-envelope.*`

Reuse the same classifications and visual language. Avoid reimplementing
their zoning logic separately in TypeScript.

## Proposed executable-rule model

Keep ordinance source extraction separate from normalized interpretation and
parcel evaluation:

```text
ordinance source
  → extracted source record
  → reviewed normalized rule
  → selected development scenario
  → measured parcel/site facts
  → evaluation result with evidence
  → web data and visualization
```

A normalized rule should be able to carry at least:

```python
NormalizedRule(
    rule_id="...",
    ordinance_version="...",
    section_ref="50-...",
    district="R1",
    use_type="one_family_dwelling",
    building_role="principal",
    metric="minimum_lot_area",
    operator=">=",
    value=5000,
    unit="square_feet",
    applicability={...},
    exceptions=[...],
    source_text="...",
    review_status="verified",
)
```

Evaluation results should never be a bare boolean:

```python
RuleEvaluation(
    rule_id="...",
    status="meets" | "fails" | "unknown" | "not_applicable",
    measured_value=...,
    required_value=...,
    unit="...",
    geometry=...,
    explanation="...",
    assumptions=[...],
    missing_inputs=[...],
    source_refs=[...],
)
```

The engine must take a named scenario. Zoning requirements differ by district,
use, building type, principal/accessory role, corner/interior lot condition,
and sometimes adjacent context. “Is this parcel legal?” is not a valid input
without specifying what exists or what is proposed.

## First supported scope

Start narrowly with the strongest existing work:

- R1–R6 districts;
- existing one-family and two-family principal buildings;
- parcel/lot area;
- lot width using the current validated frontage proxy, explicitly labeled;
- front, side, combined-side, and rear setback envelopes;
- principal building footprint relative to the applicable envelope;
- lot coverage only after its building-type and denominator rules are pinned;
- an explicit `unknown` path for ambiguous frontage, multi-parcel sites,
  multiple principal structures, missing footprints, and unresolved use.

Do not begin by attempting every zoning district and every ordinance rule.
The architecture should generalize, but the first public page must be
defensible.

## Parcel-detail experience

The parcel page or selected-parcel drawer should include:

1. Address and parcel identifier.
2. Zoning district and evaluated scenario.
3. A north-oriented, appropriately fitted map showing:
   - assessor parcel boundary;
   - exact Base Units building footprints;
   - identified front edge/street relationship;
   - generated buildable/setback envelope;
   - footprint area outside the envelope;
   - adjoining parcels and street context in subdued colors.
4. A compact rule summary:
   - measured value;
   - required value;
   - status;
   - ordinance citation.
5. A plain-language explanation of what the result does and does not mean.
6. Method and source disclosure.
7. Direct share link and downloadable SVG/PNG/data where feasible.

The geometry must remain true when zoomed. Do not substitute a generic lot
diagram for the actual parcel view.

## Wider map experience

The citywide explorer should use MapLibre/WebGL and allow visitors to switch
among evaluated layers such as:

- minimum lot area;
- minimum lot width/frontage proxy;
- setback-envelope crossing;
- lot coverage when ready;
- evaluated / unknown / outside-scope state.

At city scale, use precomputed classifications and simplified geometry or
vector tiles. Do not send hundreds of thousands of full-resolution parcel and
building polygons as one initial GeoJSON payload. Full geometry can be loaded
for the selected parcel and immediate context.

Filters should be native to the existing Land Forum UI and support multiple
selections. URL state should preserve the active layer, filters, map position,
and selected parcel so a view can be shared.

## Web-data boundary

Python owns ordinance interpretation, geometry, and classifications. React
owns interaction and presentation. Avoid duplicating legal calculations in
the browser.

Introduce a deterministic build script for web artifacts, analogous to
`scripts/build_bza_data.py`. Suggested outputs:

```text
public/data/zoning/
  manifest.json
  rules.json
  layer-summary.json
  parcel-index.*
  map tiles or simplified layer data
  parcels/{parcel_id}.json or an equivalent queryable artifact
```

Every build should record:

- ordinance/source version;
- parcel and Base Units data dates;
- rule-engine version;
- counts by status;
- exclusions/unknown reasons;
- stable identifiers;
- build timestamp.

Tests should verify both the analytical classification and the emitted web
contract.

## Shareable native format

Each publication and parcel view should have a stable canonical URL and
useful metadata for link previews. A later export path should render the same
design system to:

- responsive interactive web;
- Open Graph/social card;
- PNG;
- SVG or print-ready PDF where the visualization supports it;
- source/method/data download.

Do not create separate visual languages for web, social, and print. Use shared
tokens and composition primitives, while allowing layouts to reflow rather
than stretching a fixed poster.

## Visual language

Continue the established Land Forum / Strong Towns Detroit visual system:

- warm cream background;
- dark Detroit blue typography and context;
- red for the most consequential failure/intensity state;
- clear blues and restrained grays for comparison and unavailable data;
- editorial serif display type paired with highly legible UI text;
- small Strong Towns Detroit flag where partnership branding is appropriate;
- generous whitespace and publication-quality hierarchy.

The conference canonical assets are the strongest visual references. The
website should feel native to them without forcing poster proportions onto a
screen.

Accessibility requirements:

- never encode rule status only by color;
- visible focus and keyboard operation;
- sufficient contrast;
- textual equivalents for map findings;
- motion-reduction support;
- usable parcel inspection on mobile.

## Recommended implementation sequence

### Phase 1 — publication shell

1. Add a typed publication registry.
2. Turn the homepage's BZA feature into a collection/index pattern.
3. Preserve `/atlas`, but present it as the BZA Atlas publication.
4. Add a reusable publication page shell with methods, sources, downloads,
   metadata, and share affordances.

### Phase 2 — rule contract

1. Audit the ordinance parser against the exact R1–R6 one-/two-family tables.
2. Add normalized, typed, cited rules without destroying raw extractions.
3. Add reviewed fixtures for representative district/scenario combinations.
4. Implement four-state evaluations and explicit unknown reasons.
5. Confirm the results against the existing conference analyses.

### Phase 3 — parcel prototype

1. Select a small set of representative parcels with known geometry cases.
2. Generate exact parcel, building, front-edge, envelope, and evaluation data.
3. Build one polished parcel-detail route or drawer.
4. Validate every number and geometric overlay manually.
5. Add a shareable URL and image/export prototype.

### Phase 4 — citywide zoning explorer

1. Precompute the supported classifications for the city.
2. Package scalable map data.
3. Add layer switching, filters, search, URL state, and parcel selection.
4. Load full parcel detail on demand.
5. Publish methodology and complete accounting of unknown/excluded parcels.

### Phase 5 — extend the ordinance library

Add lot coverage, height, parking, permitted uses, accessory structures, and
additional districts one independently validated rule family at a time.

## Acceptance criteria for the first zoning publication

The first public zoning visualization is ready only when:

- its ordinance version and exact cited sections are visible;
- the normalized rules have reviewed fixtures;
- a selected parcel displays actual parcel and Base Units footprint geometry;
- calculations match the existing validated analytical pipeline;
- `unknown` and out-of-scope conditions are not silently classified;
- the citywide and parcel views share the same result definitions;
- the URL is directly shareable and restores the selected view;
- the page works on desktop and mobile;
- the finding can be understood without reading the methodology;
- the methodology makes every material assumption discoverable.

## Working principles

- Build small, reviewable increments. John will validate the UI in a tight
  loop.
- Keep analytical work reproducible and test-driven.
- Prefer shared components and tokens when a pattern appears twice.
- Do not prematurely generalize before one parcel experience is excellent.
- Preserve raw source evidence and cite the ordinance at the rule level.
- Never collapse missing evidence into a pass or failure.
- Do not let the BZA Atlas's current implementation dictate every future map;
  extract reusable primitives where they are genuinely shared.
