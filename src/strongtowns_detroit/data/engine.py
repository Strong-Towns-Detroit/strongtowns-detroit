"""Dependency-aware, offline-by-default data build engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv
import shutil

from .manifest import SnapshotStore, manifest_hash
from .model import AcquisitionPolicy, DataAsset, DataPipeline, PipelineContext
from .model import BuildMetadata, ProvenanceGrade
from .registry import discover


def _legacy_file_count(paths: list[Path]) -> int:
    return sum(
        1 if path.is_file() else sum(1 for child in path.rglob("*") if child.is_file())
        for path in paths
    )


def _legacy_record_count(paths: list[Path]) -> int:
    if len(paths) != 1 or not paths[0].is_file():
        raise ValueError("a legacy records baseline requires exactly one tabular file")
    path = paths[0]
    suffix = path.suffix.lower()
    if suffix in {".geojson", ".gpkg", ".shp"}:
        import pyogrio

        return int(pyogrio.read_info(path)["features"])
    if suffix in {".parquet", ".geoparquet"}:
        import pyarrow.parquet as pq

        return int(pq.ParquetFile(path).metadata.num_rows)
    if suffix == ".csv":
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            rows = csv.reader(handle)
            try:
                next(rows)
            except StopIteration:
                return 0
            return sum(1 for _ in rows)
    raise ValueError(f"cannot observe legacy record count for {path.suffix or path.name}")


def _observed_legacy_counts(asset: DataAsset, paths: list[Path]) -> dict[str, int]:
    observed: dict[str, int] = {}
    if "files" in asset.legacy_counts:
        observed["files"] = _legacy_file_count(paths)
    if "records" in asset.legacy_counts:
        observed["records"] = _legacy_record_count(paths)
    expected = dict(asset.legacy_counts)
    if observed != expected:
        raise ValueError(
            f"legacy baseline mismatch for {asset.id}: expected {expected}, observed {observed}"
        )
    return observed


@dataclass
class DataBuildSystem:
    root: Path
    pipelines: tuple[DataPipeline, ...] | None = None

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        if self.pipelines is None:
            self.pipelines = discover(self.root)
        self._validate_graph()

    @classmethod
    def find(cls, start: Path | str = ".") -> "DataBuildSystem":
        current = Path(start).resolve()
        if current.is_file():
            current = current.parent
        for candidate in (current, *current.parents):
            if (candidate / "strongtowns-data.toml").is_file():
                return cls(candidate)
        raise FileNotFoundError("no strongtowns-data.toml found")

    @property
    def assets(self) -> dict[str, DataAsset]:
        return {asset.id: asset for p in self.pipelines or () for asset in p.outputs}

    @property
    def producers(self) -> dict[str, DataPipeline]:
        return {asset.id: p for p in self.pipelines or () for asset in p.outputs}

    def _validate_graph(self) -> None:
        names: set[str] = set()
        assets: set[str] = set()
        for pipeline in self.pipelines or ():
            if pipeline.name in names:
                raise ValueError(f"duplicate pipeline: {pipeline.name}")
            names.add(pipeline.name)
            for output in pipeline.outputs:
                if output.id in assets:
                    raise ValueError(f"duplicate asset producer: {output.id}")
                assets.add(output.id)
                path = (self.root / output.path).resolve()
                path.relative_to(self.root)
        for pipeline in self.pipelines or ():
            unknown_inputs = set(pipeline.inputs) - assets
            if unknown_inputs:
                raise ValueError(
                    f"{pipeline.name} has unknown inputs: {sorted(unknown_inputs)}"
                )
        visiting: set[str] = set()
        visited: set[str] = set()
        producers = self.producers

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in visiting:
                raise ValueError(f"pipeline dependency cycle at {name}")
            visiting.add(name)
            pipeline = next(p for p in self.pipelines or () if p.name == name)
            for asset_id in pipeline.inputs:
                if asset_id in producers:
                    visit(producers[asset_id].name)
            visiting.remove(name)
            visited.add(name)

        for name in names:
            visit(name)

    def ordered(self, selected: list[str] | None = None) -> tuple[DataPipeline, ...]:
        by_name = {p.name: p for p in self.pipelines or ()}
        if selected:
            missing = set(selected) - set(by_name)
            if missing:
                raise ValueError(f"unknown pipelines: {sorted(missing)}")
            wanted = set(selected)
        else:
            wanted = set(by_name)
        producers = self.producers
        result: list[DataPipeline] = []
        seen: set[str] = set()

        def add(pipeline: DataPipeline) -> None:
            if pipeline.name in seen:
                return
            for input_id in pipeline.inputs:
                if input_id in producers:
                    add(producers[input_id])
            seen.add(pipeline.name)
            result.append(pipeline)

        for name in sorted(wanted):
            add(by_name[name])
        return tuple(result)

    def status(self) -> list[dict[str, Any]]:
        store = SnapshotStore(self.root)
        result = []
        for pipeline in self.pipelines or ():
            outputs = []
            for asset in pipeline.outputs:
                try:
                    directory, manifest = store.promoted(asset)
                    state = "promoted"
                    digest = manifest_hash(manifest)
                except (FileNotFoundError, ValueError):
                    directory, digest, state = None, None, "missing_or_invalid"
                outputs.append({"id": asset.id, "state": state, "path": directory, "manifest": digest})
            result.append({"pipeline": pipeline.name, "outputs": outputs})
        return result

    def verify(self, selected: list[str] | None = None) -> list[dict[str, Any]]:
        """Verify promoted snapshots and their immutable parent chains."""
        requested = set(selected or self.assets)
        unknown = requested - set(self.assets)
        if unknown:
            raise ValueError(f"unknown assets: {sorted(unknown)}")
        store = SnapshotStore(self.root)
        records = []
        verified: set[tuple[str, str]] = set()

        def verify_parents(manifest: dict[str, Any]) -> None:
            for parent in manifest["parents"]:
                key = (parent["dataset_id"], parent["snapshot_id"])
                if key in verified:
                    continue
                parent_asset = self.assets.get(parent["dataset_id"])
                if parent_asset is None:
                    raise ValueError(f"unknown parent dataset: {parent['dataset_id']}")
                _, parent_manifest = store.snapshot(parent_asset, parent["snapshot_id"])
                if manifest_hash(parent_manifest) != parent["manifest_sha256"]:
                    raise ValueError(
                        f"parent manifest hash mismatch for {parent['dataset_id']}"
                    )
                verified.add(key)
                verify_parents(parent_manifest)

        for asset_id in sorted(requested):
            asset = self.assets[asset_id]
            try:
                directory, manifest = store.promoted(asset)
                verify_parents(manifest)
                records.append({
                    "asset": asset_id,
                    "state": "promoted",
                    "path": directory,
                    "manifest": manifest_hash(manifest),
                })
            except (FileNotFoundError, ValueError) as error:
                records.append({
                    "asset": asset_id,
                    "state": "missing_or_invalid",
                    "error": str(error),
                })
        return records

    def import_legacy(self, selected: list[str] | None = None) -> list[dict[str, Any]]:
        """Register existing repository files without inventing provenance."""
        requested = set(selected or self.assets)
        missing_ids = requested - set(self.assets)
        if missing_ids:
            raise ValueError(f"unknown assets: {sorted(missing_ids)}")
        store = SnapshotStore(self.root)
        records = []
        prepared: dict[str, tuple[DataAsset, list[Path], dict[str, int]]] = {}
        for asset_id in sorted(requested):
            asset = self.assets[asset_id]
            if not asset.legacy_artifacts:
                continue
            sources = []
            for relative in asset.legacy_artifacts.values():
                source = (self.root / relative).resolve()
                source.relative_to(self.root)
                if not source.exists():
                    raise FileNotFoundError(source)
                sources.append(source)
            observed_counts = _observed_legacy_counts(asset, sources)
            prepared[asset_id] = (asset, sources, observed_counts)

        # Every requested legacy source must exist and match its observed
        # baseline before the first snapshot is copied or promoted.
        for asset_id in sorted(prepared):
            asset, sources, observed_counts = prepared[asset_id]
            snapshot_id, staging = store.create_staging(asset)
            for (artifact_name, _), source in zip(asset.legacy_artifacts.items(), sources):
                destination = staging / artifact_name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)
            metadata = BuildMetadata(
                counts=observed_counts,
                source={
                    "fingerprint": None,
                    "query": None,
                    "retrieved_at": None,
                    "legacy_paths": {
                        name: str(path) for name, path in asset.legacy_artifacts.items()
                    },
                },
                provenance_grade=ProvenanceGrade.LEGACY,
            )
            manifest = store.write_manifest(asset, staging, snapshot_id, metadata, [])
            final = store.promote(asset, staging, allow_legacy=True)
            records.append({
                "asset": asset.id,
                "path": final,
                "manifest": manifest_hash(manifest),
            })
        return records

    def build(self, selected: list[str] | None = None, *, promote: bool = True) -> list[dict[str, Any]]:
        store = SnapshotStore(self.root)
        records = []
        assets = self.assets
        ordered = self.ordered(selected)
        missing_sources: dict[str, list[str]] = {}
        for pipeline in ordered:
            if pipeline.acquisition_policy is not AcquisitionPolicy.LOCAL:
                continue
            missing = []
            for input_id in pipeline.inputs:
                producer = self.producers[input_id]
                if producer.acquisition_policy is AcquisitionPolicy.LOCAL:
                    continue
                try:
                    store.promoted(assets[input_id])
                except (FileNotFoundError, ValueError):
                    missing.append(input_id)
            if missing:
                missing_sources[pipeline.name] = sorted(missing)
        if missing_sources:
            details = "; ".join(
                f"{name}: {inputs}" for name, inputs in sorted(missing_sources.items())
            )
            raise ValueError(f"missing promoted acquisition inputs: {details}")

        for pipeline in ordered:
            if pipeline.acquisition_policy is not AcquisitionPolicy.LOCAL:
                continue
            if pipeline.build is None:
                raise ValueError(f"pipeline has no offline builder: {pipeline.name}")
            inputs, manifests, parents = {}, {}, []
            missing = []
            for input_id in pipeline.inputs:
                asset = assets.get(input_id)
                if asset is None:
                    missing.append(input_id)
                    continue
                try:
                    directory, manifest = store.promoted(asset)
                except (FileNotFoundError, ValueError):
                    missing.append(input_id)
                    continue
                inputs[input_id], manifests[input_id] = directory, manifest
                parents.append({
                    "dataset_id": input_id,
                    "snapshot_id": manifest["snapshot_id"],
                    "manifest_sha256": manifest_hash(manifest),
                })
            if missing:
                raise ValueError(f"{pipeline.name} missing promoted inputs: {sorted(missing)}")
            staging, ids = {}, {}
            for asset in pipeline.outputs:
                ids[asset.id], staging[asset.id] = store.create_staging(asset)
            context = PipelineContext(self.root, pipeline.name, inputs, manifests, staging)
            metadata = pipeline.build(context)
            if set(metadata) != {asset.id for asset in pipeline.outputs}:
                raise ValueError(f"{pipeline.name} did not return metadata for every output")
            completed = []
            for asset in pipeline.outputs:
                manifest = store.write_manifest(
                    asset, staging[asset.id], ids[asset.id], metadata[asset.id], parents
                )
                completed.append((asset, manifest))
            if promote and any(manifest["producer"]["dirty"] for _, manifest in completed):
                raise ValueError(
                    "dirty-code snapshots may be validated but cannot be promoted"
                )
            for asset, manifest in completed:
                final = store.promote(asset, staging[asset.id]) if promote else staging[asset.id]
                records.append({
                    "pipeline": pipeline.name, "asset": asset.id, "path": final,
                    "promoted": promote, "manifest": manifest_hash(manifest),
                })
        return records

    def fetch(
        self,
        name: str,
        *,
        apply: bool = False,
        allow_paid: bool = False,
        promote: bool = True,
    ) -> list[dict[str, Any]]:
        by_name = {pipeline.name: pipeline for pipeline in self.pipelines or ()}
        if name not in by_name:
            raise ValueError(f"unknown pipeline: {name}")
        pipeline = by_name[name]
        if pipeline.fetch is None:
            raise ValueError(f"pipeline has no acquisition implementation: {name}")
        if pipeline.acquisition_policy is AcquisitionPolicy.LOCAL:
            raise ValueError(f"pipeline is not an acquisition pipeline: {name}")
        if pipeline.acquisition_policy is AcquisitionPolicy.PAID and not allow_paid:
            raise ValueError("paid acquisition requires --allow-paid")
        if not apply:
            return [{
                "pipeline": name,
                "policy": pipeline.acquisition_policy.value,
                "outputs": [asset.id for asset in pipeline.outputs],
                "applied": False,
            }]
        store = SnapshotStore(self.root)
        assets = self.assets
        inputs, manifests, parents = {}, {}, []
        missing = []
        for input_id in pipeline.inputs:
            asset = assets.get(input_id)
            if asset is None:
                missing.append(input_id)
                continue
            try:
                directory, manifest = store.promoted(asset)
            except (FileNotFoundError, ValueError):
                missing.append(input_id)
                continue
            inputs[input_id], manifests[input_id] = directory, manifest
            parents.append({
                "dataset_id": input_id,
                "snapshot_id": manifest["snapshot_id"],
                "manifest_sha256": manifest_hash(manifest),
            })
        if missing:
            raise ValueError(f"{pipeline.name} missing promoted inputs: {sorted(missing)}")
        staging, ids = {}, {}
        for asset in pipeline.outputs:
            ids[asset.id], staging[asset.id] = store.create_staging(asset)
        context = PipelineContext(self.root, pipeline.name, inputs, manifests, staging)
        metadata = pipeline.fetch(context)
        if set(metadata) != {asset.id for asset in pipeline.outputs}:
            raise ValueError(f"{pipeline.name} did not return metadata for every output")
        records = []
        completed = []
        for asset in pipeline.outputs:
            manifest = store.write_manifest(
                asset, staging[asset.id], ids[asset.id], metadata[asset.id], parents
            )
            completed.append((asset, manifest))
        if promote and any(manifest["producer"]["dirty"] for _, manifest in completed):
            raise ValueError("dirty-code snapshots may be validated but cannot be promoted")
        for asset, manifest in completed:
            final = store.promote(asset, staging[asset.id]) if promote else staging[asset.id]
            records.append({
                "pipeline": pipeline.name,
                "asset": asset.id,
                "path": final,
                "promoted": promote,
                "manifest": manifest_hash(manifest),
                "applied": True,
            })
        return records

    def review_export(self) -> list[Path]:
        from .routing import export_review_packet

        assets = self.assets
        store = SnapshotStore(self.root)
        anchors_asset = assets["detroit.routing.anchors"]
        dispositions_asset = assets["detroit.routing.review-dispositions"]
        anchors_dir, _ = store.promoted(anchors_asset)
        dispositions_dir, dispositions_manifest = store.promoted(dispositions_asset)
        import geopandas as gpd
        import pandas as pd

        anchors = gpd.read_parquet(anchors_dir / "accepted.parquet")
        dispositions = pd.read_parquet(dispositions_dir / "accepted.parquet")
        paths = export_review_packet(
            anchors,
            dispositions,
            parent_manifest_sha256=manifest_hash(dispositions_manifest),
            directory=self.root / "data" / "reviews" / "routing-anchors",
        )
        return list(paths)

    def review_import(self, *, promote: bool = True) -> dict[str, Any]:
        from .routing import import_review_decisions
        import pandas as pd

        asset = self.assets["detroit.routing.review-dispositions"]
        store = SnapshotStore(self.root)
        current_dir, current_manifest = store.promoted(asset)
        parent_hash = manifest_hash(current_manifest)
        packet = self.root / "data" / "reviews" / "routing-anchors" / "routing-anchor-review.csv"
        if not packet.is_file():
            raise FileNotFoundError(packet)
        decisions = pd.read_csv(packet, dtype={"anchor_id": "string"})
        current = pd.read_parquet(current_dir / "accepted.parquet")
        updated = import_review_decisions(
            decisions, current,
            expected_parent_manifest_sha256=parent_hash,
        )
        snapshot_id, staging = store.create_staging(asset)
        updated.to_parquet(staging / "accepted.parquet", index=False)
        metadata = BuildMetadata(
            counts={"records": len(updated), "reviewed": int(updated.review_status.isin({"approved", "rejected"}).sum())},
            parameters={"review_packet": packet.relative_to(self.root).as_posix()},
        )
        manifest = store.write_manifest(
            asset, staging, snapshot_id, metadata,
            [{
                "dataset_id": asset.id,
                "snapshot_id": current_manifest["snapshot_id"],
                "manifest_sha256": parent_hash,
            }],
        )
        final = store.promote(asset, staging) if promote else staging
        return {"asset": asset.id, "path": final, "manifest": manifest_hash(manifest), "promoted": promote}

    def catalog_inspect(self, asset_id: str) -> dict[str, Any]:
        from .catalog import catalog_artifact_hash, read_catalog_index

        asset = self.assets.get(asset_id)
        if asset is None:
            raise ValueError(f"unknown asset: {asset_id}")
        directory, manifest = SnapshotStore(self.root).promoted(asset)
        index = read_catalog_index(directory)
        return {
            "asset": asset_id,
            "snapshot_id": manifest["snapshot_id"],
            "manifest_sha256": manifest_hash(manifest),
            "database_sha256": catalog_artifact_hash(directory),
            **index,
        }

    def catalog_query(self, asset_id: str, sql: str):
        from .catalog import query_catalog

        asset = self.assets.get(asset_id)
        if asset is None:
            raise ValueError(f"unknown asset: {asset_id}")
        directory, _ = SnapshotStore(self.root).promoted(asset)
        return query_catalog(directory, sql)
