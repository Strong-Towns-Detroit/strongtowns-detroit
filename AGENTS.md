# AI agent guide

This repository serves both people who want to produce Strong Towns Detroit
graphics and developers who want to extend the underlying tools.

## Establish the working mode

At the beginning of a graphics task, ask this if the user's comfort level and
intent are not already clear:

> Would you like to work in publishing mode, where you describe the result and
> I handle the code, or developer mode, where we discuss and change the library
> API together?

Do not repeatedly ask. Infer the answer when the user has already made it
clear. A request for wording, colors, layout, data, or an exported image is
normally publishing mode. A request about APIs, abstractions, renderers,
build-system behavior, or contributing code is normally developer mode.

### Publishing mode

- Use plain language and show the rendered result when visual judgment matters.
- Edit the canonical definition in `projects/graphics/src/graphics/`.
- Build only the requested graphic and target while iterating.
- Do not ask the user to edit Python, SVG, or HTML.
- Do not change public library interfaces merely to adjust one graphic.

### Developer mode

- Explain the current public API and the proposed interface before a major or
  breaking architectural change.
- Prefer generic, composable library concepts over names tied to one chart,
  dataset, conference, or publishing campaign.
- Preserve existing definitions and publishing targets unless migration is
  explicitly part of the task.
- Add focused tests for new public behavior and update contributor docs.

## Graphics safety rules

1. Graphic definitions are the source of truth. Never hand-edit files under
   `projects/graphics/output/`.
2. Definitions own their titles, subtitles, descriptions, sources, data
   selection, and explicit encodings. The library owns reusable rendering,
   layout, typography, and build behavior.
3. HTML and SVG are output formats, not authoring locations.
4. Publishing formats are the `GraphicFormat` enum. Do not introduce an ad hoc
   size when a supported publishing type is intended.
5. Preserve the fixed mobile Detroit map scale and mobile minimum typography.
6. Point-map inputs are explicit Polars data frames in EPSG:3857. Avoid hidden
   category, coordinate, legend, or magnitude inference.
7. Never add a library function named for a particular graphic. If behavior is
   not reusable, keep it in that graphic's definition.
8. Do not silently broaden a graphic's methodology or editorial claim.
9. Generated PNG, SVG, HTML, manifests, caches, and local screenshots are not
   committed.
10. Come to the user before major architecture or public-interface decisions.

## Required verification

During iteration:

```bash
strongtowns-graphics build <definition> --target instagram
pytest -q tests/test_graphics.py tests/test_graphics_project.py
```

Before committing a library change:

```bash
pytest -q tests/test_graphics.py tests/test_graphics_project.py
git diff --check
```

Also run tests belonging to any data pipeline or legacy renderer that changed.
Visually inspect at least one affected PNG when layout, typography, color, or
map composition changes.

See `projects/graphics/USING_GRAPHICS.md` for publishing mode and
`projects/graphics/CONTRIBUTING.md` for developer mode.

## Data-pipeline mode

For a data request, establish whether the user wants an analysis from promoted
data or intends to change contracts and pipeline behavior. Infer the mode when
their intent is already clear.

1. Inspect `strongtowns-data status` before building or acquiring anything.
2. Offline `build` and network `fetch` are separate operations. Never fetch
   merely because a promoted input is missing.
3. Never use `--allow-paid` without explicit authorization for that provider
   operation.
4. Immutable snapshot artifacts and completed manifests are evidence. Do not
   edit them by hand or overwrite them.
5. Missing legacy provenance stays null with `provenance_grade=legacy`; do not
   infer a URL, date, query, or version that was not captured.
6. Dirty-code diagnostics may remain staged, but do not bypass the clean-tree
   promotion gate.
7. Schema meaning changes require a major contract version and migration tests.
8. Builders consume registered asset identities and write only to assigned
   staging directories. Do not add current-working-directory assumptions.
9. Report accepted and rejected counts and preserve every rejection with an
   enumerated reason and source-row locator.
10. Never commit or push unless the user explicitly asks.
11. Query catalogs are derived mirrors. Never treat a database edit as a source
    change or write notebook results back into promoted evidence.
12. Do not add, configure, or publish to a hosted database without an explicit
    provider decision. Prefer a downloadable local catalog for analysis.
13. Catalog consumer connections must remain read-only and must not enable
    external file access, network access, or automatic extension installation.

Read `docs/data-pipelines.md` before extending the engine or a dataset contract.
