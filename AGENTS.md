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
