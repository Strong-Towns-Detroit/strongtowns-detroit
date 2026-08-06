# Exhibit component library

The canonical conference graphics are composed from small SVG helpers rather
than a single chart framework. This keeps analytical renderers independent
while making the forum's repeated visual language reusable.

## Shared components

`exhibit_brand.py`

- `masthead_svg()` — exact Strong Towns Detroit flag sprite and forum kicker.

`exhibit_components.py`

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
