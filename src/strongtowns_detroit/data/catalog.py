"""Portable, read-only analytical catalogs built from promoted Parquet data."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

from .manifest import canonical_json, manifest_hash, sha256
from .model import BuildMetadata, PipelineContext


CATALOG_VERSION = "1.0.0"
DATABASE_ARTIFACT = "catalog.duckdb"
INDEX_ARTIFACT = "catalog.json"
INTERNAL_TABLE = "_strongtowns_catalog"


def table_name_for_asset(asset_id: str) -> str:
    name = re.sub(r"[^0-9A-Za-z]+", "_", asset_id).strip("_").lower()
    if not name:
        raise ValueError(f"asset ID has no usable table name: {asset_id!r}")
    if name[0].isdigit():
        name = "asset_" + name
    return name


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _connection(path: Path, *, read_only: bool):
    return duckdb.connect(
        str(path),
        read_only=read_only,
        config={
            "autoinstall_known_extensions": "false",
            "autoload_known_extensions": "false",
            "enable_external_access": "false" if read_only else "true",
        },
    )


def build_query_catalog(
    context: PipelineContext,
    *,
    output_asset: str,
    tables: Mapping[str, str | None],
    input_artifact: str = "accepted.parquet",
) -> BuildMetadata:
    """Materialize promoted Parquet parents into one downloadable DuckDB file."""
    resolved: list[tuple[str, str]] = []
    for asset_id, requested_name in tables.items():
        if asset_id not in context.inputs or asset_id not in context.input_manifests:
            raise ValueError(f"catalog input is not promoted: {asset_id}")
        resolved.append((asset_id, requested_name or table_name_for_asset(asset_id)))
    names = [name for _, name in resolved]
    if len(names) != len(set(names)):
        raise ValueError("catalog table names must be unique")
    if INTERNAL_TABLE in names:
        raise ValueError(f"catalog table name is reserved: {INTERNAL_TABLE}")

    target = context.staging[output_asset]
    database_path = target / DATABASE_ARTIFACT
    records: list[dict[str, Any]] = []
    connection = _connection(database_path, read_only=False)
    try:
        connection.execute("SET autoinstall_known_extensions = false")
        connection.execute("SET autoload_known_extensions = false")
        for asset_id, table_name in resolved:
            source = context.inputs[asset_id] / input_artifact
            if not source.is_file():
                raise ValueError(f"missing catalog input artifact: {asset_id}/{input_artifact}")
            connection.execute(
                f"CREATE TABLE {_quoted_identifier(table_name)} AS "
                "SELECT * FROM read_parquet(?)",
                [str(source)],
            )
            row_count = int(
                connection.execute(
                    f"SELECT count(*) FROM {_quoted_identifier(table_name)}"
                ).fetchone()[0]
            )
            manifest = context.input_manifests[asset_id]
            artifact = next(
                (item for item in manifest["artifacts"] if item["path"] == input_artifact),
                None,
            )
            if artifact is None:
                raise ValueError(
                    f"input manifest does not bind {asset_id}/{input_artifact}"
                )
            records.append({
                "asset_id": asset_id,
                "table_name": table_name,
                "snapshot_id": manifest["snapshot_id"],
                "manifest_sha256": manifest_hash(manifest),
                "artifact": input_artifact,
                "artifact_sha256": artifact["sha256"],
                "rows": row_count,
            })
        connection.execute(
            f"CREATE TABLE {_quoted_identifier(INTERNAL_TABLE)} ("
            "asset_id VARCHAR NOT NULL, table_name VARCHAR NOT NULL, "
            "snapshot_id VARCHAR NOT NULL, manifest_sha256 VARCHAR NOT NULL, "
            "artifact VARCHAR NOT NULL, artifact_sha256 VARCHAR NOT NULL, "
            "rows BIGINT NOT NULL)"
        )
        connection.executemany(
            f"INSERT INTO {_quoted_identifier(INTERNAL_TABLE)} VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item["asset_id"], item["table_name"], item["snapshot_id"],
                    item["manifest_sha256"], item["artifact"],
                    item["artifact_sha256"], item["rows"],
                )
                for item in records
            ],
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()

    index = {
        "catalog_version": CATALOG_VERSION,
        "database": DATABASE_ARTIFACT,
        "tables": records,
    }
    (target / INDEX_ARTIFACT).write_bytes(canonical_json(index))
    return BuildMetadata(
        counts={
            "tables": len(records),
            "records": sum(record["rows"] for record in records),
        },
        parameters={
            "catalog_version": CATALOG_VERSION,
            "input_artifact": input_artifact,
            "table_mapping": {
                record["asset_id"]: record["table_name"] for record in records
            },
            "materialized": True,
            "consumer_access": "read_only",
        },
    )


def read_catalog_index(directory: Path) -> dict[str, Any]:
    index_path = directory / INDEX_ARTIFACT
    if not index_path.is_file():
        raise ValueError(f"missing catalog index: {INDEX_ARTIFACT}")
    value = json.loads(index_path.read_text())
    if value.get("catalog_version") != CATALOG_VERSION:
        raise ValueError("unsupported query catalog version")
    if value.get("database") != DATABASE_ARTIFACT:
        raise ValueError("catalog index names an unexpected database artifact")
    tables = value.get("tables")
    if not isinstance(tables, list) or not tables:
        raise ValueError("query catalog must contain at least one table")
    names = [item.get("table_name") for item in tables]
    assets = [item.get("asset_id") for item in tables]
    if len(names) != len(set(names)) or len(assets) != len(set(assets)):
        raise ValueError("query catalog contains duplicate table or asset identities")
    required = {
        "asset_id", "table_name", "snapshot_id", "manifest_sha256",
        "artifact", "artifact_sha256", "rows",
    }
    for item in tables:
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError("query catalog table entry has an invalid schema")
        if not all(
            isinstance(item[name], str) and item[name]
            for name in required - {"rows"}
        ):
            raise ValueError("query catalog table entry has an invalid string field")
        if not isinstance(item["rows"], int) or item["rows"] < 0:
            raise ValueError("query catalog table row count must be nonnegative")
        if not re.fullmatch(r"[0-9a-f]{64}", item["manifest_sha256"]):
            raise ValueError("query catalog contains an invalid manifest hash")
        if not re.fullmatch(r"[0-9a-f]{64}", item["artifact_sha256"]):
            raise ValueError("query catalog contains an invalid artifact hash")
    return value


def validate_query_catalog_snapshot(directory: Path, manifest: Mapping[str, Any]) -> None:
    index = read_catalog_index(directory)
    database_path = directory / DATABASE_ARTIFACT
    if not database_path.is_file():
        raise ValueError(f"missing query database: {DATABASE_ARTIFACT}")
    parents = {
        (item["dataset_id"], item["snapshot_id"]): item["manifest_sha256"]
        for item in manifest["parents"]
    }
    expected_parents = {
        (item["asset_id"], item["snapshot_id"]): item["manifest_sha256"]
        for item in index["tables"]
    }
    if parents != expected_parents:
        raise ValueError("catalog parent set does not match catalog index")
    connection = _connection(database_path, read_only=True)
    try:
        database_tables = {
            row[0]
            for row in connection.execute("SHOW TABLES").fetchall()
        }
        expected_tables = {INTERNAL_TABLE} | {
            item["table_name"] for item in index["tables"]
        }
        if database_tables != expected_tables:
            raise ValueError("database tables do not match catalog index")
        internal = connection.execute(
            f"SELECT asset_id, table_name, snapshot_id, manifest_sha256, "
            f"artifact, artifact_sha256, rows FROM {_quoted_identifier(INTERNAL_TABLE)} "
            "ORDER BY asset_id"
        ).fetchall()
        indexed = [
            (
                item["asset_id"], item["table_name"], item["snapshot_id"],
                item["manifest_sha256"], item["artifact"],
                item["artifact_sha256"], item["rows"],
            )
            for item in sorted(index["tables"], key=lambda item: item["asset_id"])
        ]
        if internal != indexed:
            raise ValueError("embedded catalog does not match catalog index")
        for item in index["tables"]:
            rows = int(connection.execute(
                f"SELECT count(*) FROM {_quoted_identifier(item['table_name'])}"
            ).fetchone()[0])
            if rows != item["rows"]:
                raise ValueError(f"catalog row-count mismatch: {item['table_name']}")
            parent_key = (item["asset_id"], item["snapshot_id"])
            if parents.get(parent_key) != item["manifest_sha256"]:
                raise ValueError(f"catalog lineage mismatch: {item['asset_id']}")
    finally:
        connection.close()
    if manifest["counts"].get("tables") != len(index["tables"]):
        raise ValueError("catalog table count does not match manifest")
    if manifest["counts"].get("records") != sum(
        item["rows"] for item in index["tables"]
    ):
        raise ValueError("catalog record count does not match manifest")


def query_catalog(
    directory: Path,
    sql: str,
    parameters: Sequence[Any] | Mapping[str, Any] | None = None,
) -> pl.DataFrame:
    """Run exactly one read-only SELECT against a validated catalog."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("query catalog is missing its contract manifest")
    manifest = json.loads(manifest_path.read_text())
    expected_artifacts = {
        item["path"]: item for item in manifest.get("artifacts", [])
        if item.get("path") in {DATABASE_ARTIFACT, INDEX_ARTIFACT}
    }
    if set(expected_artifacts) != {DATABASE_ARTIFACT, INDEX_ARTIFACT}:
        raise ValueError("catalog manifest does not bind both portable artifacts")
    for name, expected in expected_artifacts.items():
        path = directory / name
        if (
            not path.is_file()
            or path.stat().st_size != expected["size"]
            or sha256(path) != expected["sha256"]
        ):
            raise ValueError(f"catalog artifact failed integrity check: {name}")
    validate_query_catalog_snapshot(directory, manifest)
    database_path = directory / DATABASE_ARTIFACT
    connection = _connection(database_path, read_only=True)
    try:
        statements = connection.extract_statements(sql)
        if len(statements) != 1 or statements[0].type.name != "SELECT":
            raise ValueError("catalog queries must contain exactly one SELECT statement")
        result = connection.execute(sql, parameters or []).pl()
    finally:
        connection.close()
    return result


def catalog_artifact_hash(directory: Path) -> str:
    return sha256(directory / DATABASE_ARTIFACT)
