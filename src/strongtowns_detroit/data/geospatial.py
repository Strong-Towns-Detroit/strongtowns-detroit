"""Canonical GeoParquet builders shared by repository pipelines."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .model import BuildMetadata, PipelineBuilder, PipelineContext


def canonical_geojson_builder(
    *,
    input_asset: str,
    input_artifact: str,
    output_asset: str,
    primary_key: str,
    geometry_types: tuple[str, ...],
    target_crs: str = "EPSG:4326",
) -> PipelineBuilder:
    """Return a deterministic GeoJSON-to-GeoParquet canonicalizer.

    Invalid records are retained in ``rejects.parquet`` with a stable source-row
    locator and one enumerated reason. Source identifiers are converted to
    strings before any normalization or filtering.
    """

    def build(context: PipelineContext):
        source = context.inputs[input_asset] / input_artifact
        frame = gpd.read_file(source)
        input_count = len(frame)
        expected = context.input_manifests[input_asset].get("counts", {}).get("records")
        if expected is not None and input_count != expected:
            raise ValueError(
                f"{input_asset} legacy count drift: {input_count} != {expected}"
            )
        frame = frame.reset_index(drop=True)
        frame["source_row"] = frame.index.astype("int64")
        if primary_key not in frame:
            raise ValueError(f"missing source primary key: {primary_key}")
        frame[primary_key] = frame[primary_key].astype("string")

        reasons = pd.Series(pd.NA, index=frame.index, dtype="string")
        reasons.loc[frame[primary_key].isna() | frame[primary_key].eq("")] = "null_primary_key"
        reasons.loc[reasons.isna() & frame.geometry.isna()] = "null_geometry"
        reasons.loc[reasons.isna() & ~frame.geometry.is_valid] = "invalid_geometry"
        reasons.loc[
            reasons.isna() & ~frame.geometry.geom_type.isin(geometry_types)
        ] = "unexpected_geometry_type"
        duplicate = frame[primary_key].duplicated(keep="first") & reasons.isna()
        reasons.loc[duplicate] = "duplicate_primary_key"

        accepted = frame.loc[reasons.isna()].copy()
        rejected = pd.DataFrame({
            "source_row": frame.loc[reasons.notna(), "source_row"].astype("int64"),
            "source_id": frame.loc[reasons.notna(), primary_key].astype("string"),
            "reason": reasons.loc[reasons.notna()].astype("string"),
        })
        accepted = accepted.to_crs(target_crs)
        target = context.staging[output_asset]
        accepted.to_parquet(target / "accepted.parquet", index=False)
        rejected.to_parquet(target / "rejects.parquet", index=False)
        return {
            output_asset: BuildMetadata(
                counts={
                    "input": input_count,
                    "accepted": len(accepted),
                    "rejected": len(rejected),
                },
                parameters={
                    "primary_key": primary_key,
                    "geometry_types": list(geometry_types),
                    "target_crs": target_crs,
                },
            )
        }

    return build
