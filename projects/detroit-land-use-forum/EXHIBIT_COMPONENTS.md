# Exhibit component library

The canonical graphics live in `projects/graphics/src/` and use the installed
`strongtowns_graphics` package. Source definitions provide semantic page
content and chart-specific SVG marks; the package owns page composition,
aspect ratio, title wrapping, HTML embedding, and SVG/PNG output.

The library's `GraphicBuildSystem` automatically discovers each source
definition, loads it once, and fans it out to `output/instagram/`,
`output/instagram_story/`, and `output/landuseconference/`. The installed
`strongtowns-graphics` command is the primary entry point;
`projects/graphics/build.py` is only a compatibility shim. Conference code is
no longer the owner of the definitions.

## Shared components

`exhibit_brand.py`

- `masthead_svg()` — exact Strong Towns Detroit flag sprite and forum kicker.

`strongtowns_graphics` (installed library)

- `AspectRatio` and common presets — composition shape without coupling it to
  pixels, DPI, print, or a browser-export workflow.
- `Graphic` — semantic title, subtitle, visual, notes, sources, and accessible
  description.
- `SvgComponent` — chart-specific SVG markup and its local coordinate system.
- `SvgRegion` — a semantic part of an SVG visual that may be stacked in a
  portrait composition while the original visual remains intact in landscape.
- `render_graphic_svg()` — applies the shared page composition and requested
  aspect ratio.
- `write_graphic_bundle()` — writes matching HTML/SVG/PNG without a browser.
- `write_graphic_variants()` — writes caller-selected named ratios from one
  `Graphic` definition.
- `GraphicBuildSystem` + `GraphicFormat` — discover source definitions once,
  render the supported Instagram post, Instagram Story, and land-use
  conference formats, and write their manifests.
- `MobileMapLayout` — gives every Detroit map the same fixed mobile width and
  lays out its legend independently so legend density cannot shrink the map.

`exhibit_components.py` (legacy helpers for noncanonical graphics)

- `forum_css()` — semantic typography classes and palette defaults.
- `title_block()` — title/dek positioning with escaped text.
- `map_frame()` — standard map-column image frame.
- `metric_block()` — large sidebar metric, label, and supporting count.
- `LegendItem` + `swatch_legend()` — positioned map legends.
- `source_lines()` — method/source footer lines.
- `ghost_hatch_pattern()` — architectural wireframe for required-but-absent
  quantities.
- `html_document()` — responsive, print-sized HTML wrapper.
- `write_svg_bundle()` — matching HTML/SVG/PNG exports.

`parcel-geometry/parcel_exhibit_components.py`

- `bza_case_stat()` — parcel-map sidebar summary for the appropriate subset of
  BZA case histories.

## Composition example

The caller owns content and chart marks; the library owns the page:

```python
from strongtowns_graphics import (
    CONFERENCE_LANDSCAPE,
    INSTAGRAM_PORTRAIT,
    INSTAGRAM_SQUARE,
    AspectRatio,
    Graphic,
    SvgComponent,
    write_graphic_bundle,
    write_graphic_variants,
)

graphic = Graphic(
    title="Exhibit title",
    subtitle="Short explanatory subtitle",
    visual=SvgComponent(map_and_legend_svg, width=1600, height=780),
    notes=("Interpretive note …",),
    sources=("Source: …",),
)

write_graphic_bundle(
    OUTPUT,
    "example",
    graphic,
    aspect_ratio=CONFERENCE_LANDSCAPE,
)

write_graphic_variants(
    OUTPUT,
    "example",
    graphic,
    {
        "conference": CONFERENCE_LANDSCAPE,
        "instagram": INSTAGRAM_PORTRAIT,
        "square": INSTAGRAM_SQUARE,
        "custom": AspectRatio.parse("3:2"),
    },
)
```

Each variant has one composed SVG, embedded unchanged in its HTML artifact and
optionally converted directly to PNG with librsvg. There is no screenshot or
headless-browser stage.

The original coordinate-based helpers remain for noncanonical generators:

```python
css = forum_css(title_size=57)
heading = title_block("Exhibit title", "Short explanatory subtitle")
legend = swatch_legend(
    [
        LegendItem("Does not meet rule", RED),
        LegendItem("Meets rule", NAVY),
    ],
    positions=(67, 345),
)
footer = source_lines(["Method: …", "Source: …"])

svg = f"""<svg viewBox="0 0 1600 1100">
<style>{css}</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
{heading}
<!-- chart-specific map or marks -->
{legend}
{footer}
</svg>"""

write_svg_bundle(
    OUTPUT, "example", "Exhibit title", svg,
    width=1600, height=1100, png_width=3200,
)
```

## Canonical exhibit coverage

| Component | Request bars | BZA map | Lot area | Lot width | Setbacks | Parking | Transit | Driving |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Masthead | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Shared typography/title | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Map swatch legend |  |  | ✓ | ✓ | ✓ |  |  |  |
| BZA case stat |  |  | ✓ | ✓ | ✓ |  |  |  |
| Source/footer lines | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |
| Wireframe quantity |  |  |  |  |  | ✓ |  |  |
| Export wrapper | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

The following stay chart-specific because they encode meaning rather than
layout: parcel-map rasterization, isochrone and road paths, displaced BZA
markers and their magnitude legend, parking bar scaling/clipping, and the BZA
request-type bar and category layouts.
