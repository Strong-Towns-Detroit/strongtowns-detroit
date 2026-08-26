from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from strongtowns_detroit.data.engine import DataBuildSystem
from strongtowns_detroit.data.manifest import (
    SnapshotStore,
    manifest_hash,
    validate_snapshot,
)
from strongtowns_detroit.data.model import (
    AcquisitionPolicy,
    BuildMetadata,
    DataAsset,
    DataPipeline,
    DatasetContract,
    PipelineContext,
    ProvenanceGrade,
)


CONTRACT = DatasetContract(
    "example.rows",
    "1.0.0",
    required_columns={"id": "string", "value": "int64"},
    primary_key=("id",),
    accepted_artifact="accepted.parquet",
    rejects_artifact="rejects.parquet",
)


def asset(name: str, path: str) -> DataAsset:
    return DataAsset(name, Path(path), CONTRACT)


def write_rows(context: PipelineContext, output: str, rows=None):
    rows = rows or {"id": ["a", "b"], "value": [1, 2]}
    target = context.staging[output]
    pq.write_table(pa.table(rows), target / "accepted.parquet")
    pq.write_table(
        pa.table({"source_row": pa.array([], type=pa.int64()), "reason": pa.array([], type=pa.string())}),
        target / "rejects.parquet",
    )
    return {
        output: BuildMetadata(
            counts={"input": len(rows["id"]), "accepted": len(rows["id"]), "rejected": 0},
            provenance_grade=ProvenanceGrade.LEGACY,
        )
    }


def test_contract_schema_hash_is_stable_across_mapping_order():
    other = DatasetContract(
        "example.rows", "1.0.0",
        required_columns={"value": "int64", "id": "string"},
        primary_key=("id",), accepted_artifact="accepted.parquet",
        rejects_artifact="rejects.parquet",
    )
    assert CONTRACT.schema_hash == other.schema_hash


def test_graph_orders_producers_before_consumers(tmp_path):
    raw = asset("raw", "data/sources/raw")
    derived = asset("derived", "data/derived/derived")
    first = DataPipeline("first", (), (raw,), build=lambda ctx: write_rows(ctx, "raw"))
    second = DataPipeline("second", ("raw",), (derived,), build=lambda ctx: write_rows(ctx, "derived"))
    system = DataBuildSystem(tmp_path, (second, first))
    assert [item.name for item in system.ordered(["second"])] == ["first", "second"]


def test_graph_rejects_duplicate_asset_producer(tmp_path):
    duplicate = asset("same", "data/sources/same")
    with pytest.raises(ValueError, match="duplicate asset producer"):
        DataBuildSystem(
            tmp_path,
            (
                DataPipeline("one", (), (duplicate,), build=lambda ctx: {}),
                DataPipeline("two", (), (duplicate,), build=lambda ctx: {}),
            ),
        )


def test_graph_rejects_unregistered_input(tmp_path):
    output = asset("output", "data/derived/output")
    with pytest.raises(ValueError, match="unknown inputs"):
        DataBuildSystem(
            tmp_path,
            (DataPipeline("broken", ("not.registered",), (output,), build=lambda ctx: {}),),
        )


def test_multi_output_pipeline_validates_all_outputs_before_any_promotion(tmp_path):
    one = asset("one", "data/derived/one")
    two = asset("two", "data/derived/two")

    def incomplete(context):
        first = write_rows(context, one.id)[one.id]
        return {one.id: first, two.id: BuildMetadata(counts={"records": 0})}

    system = DataBuildSystem(
        tmp_path, (DataPipeline("multi", (), (one, two), build=incomplete),)
    )
    with pytest.raises(ValueError, match="snapshot contains no artifacts"):
        system.build()
    assert not (tmp_path / one.path / "PROMOTED.json").exists()
    assert not (tmp_path / two.path / "PROMOTED.json").exists()


def test_graph_rejects_cycle(tmp_path):
    one = asset("one", "data/derived/one")
    two = asset("two", "data/derived/two")
    with pytest.raises(ValueError, match="cycle"):
        DataBuildSystem(
            tmp_path,
            (
                DataPipeline("one", ("two",), (one,), build=lambda ctx: {}),
                DataPipeline("two", ("one",), (two,), build=lambda ctx: {}),
            ),
        )


def test_legacy_import_rejects_changed_record_count(tmp_path):
    source = tmp_path / "legacy.csv"
    source.write_text("id,value\na,1\nb,2\n")
    item = DataAsset(
        "legacy", Path("data/sources/legacy"),
        DatasetContract("legacy", "1.0.0"),
        legacy_artifacts={"raw.csv": Path("legacy.csv")},
        legacy_counts={"records": 3},
    )
    system = DataBuildSystem(
        tmp_path, (DataPipeline("legacy", (), (item,), acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK),)
    )
    with pytest.raises(ValueError, match="expected.*3.*observed.*2"):
        system.import_legacy()


def test_legacy_import_observes_directory_file_count(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    (source / "one.txt").write_text("one")
    (source / "two.txt").write_text("two")
    item = DataAsset(
        "legacy", Path("data/sources/legacy"),
        DatasetContract("legacy", "1.0.0"),
        legacy_artifacts={"raw": Path("legacy")}, legacy_counts={"files": 2},
    )
    system = DataBuildSystem(
        tmp_path, (DataPipeline("legacy", (), (item,), acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK),)
    )
    records = system.import_legacy()
    assert records[0]["asset"] == "legacy"
    assert system.verify(["legacy"])[0]["state"] == "promoted"


def test_legacy_import_preflights_every_asset_before_promoting(tmp_path):
    (tmp_path / "one.csv").write_text("id\na\n")
    (tmp_path / "two.csv").write_text("id\na\n")
    one = DataAsset(
        "one", Path("data/sources/one"), DatasetContract("one", "1.0.0"),
        legacy_artifacts={"raw.csv": Path("one.csv")}, legacy_counts={"records": 1},
    )
    two = DataAsset(
        "two", Path("data/sources/two"), DatasetContract("two", "1.0.0"),
        legacy_artifacts={"raw.csv": Path("two.csv")}, legacy_counts={"records": 2},
    )
    system = DataBuildSystem(
        tmp_path,
        (
            DataPipeline("one", (), (one,), acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK),
            DataPipeline("two", (), (two,), acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK),
        ),
    )
    with pytest.raises(ValueError, match="legacy baseline mismatch for two"):
        system.import_legacy()
    assert not (tmp_path / one.path / "PROMOTED.json").exists()


def test_manifest_rejects_bad_reconciliation(tmp_path, monkeypatch):
    item = asset("rows", "data/sources/rows")
    store = SnapshotStore(tmp_path)
    snapshot_id, staging = store.create_staging(item)
    pq.write_table(pa.table({"id": ["a"], "value": [1]}), staging / "accepted.parquet")
    pq.write_table(
        pa.table({"source_row": [2], "reason": ["invalid"]}),
        staging / "rejects.parquet",
    )
    with pytest.raises(ValueError, match=r"accepted \+ rejected"):
        store.write_manifest(
            item, staging, snapshot_id,
            BuildMetadata(counts={"input": 3, "accepted": 1, "rejected": 1}),
            [],
        )


def test_manifest_rejects_row_count_that_disagrees_with_parquet(tmp_path):
    item = asset("rows", "data/sources/rows")
    store = SnapshotStore(tmp_path)
    snapshot_id, staging = store.create_staging(item)
    context = PipelineContext(tmp_path, "rows", {}, {}, {"rows": staging})
    write_rows(context, "rows")
    with pytest.raises(ValueError, match="accepted artifact row count"):
        store.write_manifest(
            item, staging, snapshot_id,
            BuildMetadata(counts={"input": 3, "accepted": 3, "rejected": 0}), [],
        )


def test_contract_rejects_unknown_enumerated_value(tmp_path):
    contract = DatasetContract(
        "enum", "1.0.0", required_columns={"id": "string", "state": "string"},
        allowed_values={"state": ("ready", "blocked")}, primary_key=("id",),
        accepted_artifact="accepted.parquet",
    )
    item = DataAsset("enum", Path("data/derived/enum"), contract)
    store = SnapshotStore(tmp_path)
    snapshot_id, staging = store.create_staging(item)
    pq.write_table(pa.table({"id": ["a"], "state": ["mystery"]}), staging / "accepted.parquet")
    with pytest.raises(ValueError, match="unknown state values"):
        store.write_manifest(item, staging, snapshot_id, BuildMetadata(counts={"records": 1}), [])


def test_snapshot_hash_validation_detects_corruption(tmp_path, monkeypatch):
    item = asset("rows", "data/sources/rows")
    store = SnapshotStore(tmp_path)
    snapshot_id, staging = store.create_staging(item)
    context = PipelineContext(tmp_path, "rows", {}, {}, {"rows": staging})
    metadata = write_rows(context, "rows")["rows"]
    manifest = store.write_manifest(item, staging, snapshot_id, metadata, [])
    (staging / "accepted.parquet").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="artifact size mismatch|artifact hash mismatch"):
        validate_snapshot(item, staging, manifest)


def test_dirty_snapshot_cannot_promote(tmp_path, monkeypatch):
    item = asset("rows", "data/sources/rows")
    store = SnapshotStore(tmp_path)
    snapshot_id, staging = store.create_staging(item)
    context = PipelineContext(tmp_path, "rows", {}, {}, {"rows": staging})
    metadata = write_rows(context, "rows")["rows"]
    store.write_manifest(item, staging, snapshot_id, metadata, [])
    manifest_path = staging / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["producer"]["dirty"] = True
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="dirty-code"):
        store.promote(item, staging)


def test_promoted_pointer_is_bound_to_manifest_hash(tmp_path, monkeypatch):
    item = asset("rows", "data/sources/rows")
    store = SnapshotStore(tmp_path)
    snapshot_id, staging = store.create_staging(item)
    context = PipelineContext(tmp_path, "rows", {}, {}, {"rows": staging})
    metadata = write_rows(context, "rows")["rows"]
    store.write_manifest(item, staging, snapshot_id, metadata, [])
    manifest = json.loads((staging / "manifest.json").read_text())
    manifest["producer"]["dirty"] = False
    (staging / "manifest.json").write_text(json.dumps(manifest))
    final = store.promote(item, staging)
    assert store.promoted(item)[0] == final
    pointer = store.asset_root(item) / "PROMOTED.json"
    data = json.loads(pointer.read_text())
    data["manifest_sha256"] = "0" * 64
    pointer.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="pointer hash mismatch"):
        store.promoted(item)


def test_verify_recursively_checks_immutable_parent_snapshot(tmp_path):
    parent = asset("parent", "data/sources/parent")
    child = asset("child", "data/derived/child")
    system = DataBuildSystem(
        tmp_path,
        (
            DataPipeline("parent", (), (parent,), build=lambda context: {}),
            DataPipeline("child", (parent.id,), (child,), build=lambda context: {}),
        ),
    )
    store = SnapshotStore(tmp_path)
    parent_id, parent_staging = store.create_staging(parent)
    parent_metadata = write_rows(
        PipelineContext(tmp_path, "parent", {}, {}, {parent.id: parent_staging}),
        parent.id,
    )[parent.id]
    parent_manifest = store.write_manifest(
        parent, parent_staging, parent_id, parent_metadata, [],
    )
    parent_directory = store.promote(parent, parent_staging, allow_legacy=True)

    child_id, child_staging = store.create_staging(child)
    child_metadata = write_rows(
        PipelineContext(tmp_path, "child", {}, {}, {child.id: child_staging}),
        child.id,
    )[child.id]
    store.write_manifest(
        child, child_staging, child_id, child_metadata,
        [{
            "dataset_id": parent.id,
            "snapshot_id": parent_manifest["snapshot_id"],
            "manifest_sha256": manifest_hash(parent_manifest),
        }],
    )
    store.promote(child, child_staging, allow_legacy=True)
    assert system.verify([child.id])[0]["state"] == "promoted"

    (parent_directory / "accepted.parquet").write_bytes(b"corrupt")
    result = system.verify([child.id])[0]
    assert result["state"] == "missing_or_invalid"
    assert "artifact size mismatch" in result["error"]
