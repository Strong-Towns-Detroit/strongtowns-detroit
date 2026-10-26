# Strong Towns Detroit

Research, maps, and graphics about Detroit housing, land use, and BZA cases.

## Setup

**Requirements:** Python 3.12+

```bash
# Clone the repositories beside one another
git clone https://github.com/Strong-Towns-Detroit/strongtowns-detroit.git
git clone https://github.com/Strong-Towns-Detroit/strongtowns-data.git
git clone https://github.com/Strong-Towns-Detroit/strongtowns-graphics.git
git clone https://github.com/Strong-Towns-Detroit/strongtowns-cli.git
git clone https://github.com/Strong-Towns-Detroit/zoning-rule-engine.git
cd strongtowns-detroit

uv sync --locked --extra dev
uv run pytest -q
uv pip install --python .venv/bin/python --no-deps -e ../strongtowns-cli
.venv/bin/strongtowns doctor --require graphics --require data
```

The CLI requires Python 3.12+. `uv sync` installs this project and its pinned
data and graphics SDKs. Install the CLI with `--no-deps` to preserve those
versions: the CLI pins different SDK revisions, which can otherwise replace
the versions this project requires and cause missing-import errors. No extras
or separate zoning executable are needed. The commands above install into this
checkout's `.venv`. Run the examples below from this
repository's root; the explicit `.venv/bin/strongtowns` path uses that environment
even when another virtual environment or Conda environment is active.

For a standalone CLI install in your Python environment:

```bash
python -m pip install 'strongtowns-cli @ git+https://github.com/Strong-Towns-Detroit/strongtowns-cli.git@main'
```

The standalone CLI does not install this Detroit project package.

### Troubleshooting: `No module named 'strongtowns_detroit'`

This error means the Python environment running the CLI cannot import this
project's package. Changing into the repository alone does not make its `src/`
package importable. From this repository's root, install the project and CLI into
the same environment and run that CLI explicitly:

```bash
uv sync --locked --extra dev
uv pip install --python .venv/bin/python --no-deps -e ../strongtowns-cli
.venv/bin/strongtowns assets build --project . --target instagram
```

If `.venv/bin/python` can already import `strongtowns_detroit`, only the last two
commands are needed. Repeat the CLI install after a `uv sync` if it removes the
separately installed CLI.

### Data Files

Large and third-party evidence files are not checked into this repository.
Materialize the content-addressed inputs through `strongtowns-data`. Adjacent
clones are detected automatically; set `STRONGTOWNS_DATA_REPOSITORY` when using
a different checkout layout.

## Use the data and graphics

### Publishing graphics

Create Instagram posts, Stories, and conference graphics.

- Start with the [plain-language graphics guide](projects/graphics/USING_GRAPHICS.md)
  if you want to produce or revise graphics without working directly in code.
- Open the [Instagram example notebooks](projects/graphics/notebooks/README.md)
  to generate and adapt our existing graphics directly with the Python SDKs.
- Read the [graphics contributor guide](projects/graphics/CONTRIBUTING.md) before
  changing library APIs or adding reusable rendering behavior.
```bash
.venv/bin/strongtowns assets list --project .
.venv/bin/strongtowns assets check --project .
.venv/bin/strongtowns assets build --project . --target instagram
```

`assets check` reports input readiness. Select a graphic by placing its name
after `check` or `build`, or omit the name to select all.

### Reproducible data and local SQL

```bash
.venv/bin/strongtowns data status --repository ../strongtowns-data
.venv/bin/strongtowns data materialize strongtowns-data.lock.json .data \
  --repository ../strongtowns-data
```

### BZA cases

```bash
.venv/bin/strongtowns bza list --search "side setback"
.venv/bin/strongtowns bza export --output cases.csv
```

See the [Python guide](docs/package-walkthrough.md) for SDK examples and this
project's pinned BZA dataset.

## Tests

```bash
uv sync --locked --extra dev
uv run pytest -q
cd sites/land-forum
npm ci
npm test
npm run tokens:check
npm run build
```

The default suite covers Detroit consumer boundaries, exhibit logic, and the
Land Forum. Library, data-engine, and zoning-compiler suites run in their own
repositories. See [AGENTS.md](AGENTS.md) for the locked environment and
clean-checkout workflow.

## License

This project analyzes publicly available municipal data and ordinances. The zoning ordinance text is published by the City of Detroit via Municode.
