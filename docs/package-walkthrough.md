# Python guide

Use the data and graphics SDKs from Python scripts or notebooks.

## BZA cases

```python
from strongtowns_data import bza

dataset = bza.open()
setbacks = dataset.cases(search="side setback")
dataset.export("setbacks.csv", search="side setback")
```

For this project's pinned BZA data:

```python
from strongtowns_detroit.bza import dataset

cases = dataset()
print(cases.status())
```

See the [BZA guide](https://github.com/Strong-Towns-Detroit/strongtowns-data/blob/main/docs/bza.md)
for filters, updates, and version pins.

## Graphics

Start with the [Instagram notebooks](../projects/graphics/notebooks/README.md)
to generate and adapt existing graphics. The
[graphics guide](../projects/graphics/USING_GRAPHICS.md) covers selecting a graphic,
checking its inputs, and exporting it.

## Other data

The [Data SDK reference](https://github.com/Strong-Towns-Detroit/strongtowns-data/blob/main/docs/API.md)
covers parcels, census data, geography, use-code mapping, and dataset access.
The versions used by this project are listed in `strongtowns-data.lock.json`.

## Tests

```bash
uv sync --locked --extra dev
uv run pytest -q
```
