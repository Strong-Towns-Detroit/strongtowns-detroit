"""Transactional Cloudflare R2 archive for registered immutable assets."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import canonical_json, sha256
from .model import ArchiveTier, DataAsset


PREFIX = "archive/v1"


def _validated_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("manifest_version") != "1.0.0" or payload.get("prefix") != PREFIX:
        raise ValueError("unsupported archive manifest")
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("archive entries must be an object")
    for key, meta in entries.items():
        if not isinstance(meta, dict) or not key.startswith(PREFIX + "/"):
            raise ValueError(f"invalid archive entry: {key}")
        required = {"path", "dataset_id", "tier", "size", "sha256"}
        if not required <= set(meta):
            raise ValueError(f"incomplete archive entry: {key}")
        path = Path(meta["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe archive path: {meta['path']}")
        if key != f"{PREFIX}/{path.as_posix()}":
            raise ValueError(f"archive key/path mismatch: {key}")
        if not isinstance(meta["size"], int) or meta["size"] < 0:
            raise ValueError(f"invalid archive size: {key}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(meta["sha256"])):
            raise ValueError(f"invalid archive hash: {key}")
    return payload


def _client():
    required = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError("missing R2 configuration: " + ", ".join(missing))
    try:
        import boto3
        from botocore.config import Config
    except ModuleNotFoundError as error:
        raise ValueError("install the archive dependency group to use R2") from error
    return boto3.client(
        "s3",
        endpoint_url=(
            f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
        ),
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
    )


@dataclass
class DataArchive:
    root: Path
    assets: tuple[DataAsset, ...]

    @property
    def manifest_path(self) -> Path:
        return self.root / "scripts" / "data_archive_manifest.json"

    def load(self) -> dict[str, Any]:
        if self.manifest_path.is_file():
            return _validated_manifest(json.loads(self.manifest_path.read_text()))
        return {"manifest_version": "1.0.0", "prefix": PREFIX, "entries": {}}

    def local_path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        path.relative_to(self.root.resolve())
        return path

    def selected(self, tiers: list[str] | None) -> tuple[DataAsset, ...]:
        wanted = {ArchiveTier(item) for item in (tiers or ["critical"])}
        return tuple(asset for asset in self.assets if asset.archive_tier in wanted)

    def files(self, asset: DataAsset) -> list[Path]:
        base = (self.root / asset.path).resolve()
        base.relative_to(self.root.resolve())
        if not base.exists():
            return []
        if base.is_file():
            return [base]
        return sorted(
            path for path in base.rglob("*")
            if path.is_file() and ".staging" not in path.parts and not path.is_symlink()
        )

    def key(self, path: Path) -> str:
        return f"{PREFIX}/{path.relative_to(self.root).as_posix()}"

    def status(self, tiers: list[str] | None = None) -> list[dict[str, Any]]:
        known = self.load()["entries"]
        records = []
        for asset in self.selected(tiers):
            paths = self.files(asset)
            archived = sum(
                1 for path in paths
                if known.get(self.key(path), {}).get("sha256") == sha256(path)
            )
            records.append({
                "tier": asset.archive_tier.value,
                "asset": asset.id,
                "files": len(paths),
                "bytes": sum(path.stat().st_size for path in paths),
                "archived": archived,
            })
        return records

    def push(self, tiers: list[str] | None = None, *, apply: bool = False) -> dict[str, Any]:
        manifest = self.load()
        next_entries = dict(manifest["entries"])
        pending = []
        for asset in self.selected(tiers):
            for path in self.files(asset):
                key = self.key(path)
                digest = sha256(path)
                if next_entries.get(key, {}).get("sha256") != digest:
                    pending.append((path, key, digest, asset))
        result = {
            "files": len(pending),
            "bytes": sum(item[0].stat().st_size for item in pending),
            "applied": apply,
        }
        if not apply or not pending:
            return result
        client = _client()
        bucket = os.environ["R2_BUCKET"]
        for path, key, digest, asset in pending:
            client.upload_file(str(path), bucket, key)
            next_entries[key] = {
                "path": path.relative_to(self.root).as_posix(),
                "dataset_id": asset.id,
                "tier": asset.archive_tier.value,
                "size": path.stat().st_size,
                "sha256": digest,
            }
        # Publish the local manifest only after every object upload succeeds.
        manifest["entries"] = dict(sorted(next_entries.items()))
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(canonical_json(manifest))
        os.replace(temporary, self.manifest_path)
        return result

    def pull(self, tiers: list[str] | None = None, *, apply: bool = False) -> dict[str, Any]:
        manifest = self.load()
        wanted = {asset.id for asset in self.selected(tiers)}
        entries = [
            (key, meta) for key, meta in sorted(manifest["entries"].items())
            if meta.get("dataset_id") in wanted
        ]
        pending = []
        for key, meta in entries:
            destination = self.local_path(meta["path"])
            if (
                not destination.is_file()
                or destination.stat().st_size != meta["size"]
                or sha256(destination) != meta["sha256"]
            ):
                pending.append((key, meta, destination))
        result = {
            "files": len(pending),
            "bytes": sum(meta["size"] for _, meta, _ in pending),
            "applied": apply,
        }
        if not apply or not pending:
            return result
        client = _client()
        bucket = os.environ["R2_BUCKET"]
        for key, meta, destination in pending:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".download")
            client.download_file(bucket, key, str(temporary))
            if temporary.stat().st_size != meta["size"] or sha256(temporary) != meta["sha256"]:
                temporary.unlink(missing_ok=True)
                raise ValueError(f"archive checksum mismatch: {meta['path']}")
            os.replace(temporary, destination)
        return result
