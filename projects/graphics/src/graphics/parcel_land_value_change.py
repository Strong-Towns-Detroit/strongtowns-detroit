"""Comparable residential parcel land values, 2023–2026."""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import numpy as np
import polars as pl
import pyogrio

GRAPHICS = Path(__file__).resolve().parents[2]
ROOT = GRAPHICS.parents[1]
FORUM = ROOT / "projects" / "detroit-land-use-forum"
sys.path.insert(0, str(GRAPHICS))

from basemap import load_detroit_basemap  # noqa: E402
from strongtowns_graphics import (  # noqa: E402
    ContinuousChoroplethScale,
    graphic_definition,
    parcel_choropleth_map,
)
from strongtowns_data.pipelines.land_values import (  # noqa: E402
    LandValueSmoothing,
    SmoothingMode,
    apply_land_value_smoothing,
)

PARCELS = ROOT / "pipelines" / "parcel-data" / "parcels_with_compliance.gpkg"
DATASETS = ROOT / "data" / "datasets"
NO_DATA = "#e4dfd6"

VALUE_SCALE = ContinuousChoroplethScale(
    minimum=3_000,
    maximum=160_000,
    colors=("#b8d2ef", "#72a7df", "#fff1c9", "#ffbd59", "#ef8545", "#8f1d2d"),
    ticks=(
        (3_000, "≤$3K"),
        (10_000, "$10K"),
        (30_000, "$30K"),
        (100_000, "$100K"),
        (160_000, "≥$160K"),
    ),
    logarithmic=True,
)

CHANGE_SCALE = ContinuousChoroplethScale(
    minimum=-60_000,
    maximum=60_000,
    midpoint=0,
    colors=("#356daf", "#91b9e6", "#f5eddd", "#ffbd59", "#e8783d", "#9d2132"),
    ticks=(
        (-60_000, "≤−$60K"),
        (-30_000, "−$30K"),
        (0, "$0"),
        (30_000, "+$30K"),
        (60_000, "≥+$60K"),
    ),
)


def _local_artifact(dataset: str, filename: str) -> Path:
    """Use a promoted snapshot, or a sole local staging preview."""
    root = DATASETS / dataset
    pointer = root / "PROMOTED.json"
    if pointer.is_file():
        manifest = root / json.loads(pointer.read_text())["manifest"]
        artifact = manifest.parent / filename
        if artifact.is_file():
            return artifact
    candidates = sorted((root / ".staging").glob(f"*/{filename}"))
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"expected one promoted or staged {dataset}/{filename}; "
            f"found {len(candidates)}"
        )
    return candidates[0]


@lru_cache(maxsize=1)
def comparison_frame() -> gpd.GeoDataFrame:
    parcels = gpd.read_file(PARCELS, columns=["parcel_id", "geometry"])
    parcels = parcels.drop_duplicates("parcel_id").to_crs("EPSG:3857")
    centroids = parcels.geometry.centroid
    coordinates = pl.DataFrame({
        "parcel_id": parcels["parcel_id"].astype(str),
        "x": centroids.x,
        "y": centroids.y,
    })

    current_source = _local_artifact("detroit-assessments-source", "raw.geojson")
    current_rows = pyogrio.read_dataframe(
        current_source,
        read_geometry=False,
        columns=["parcel_id", "amt_land_value", "total_square_footage"],
    )
    current = pl.from_pandas(current_rows).select(
        pl.col("parcel_id").cast(pl.String),
        pl.col("amt_land_value").cast(pl.Float64, strict=False).alias("land_value"),
        pl.col("total_square_footage")
        .cast(pl.Float64, strict=False)
        .alias("parcel_area_sqft"),
    ).join(coordinates, on="parcel_id", how="inner")
    current = apply_land_value_smoothing(
        current,
        config=LandValueSmoothing(mode=SmoothingMode.ISOLATED_SPIKES),
    ).select("parcel_id", "parcel_area_sqft", "selected_land_value")

    history_source = _local_artifact(
        "detroit-lvt-estimator-2023-source", "raw.csv"
    )
    history = pl.read_csv(
        history_source,
        schema_overrides={"parcel_num": pl.String},
        infer_schema_length=10_000,
    ).select(
        pl.col("parcel_num").str.strip_chars().alias("parcel_id"),
        pl.col("land_value").cast(pl.Float64, strict=False).alias("land_value_2023"),
    ).filter(pl.col("land_value_2023") > 0)
    conflicting = history.group_by("parcel_id").agg(
        pl.col("land_value_2023").n_unique().alias("values")
    ).filter(pl.col("values") > 1)
    if conflicting.height:
        raise ValueError("2023 source has conflicting land values for a parcel")
    history = history.unique("parcel_id", keep="first")

    comparison = history.join(current, on="parcel_id", how="inner").filter(
        pl.col("parcel_area_sqft").is_finite()
        & (pl.col("parcel_area_sqft") > 0)
        & pl.col("selected_land_value").is_finite()
        & (pl.col("selected_land_value") > 0)
    ).with_columns(
        (
            pl.col("land_value_2023") / pl.col("parcel_area_sqft") * 43_560
        ).alias("land_value_per_acre_2023"),
        (
            pl.col("selected_land_value") / pl.col("parcel_area_sqft") * 43_560
        ).alias("land_value_per_acre_2026"),
    ).with_columns(
        (
            pl.col("land_value_per_acre_2026")
            - pl.col("land_value_per_acre_2023")
        ).alias("land_value_per_acre_change")
    )
    values = comparison.to_pandas()
    result = parcels.merge(values, on="parcel_id", how="left")
    for column in (
        "land_value_per_acre_2023",
        "land_value_per_acre_2026",
        "land_value_per_acre_change",
    ):
        result.loc[~np.isfinite(result[column]), column] = np.nan
    return result


@graphic_definition("parcel_land_value_change")
def build():
    frame = comparison_frame()
    comparable = int(frame["land_value_per_acre_2023"].notna().sum())
    sources = (
        "Sources: City of Detroit 2023 residential LVT estimator, 2026 tentative "
        "assessment roll, and current parcel geometry.",
    )
    common_subtitle = (
        f"Assessor-recorded land value per acre · same {comparable:,} residential parcels"
    )
    basemap = load_detroit_basemap()
    map_2023 = parcel_choropleth_map(
        frame,
        value_column="land_value_per_acre_2023",
        scale=VALUE_SCALE,
        basemap=basemap,
        title=("Detroit residential land values", "in 2023"),
        subtitle=common_subtitle,
        legend_heading="LAND VALUE PER ACRE",
        sources=sources,
        description=(
            "City-recorded 2023 land value per acre for residential parcels "
            "that can also be matched to the 2026 tentative assessment roll."
        ),
        missing_label="Outside comparison cohort",
        missing_color=NO_DATA,
    )
    map_2026 = parcel_choropleth_map(
        frame,
        value_column="land_value_per_acre_2026",
        scale=VALUE_SCALE,
        basemap=basemap,
        title=("Detroit residential land values", "estimated for 2026"),
        subtitle=(
            f"Filtered estimate per acre · same {comparable:,} residential parcels"
        ),
        legend_heading="LAND VALUE PER ACRE",
        sources=sources,
        description=(
            "Estimated 2026 land value per acre after replacing only isolated "
            "fourfold spatial spikes without nearby similarly valued parcels."
        ),
        missing_label="Outside comparison cohort",
        missing_color=NO_DATA,
    )
    change = parcel_choropleth_map(
        frame,
        value_column="land_value_per_acre_change",
        scale=CHANGE_SCALE,
        basemap=basemap,
        title=("Change in Detroit residential", "land values, 2023–2026"),
        subtitle=(
            f"Change per acre · same {comparable:,} residential parcels"
        ),
        legend_heading="CHANGE IN LAND VALUE PER ACRE",
        sources=sources,
        description=(
            "Difference between the filtered 2026 estimate and City-recorded "
            "2023 land value per acre for the common residential parcel cohort."
        ),
        missing_label="Outside comparison cohort",
        missing_color=NO_DATA,
    )
    return {
        "residential-land-value-2023": map_2023,
        "residential-land-value-2026": map_2026,
        "residential-land-value-change-2023-2026": change,
    }
