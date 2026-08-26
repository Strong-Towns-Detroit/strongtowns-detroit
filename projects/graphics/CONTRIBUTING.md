# Contributing to the graphics library

This guide is for developers and AI agents working in developer mode. Read
`AGENTS.md` first.

## Architecture

There are three deliberate layers:

```text
projects/graphics/src/graphics/*.py   canonical graphic definitions
src/strongtowns_detroit/graphics/     reusable library and build engine
projects/graphics/output/             generated publishing artifacts
```

A definition owns editorial copy, data preparation, and explicit visual
encoding. The library owns reusable chart/map rendering, composition,
typography, publishing formats, automatic registration, and artifact writing.

Do not move graphic-specific assumptions into the library. Conversely, do not
copy reusable render/layout machinery into several definitions.

## Define a graphic

Definitions are registered through the library, not by filename or directory:

```python
from strongtowns_detroit.graphics import Graphic, graphic_definition


@graphic_definition("example")
def build() -> dict[str, Graphic]:
    return {"example": make_graphic()}
```

The source file may live anywhere beneath the configured `src` root. The
registration name determines discovery and output identity.

All editorial fields must be visible in the definition's renderer call:

- `title`
- `subtitle`
- `sources`
- `description`

Do not build a graphic and then use `dataclasses.replace()` to retrofit those
fields. Public renderers expose them directly.

## Public API principles

- Accept explicit data. Categorical proportional-symbol maps use a Polars data
  frame containing point ID, EPSG:3857 easting/northing, category, label, color,
  magnitude, and category count.
- Use enums for finite semantic choices such as publishing format, bar
  orientation, and arrangement.
- Accept comparators when ordering is genuinely open-ended.
- Keep API names generic: `bar_chart`, not a name describing one policy ratio;
  categorical proportional-symbol map, not a name describing one BZA map.
- A legend, map pocket, segment, or hero figure is a child of the map
  composition. It should not unexpectedly own or resize a sibling.
- Marker legends must use the exact same sizing function and scale as markers
  on the map.
- Preserve resolution-independent HTML/SVG; PNG width belongs to the publishing
  target.
- Avoid breaking changes. If one is justified, migrate every canonical
  definition in the same change and discuss major interface decisions first.

## Typography and mobile behavior

Instagram is a mobile editorial format. It is not a scaled conference layout.
Respect `MOBILE_TYPOGRAPHY`, automatic balanced title wrapping, the standard
masthead, and the fixed 1570-unit Detroit map slot. Mobile compositions should
prioritize title, map/chart, and legend in that order unless the definition
explicitly establishes another hierarchy. A mobile map, its pocket insets,
legend, and following segments form one measured composition that is centered
vertically in the space between the completed masthead and footer.

## Testing and review

For a definition-only change:

```bash
strongtowns-graphics build <definition> --target instagram
pytest -q tests/test_graphics_project.py
```

For a library change:

```bash
pytest -q tests/test_graphics.py tests/test_graphics_project.py
strongtowns-graphics build
git diff --check
```

Run tests for every changed source pipeline. Visually inspect affected raster
outputs. Do not commit `projects/graphics/output/`, caches, or exploratory
screenshots.

## Changes requiring user agreement

Pause and discuss:

- a new public abstraction or breaking signature;
- a new publishing format or change to standard dimensions;
- changes to shared map scale, typography minimums, or branding;
- hidden data inference or a new methodological assumption;
- moving responsibility between definitions and the library.

Ordinary use of an existing public parameter does not require architectural
approval.
