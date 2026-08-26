"""Reactive, read-only exploration of the promoted Strong Towns data catalog."""

import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from strongtowns_detroit.data import DataBuildSystem

    return DataBuildSystem, mo


@app.cell
def _(DataBuildSystem):
    system = DataBuildSystem.find()
    catalog_asset = "detroit.query.catalog"
    return catalog_asset, system


@app.cell
def _(mo):
    intro = mo.md(
        "# Strong Towns Detroit data explorer\n\n"
        "This notebook queries a local, immutable catalog in read-only mode. "
        "It cannot modify the catalog, read other files, make network "
        "requests, or trigger a paid provider operation."
    )
    intro
    return


@app.cell
def _(mo):
    sql = mo.ui.text_area(
        value="SELECT count(*) AS parcel_count FROM parcels",
        label="SQL query",
        full_width=True,
        rows=6,
    )
    run_query = mo.ui.run_button(label="Run read-only query")
    mo.vstack([sql, run_query])
    return run_query, sql


@app.cell
def _(catalog_asset, mo, run_query, sql, system):
    mo.stop(
        not run_query.value,
        mo.callout("Edit the SQL above, then run the query.", kind="info"),
    )
    try:
        result = system.catalog_query(catalog_asset, sql.value)
        output = mo.ui.table(result)
    except Exception as error:
        output = mo.callout(str(error), kind="danger")
    output
    return


if __name__ == "__main__":
    app.run()
