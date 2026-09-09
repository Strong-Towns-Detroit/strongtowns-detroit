# Instagram graphics, step by step

These notebooks show how to make graphics directly with the Python graphics and
data SDKs. Open an example, run it, inspect the table and image, then make a copy
and change it. No website or graphics CLI is involved in rendering.

Start with **[00 — A small bar chart](00_start_here.ipynb)**. It uses clearly
labelled invented data and works without the Detroit datasets. The other nine
notebooks reproduce the twelve Instagram graphics in our existing definitions.

| Notebook | What it makes | Pattern to reuse |
| --- | --- | --- |
| [01 — Parking proposed and mandated](01_parking_gaps_by_project_type.ipynb) | Parking by project type | Filter records, aggregate a Polars table, encode stacked bars |
| [02 — BZA relief requests](02_bza_cases_map.ipynb) | Cases by primary request | Explicit point IDs, projected coordinates, categories, and magnitudes |
| [03 — BZA proposed uses](03_bza_proposed_use_map.ipynb) | Cases by proposed use | The same point-map renderer with another classification |
| [04 — Minimum lot area](04_minimum_lot_area.ipynb) | Lot-area map and statistic | Prepared parcel classifications and mobile map composition |
| [05 — Minimum lot width](05_minimum_lot_width.ipynb) | Frontage map and statistic | Reuse the parcel-map pattern for another measurement |
| [06 — Setback envelopes](06_residential_setback_envelope.ipynb) | Setback classification map | Display a prepared spatial assessment without rerunning the model |
| [07 — Assessed value per acre](07_assessed_value_per_acre.ipynb) | Assessment map and median | Normalize by area, distinguish missing records, add a statistic |
| [08 — Residential land values](08_parcel_land_value_change.ipynb) | 2023, 2026, and change maps | Continuous color scales and a consistent comparison cohort |
| [09 — Transit and driving](09_campus_martius_accessibility.ipynb) | Two travel-time maps | Compose prepared geographic layers and legends |

## Open the notebooks

A volunteer can do the initial setup. Use Python 3.12 or newer and `uv`. From the
**strongtowns-detroit repository root**, run:

```sh
uv run --locked --with jupyterlab --with ipykernel jupyter lab projects/graphics/notebooks
```

This launches JupyterLab in your browser with the project's locked data and
graphics SDKs. The first launch needs network access to install dependencies;
rendering prepared graphics does not fetch civic data. The optional notebook tools
are added for this command, without changing the project's dependency lock.
Select the Python kernel in that environment, not an unrelated system Python.
You can also open these `.ipynb` files in a notebook-capable editor using the same
environment.

For PNG downloads, install **librsvg**, which supplies `rsvg-convert`:

```sh
# macOS with Homebrew
brew install librsvg
# Ubuntu / Debian
sudo apt-get install librsvg2-bin
```

SVG and HTML exports do not need that system program. Set `EXPORT_PNG = False`
in the notebook's format cell if you want those formats first.

For notebooks 01–09, keep the `strongtowns-data` checkout beside this repository
with the snapshots named in `strongtowns-data.lock.json` already available. An
unusual checkout location can be configured with `STRONGTOWNS_DATA_REPOSITORY`.
If a prepared input is missing, ask the data maintainer to restore that pinned
snapshot. These examples never fetch, build, promote, or replace data. The transit
notebook uses existing travel-time bands; it does not call a paid routing API.

## Make your first graphic

1. Open `00_start_here.ipynb` and choose **Run → Run All Cells**.
2. Inspect the small input table and the image below it.
3. Change the headline in the `bar_chart(...)` cell and rerun that cell, the
   preview cell, and the export cell. When in doubt, **Restart Kernel and Run All**.
4. Try changing a numeric value or using `BarArrangement.GROUPED`.
5. Open notebook 01 to see the same pattern using actual prepared records.

Every real-data example has six steps: open libraries, resolve pinned inputs,
prepare and inspect the table, construct the graphic, preview a publishing
format, and export. The renderer calls expose wording, sources, descriptions,
and explicit encodings. Start there rather than rewriting setup code.

The bar, proportional-point, and continuous-choropleth notebooks call those
SDK renderers directly. Older parcel and travel graphics still use the project's
existing map-drawing helpers, then the SDK's mobile composition functions. Those
helpers are imported openly; their domain-specific assumptions have not been
moved into the SDK or hidden behind a new notebook framework.

## Adapt and share

- Duplicate a notebook before experimenting. Use a different `NOTEBOOK_NAME`
  to keep exports separate.
- Replace the input table with your own prepared data, then explicitly choose
  columns, labels, units, colors, and the question the graphic answers.
- Inspect coverage and denominators before keeping an existing headline.
  In particular, BZA marker size represents hearings; proposed-use labels are
  analytic groupings; assessed values are not sale prices; and missing values
  do not mean zero or compliance.
- Select `GraphicFormat.INSTAGRAM_POST` for 1080 × 1350 or
  `GraphicFormat.INSTAGRAM_STORY` for 1080 × 1920. The SDK preserves the standard
  layout and map scale; no notebook invents a publishing size.
- Look under `projects/graphics/output/notebooks/<NOTEBOOK_NAME>/<format>/` for
  PNG, SVG, HTML, alt text, and `sources.json` with the exact input identities.
  These generated files are ignored by Git. Inspect images and alt text before
  sharing; changing a title does not automatically update the description.

The full-city parcel maps can take several minutes and use substantial memory.
The examples deliberately do not silently sample parcels to speed up rendering.
The twelve real graphics retain their existing cohort, classification, smoothing,
and legal-threshold assumptions.

## Maintaining the examples

Canonical publishing definitions remain in `../src/graphics/`. The notebooks
are worked examples with the build function opened into editable cells, not a
second registration system. When publishing a change, update the canonical
definition and keep its notebook's method and wording aligned. Clear notebook
outputs and execution counts before committing, so generated graphics and large
tables are not embedded in Git.

To check all notebooks in fresh kernels (writes executed copies under the ignored
output directory):

```sh
uv run --locked --with nbclient --with nbformat --with ipykernel \
  python projects/graphics/notebooks/check_notebooks.py
```

This executes the actual cells, including PNG export when enabled. It requires
the same prepared snapshots as an interactive run. A failure identifies the
notebook and cell; there is no fallback to sample data or stale output.

Validation of this collection: all ten notebooks were executed in fresh Python
3.12 kernels against the SDK commits pinned by this project. The twelve existing
graphics plus the starter exported successfully at 1080 × 1350, with SVG, HTML,
alt text, and source identities. An in-memory copy of the starter was also changed
to grouped bars and successfully exported as a 1080 × 1920 story. Representative
chart and map PNGs were visually inspected; the 54 existing graphics and graphics
project tests passed. Source notebooks are saved with outputs cleared.
