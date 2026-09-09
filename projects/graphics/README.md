# Graphics

This is the publishing-neutral home for Strong Towns Detroit graphics.

Choose the guide that matches how you want to work:

- [Example notebooks](notebooks/README.md): editable Python SDK walkthroughs
  for all twelve existing Instagram graphics, plus a small starter chart.
- [Using the graphics](USING_GRAPHICS.md): plain-language publishing workflow
  for editors, researchers, organizers, and AI-assisted users.
- [Contributing](CONTRIBUTING.md): architecture and safeguards for developers
  and AI agents extending the library.

The current definitions are grouped under `src/graphics/`, with one plainly
named file per graphic. That is an organizational choice, not a library
requirement. A builder registered with `@graphic_definition(...)` may live at
any depth or filename beneath `src/`. The library discovers registrations,
loads each builder once, then renders the same `Graphic` objects into every
requested `GraphicFormat`:

```text
projects/graphics/
├── src/graphics/<graphic-family>.py
└── output/
    ├── instagram/<graphic-family>/{name}.html|svg|png
    ├── instagram_story/<graphic-family>/{name}.html|svg|png
    └── landuseconference/<graphic-family>/{name}.html|svg|png
```

Publishing formats are an explicit enum rather than arbitrary ratios. The Instagram
feed is 4:5 at 1080×1350. The Story target is 9:16 at 1080×1920 and places the
unchanged feed composition after 14% top padding. The land-use conference is
16:11 at 3200 px wide. HTML and SVG remain resolution-independent. A source
may identify semantic regions so mobile formats can select and reflow their
essential content while the conference format retains the complete landscape
composition.

Instagram is treated as a mobile editorial format, not as a smaller conference
page. Map graphics prioritize the title, a substantially larger map, and its
legend. Conference-only analytical sidebars, hero metrics, and explanatory
blocks such as “What this measures” are omitted from mobile output.

The library owns a fixed 1570-unit Detroit map slot on every 1600-unit mobile
composition. Source graphics identify their map and legend regions, but cannot
shrink the map to accommodate a longer legend. Each standard negative-space
pocket in Detroit's geometry may independently be empty or contain a typed
mobile inset. Available inset kinds include a hero statistic, an effect-size
legend, and an editorial text block; using any of them does not change the map
scale.

## Build system

The build engine and command ship with the installed library. From anywhere in
this repository, build every discovered definition with one command:

```bash
strongtowns assets check
strongtowns assets build
```

The umbrella command verifies every definition's declared artifacts against
`strongtowns-data.lock.json` before invoking the library build engine. It never
fetches, builds, or promotes data. When an input is unavailable it stops before
rendering and prints the separate data preparation steps.

The engine then finds `projects/graphics`, recursively discovers every builder
registered through the library, and writes the requested publishing outputs
and manifests. Definition identity comes from the registration, never from its
directory or filename. There is no central registry or build file to update.

List the definitions that the engine found:

```bash
strongtowns assets list
```

Build one definition or publishing target:

```bash
strongtowns assets build assessed_value_per_acre
strongtowns assets build --target instagram
strongtowns assets build bza_cases_map --target instagram_story
```

`strongtowns-graphics list` and `strongtowns-graphics build` remain available
for library development and self-contained definitions. Detroit's definitions
use locked external inputs and therefore use the project-aware `strongtowns
assets` workflow.

The reusable Python API is also available from the installed library:

```python
from strongtowns_graphics import GraphicBuildSystem, GraphicFormat

build_system = GraphicBuildSystem.find()
build_system.build()
```

To define a new graphic, create one file:

```text
projects/graphics/src/graphics/my_graphic.py
```

Register a builder that returns `dict[str, Graphic]`:

```python
from strongtowns_graphics import Graphic, graphic_definition


@graphic_definition("my_graphic")
def build() -> dict[str, Graphic]:
    return {"my-graphic": make_my_graphic()}
```

It will appear in `strongtowns-graphics list` and participate in the next build
automatically. The file could instead be named or nested however the user
prefers. `projects/graphics/build.py` remains as a compatibility shim for the
previous command line.

Map definitions may configure dot translucency and collision overlap through
the public library model:

```python
from strongtowns_graphics import MapMarkerStyle

marker_style = MapMarkerStyle(opacity=0.78, overlap_fraction=0.10)
```

Pass that value to a map renderer's `marker_style=` parameter. An overlap of
`0.10` allows symbols to intersect by ten percent of their combined radii;
`0` keeps them fully separated.

Bar charts can declare a separate portrait orientation and category-label
angle while retaining one data and series definition:

```python
bar_chart(
    data,
    orientation=BarOrientation.HORIZONTAL,
    portrait_orientation=BarOrientation.VERTICAL,
    portrait_category_label_angle=-35,
    # category, series, arrangement, axis, and editorial copy...
)
```

Instagram typography follows the exported `MOBILE_TYPOGRAPHY` standard. Its
minimum is measured in the final 1600-unit composition canvas; nested map and
legend components convert that minimum into their own scaled coordinate space.

Mobile maps accept independent sibling content after their legend:

```python
map_on_mobile(
    graphic,
    legend=legend,
    insets=(left_hero, right_hero),
    segments=(
        MobileMapSegment(
            name="context",
            content=SvgComponent(context_markup, 1080, 180),
        ),
    ),
)
```

The map, legend, pocket insets, and segments belong to the map composition;
segments do not belong to the legend. Segments render after the legend and are
clipped at the visual/footer boundary when the preceding content is too tall.

The older `projects/detroit-land-use-forum/` modules currently provide the
data preparation and SVG visual components. They are inputs to this catalog;
they no longer determine where a publishing variant belongs.
