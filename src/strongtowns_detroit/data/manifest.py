"""Immutable snapshot manifests, validation, and promotion."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import jsonschema
import pyarrow.parquet as pq

from .model import BuildMetadata, DataAsset, DatasetContract


MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "manifest_version", "dataset_id", "contract_version", "schema_hash",
        "snapshot_id", "producer", "parents", "artifacts", "counts",
        "created_at", "parameters", "source", "provenance_grade", "transaction_quality",
    ],
    "properties": {
        "manifest_version": {"const": "1.0.0"},
        "dataset_id": {"type": "string", "minLength": 1},
        "contract_version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
        "schema_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "snapshot_id": {
            "type": "string",
            "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        },
        "created_at": {"type": "string"},
        "producer": {
            "type": "object",
            "required": ["git_commit", "dirty"],
            "properties": {
                "git_commit": {"type": ["string", "null"]},
                "dirty": {"type": "boolean"},
            },
        },
        "parents": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["dataset_id", "snapshot_id", "manifest_sha256"],
                "properties": {
                    "dataset_id": {"type": "string", "minLength": 1},
                    "snapshot_id": {"type": "string", "minLength": 1},
                    "manifest_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
                "additionalProperties": False,
            },
        },
        "artifacts": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object",
                "required": ["path", "size", "sha256"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "size": {"type": "integer", "minimum": 0},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
                "additionalProperties": False,
            },
        },
        "counts": {"type": "object"},
        "parameters": {"type": "object"},
        "source": {"type": "object"},
        "provenance_grade": {"enum": ["captured", "legacy"]},
        "transaction_quality": {
            "enum": ["atomic", "best_effort", "provider_reconciled"]
        },
    },
}


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(manifest)).hexdigest()


def producer_state(root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
            capture_output=True, check=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, text=True,
            capture_output=True, check=True,
        ).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, True
    return {"git_commit": commit, "dirty": dirty}


def artifact_records(directory: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        if path.name == "manifest.json":
            continue
        records.append({
            "path": path.relative_to(directory).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        })
    if not records:
        raise ValueError(f"snapshot contains no artifacts: {directory}")
    return records


def _validate_parquet(
    contract: DatasetContract, directory: Path, counts: Mapping[str, Any]
) -> None:
    if not contract.accepted_artifact:
        return
    accepted = directory / contract.accepted_artifact
    if not accepted.is_file():
        raise ValueError(f"missing accepted artifact: {accepted}")
    table = pq.read_table(accepted)
    actual = {field.name: str(field.type) for field in table.schema}
    missing = set(contract.required_columns) - set(actual)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    mismatched = {
        name: (expected, actual[name])
        for name, expected in contract.required_columns.items()
        if name in actual and actual[name] != expected
    }
    if mismatched:
        raise ValueError(f"column type mismatch: {mismatched}")
    if contract.primary_key:
        frame = table.select(contract.primary_key).to_pandas()
        if frame.isna().any(axis=None):
            raise ValueError(f"null primary key in {contract.name}")
        if frame.duplicated().any():
            raise ValueError(f"duplicate primary key in {contract.name}")
    for name, permitted in contract.allowed_values.items():
        if name not in actual:
            raise ValueError(f"allowed-values column is missing: {name}")
        values = set(table.column(name).drop_null().to_pylist())
        unexpected = values - set(permitted)
        if unexpected:
            raise ValueError(f"unknown {name} values: {sorted(unexpected)}")
    if "accepted" in counts and table.num_rows != counts["accepted"]:
        raise ValueError("accepted artifact row count does not match manifest")
    if contract.rejects_artifact and not (directory / contract.rejects_artifact).is_file():
        raise ValueError(f"missing rejects artifact: {contract.rejects_artifact}")
    if contract.rejects_artifact and "rejected" in counts:
        rejected_rows = pq.ParquetFile(directory / contract.rejects_artifact).metadata.num_rows
        if rejected_rows != counts["rejected"]:
            raise ValueError("rejects artifact row count does not match manifest")
    if contract.geometry_types or contract.crs:
        import geopandas as gpd

        frame = gpd.read_parquet(accepted)
        if contract.crs and frame.crs is None:
            raise ValueError(f"missing CRS in {contract.name}")
        if contract.crs and frame.crs.to_string().upper() != contract.crs.upper():
            raise ValueError(
                f"CRS mismatch in {contract.name}: {frame.crs} != {contract.crs}"
            )
        if contract.geometry_types:
            actual_types = set(frame.geometry.dropna().geom_type.unique())
            unexpected = actual_types - set(contract.geometry_types)
            if unexpected:
                raise ValueError(f"unexpected geometry types: {sorted(unexpected)}")
        if not frame.geometry.dropna().is_valid.all():
            raise ValueError(f"invalid geometry in {contract.name}")
        if len(frame) and not __import__("numpy").isfinite(frame.total_bounds).all():
            raise ValueError(f"non-finite geometry coordinates in {contract.name}")


def validate_snapshot(
    asset: DataAsset, directory: Path, manifest: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    path = directory / "manifest.json"
    data = dict(manifest) if manifest is not None else json.loads(path.read_text())
    jsonschema.validate(data, MANIFEST_SCHEMA)
    created_at = datetime.fromisoformat(data["created_at"])
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("manifest created_at must be timezone-aware")
    if data["dataset_id"] != asset.id:
        raise ValueError(f"manifest dataset mismatch: {data['dataset_id']} != {asset.id}")
    if data["contract_version"] != asset.contract.version:
        raise ValueError("contract version mismatch")
    if data["schema_hash"] != asset.contract.schema_hash:
        raise ValueError("contract schema hash mismatch")
    for artifact in data["artifacts"]:
        artifact_path = (directory / artifact["path"]).resolve()
        artifact_path.relative_to(directory.resolve())
        if not artifact_path.is_file():
            raise ValueError(f"missing artifact: {artifact['path']}")
        if artifact_path.stat().st_size != artifact["size"]:
            raise ValueError(f"artifact size mismatch: {artifact['path']}")
        if sha256(artifact_path) != artifact["sha256"]:
            raise ValueError(f"artifact hash mismatch: {artifact['path']}")
    counts = data.get("counts", {})
    _validate_parquet(asset.contract, directory, counts)
    if {"input", "accepted", "rejected"} <= set(counts):
        if counts["accepted"] + counts["rejected"] != counts["input"]:
            raise ValueError("input count does not equal accepted + rejected")
        if counts["accepted"] <= 0:
            raise ValueError("accepted count must be positive")
    if asset.contract.custom_validator:
        asset.contract.custom_validator(directory, data)
    return data


@dataclass(frozen=True)
class SnapshotStore:
    root: Path

    def asset_root(self, asset: DataAsset) -> Path:
        path = (self.root / asset.path).resolve()
        path.relative_to(self.root.resolve())
        return path

    def create_staging(self, asset: DataAsset) -> tuple[str, Path]:
        snapshot_id = str(uuid4())
        path = self.asset_root(asset) / ".staging" / snapshot_id
        path.mkdir(parents=True, exist_ok=False)
        return snapshot_id, path

    def write_manifest(
        self,
        asset: DataAsset,
        staging: Path,
        snapshot_id: str,
        metadata: BuildMetadata,
        parents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        manifest = {
            "manifest_version": "1.0.0",
            "dataset_id": asset.id,
            "contract_version": asset.contract.version,
            "schema_hash": asset.contract.schema_hash,
            "snapshot_id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "producer": producer_state(self.root),
            "parents": parents,
            "artifacts": artifact_records(staging),
            "counts": dict(metadata.counts),
            "parameters": dict(metadata.parameters),
            "source": dict(metadata.source),
            "provenance_grade": metadata.provenance_grade.value,
            "transaction_quality": metadata.transaction_quality,
        }
        validate_snapshot(asset, staging, manifest)
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        return manifest

    def promote(self, asset: DataAsset, staging: Path, *, allow_legacy: bool = False) -> Path:
        manifest = validate_snapshot(asset, staging)
        if manifest["producer"]["dirty"] and not (
            allow_legacy and manifest["provenance_grade"] == "legacy"
        ):
            raise ValueError("dirty-code snapshots may be validated but cannot be promoted")
        final = self.asset_root(asset) / "snapshots" / (
            manifest["created_at"][:10] + "_" + manifest["snapshot_id"]
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            raise FileExistsError(final)
        os.replace(staging, final)
        pointer = {
            "dataset_id": asset.id,
            "manifest": str((final / "manifest.json").relative_to(self.asset_root(asset))),
            "manifest_sha256": sha256(final / "manifest.json"),
        }
        temporary = self.asset_root(asset) / "PROMOTED.json.tmp"
        temporary.write_bytes(canonical_json(pointer))
        os.replace(temporary, self.asset_root(asset) / "PROMOTED.json")
        return final

    def promoted(self, asset: DataAsset) -> tuple[Path, dict[str, Any]]:
        pointer_path = self.asset_root(asset) / "PROMOTED.json"
        if not pointer_path.is_file():
            raise FileNotFoundError(f"no promoted snapshot for {asset.id}")
        pointer = json.loads(pointer_path.read_text())
        if pointer.get("dataset_id") != asset.id:
            raise ValueError(f"promoted pointer dataset mismatch for {asset.id}")
        manifest_path = (self.asset_root(asset) / pointer["manifest"]).resolve()
        manifest_path.relative_to(self.asset_root(asset))
        if sha256(manifest_path) != pointer["manifest_sha256"]:
            raise ValueError(f"promoted pointer hash mismatch for {asset.id}")
        directory = manifest_path.parent
        return directory, validate_snapshot(asset, directory)

    def snapshot(self, asset: DataAsset, snapshot_id: str) -> tuple[Path, dict[str, Any]]:
        matches = list((self.asset_root(asset) / "snapshots").glob(f"*_{snapshot_id}"))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"expected one snapshot {snapshot_id} for {asset.id}; found {len(matches)}"
            )
        return matches[0], validate_snapshot(asset, matches[0])

    def discard(self, staging: Path) -> None:
        if staging.is_dir() and ".staging" in staging.parts:
            shutil.rmtree(staging)
