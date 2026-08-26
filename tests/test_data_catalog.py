from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import geopandas as gpd
from shapely.geometry import Point

from strongtowns_detroit.data.catalog import (
    DATABASE_ARTIFACT,
    build_query_catalog,
    query_catalog,
    read_catalog_index,
    table_name_for_asset,
    validate_query_catalog_snapshot,
)
from strongtowns_detroit.data.engine import DataBuildSystem
from strongtowns_detroit.data.manifest import SnapshotStore, canonical_json
from strongtowns_detroit.data.manifest import sha256
from strongtowns_detroit.data.model import (
    AcquisitionPolicy,
    BuildMetadata,
    DataAsset,
    DataPipeline,
    DatasetContract,
    PipelineContext,
    ProvenanceGrade,
)


def tabular_asset(asset_id: str) -> DataAsset:
    return DataAsset(
        asset_id,
        Path("data/sources") / asset_id,
        DatasetContract(
            asset_id, "1.0.0",
            required_columns={"id": "string", "value": "int64"},
            primary_key=("id",), accepted_artifact="accepted.parquet",
        ),
    )


def catalog_asset() -> DataAsset:
    return DataAsset(
        "query.catalog", Path("data/derived/query-catalog"),
        DatasetContract(
            "query.catalog", "1.0.0",
            custom_validator=validate_query_catalog_snapshot,
        ),
    )


def promote_parent(store: SnapshotStore, item: DataAsset, values: list[int]):
    snapshot_id, staging = store.create_staging(item)
    pq.write_table(
        pa.table({
            "id": [f"row-{number}" for number in values],
            "value": values,
        }),
        staging / "accepted.parquet",
    )
    manifest = store.write_manifest(
        item, staging, snapshot_id,
        BuildMetadata(
            counts={"records": len(values)},
            provenance_grade=ProvenanceGrade.LEGACY,
        ),
        [],
    )
    return store.promote(item, staging, allow_legacy=True), manifest


def catalog_system(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "strongtowns_detroit.data.manifest.producer_state",
        lambda root: {"git_commit": "a" * 40, "dirty": False},
    )
    one = tabular_asset("source.one")
    two = tabular_asset("source.two")
    catalog = catalog_asset()
    source_one = DataPipeline(
        "source-one", (), (one,), acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK,
    )
    source_two = DataPipeline(
        "source-two", (), (two,), acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK,
    )

    def build(context: PipelineContext):
        return {
            catalog.id: build_query_catalog(
                context,
                output_asset=catalog.id,
                tables={one.id: "one", two.id: "two"},
            )
        }

    pipeline = DataPipeline(
        "catalog", (one.id, two.id), (catalog,), build=build,
    )
    system = DataBuildSystem(tmp_path, (source_one, source_two, pipeline))
    store = SnapshotStore(tmp_path)
    parent_one, _ = promote_parent(store, one, [1, 2])
    parent_two, _ = promote_parent(store, two, [10])
    records = system.build(["catalog"])
    catalog_directory = Path(records[-1]["path"])
    return system, catalog, catalog_directory, parent_one, parent_two


def test_table_name_is_stable_and_conservative():
    assert table_name_for_asset("Detroit.Base Units/Addresses") == (
        "detroit_base_units_addresses"
    )
    assert table_name_for_asset("123.rows") == "asset_123_rows"


def test_catalog_materializes_promoted_parquet_and_binds_lineage(tmp_path, monkeypatch):
    system, catalog, directory, _, _ = catalog_system(tmp_path, monkeypatch)
    index = read_catalog_index(directory)
    assert [(item["table_name"], item["rows"]) for item in index["tables"]] == [
        ("one", 2), ("two", 1),
    ]
    result = system.catalog_query(
        catalog.id,
        "SELECT sum(value) AS total FROM one UNION ALL SELECT sum(value) FROM two",
    )
    assert result["total"].to_list() == [3, 10]
    inspected = system.catalog_inspect(catalog.id)
    assert inspected["database_sha256"]
    assert inspected["snapshot_id"]


def test_catalog_is_materialized_and_survives_parent_file_removal(tmp_path, monkeypatch):
    _, _, directory, parent_one, parent_two = catalog_system(tmp_path, monkeypatch)
    (parent_one / "accepted.parquet").unlink()
    (parent_two / "accepted.parquet").unlink()
    result = query_catalog(directory, "SELECT count(*) AS rows FROM one")
    assert result.item() == 2


def test_catalog_build_is_byte_stable_for_identical_inputs(tmp_path, monkeypatch):
    system, _, first, _, _ = catalog_system(tmp_path, monkeypatch)
    second = Path(system.build(["catalog"])[-1]["path"])
    assert sha256(first / DATABASE_ARTIFACT) == sha256(second / DATABASE_ARTIFACT)
    assert (first / "catalog.json").read_bytes() == (second / "catalog.json").read_bytes()


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE one",
        "INSERT INTO one VALUES ('x', 3)",
        "SELECT 1; DROP TABLE one",
    ],
)
def test_catalog_query_rejects_mutating_or_multiple_statements(
    tmp_path, monkeypatch, sql
):
    _, _, directory, _, _ = catalog_system(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="exactly one SELECT"):
        query_catalog(directory, sql)
    assert query_catalog(directory, "SELECT count(*) FROM one").item() == 2


def test_catalog_query_disables_external_file_access(tmp_path, monkeypatch):
    _, _, directory, _, _ = catalog_system(tmp_path, monkeypatch)
    with pytest.raises(Exception, match="external access|disabled|Permission"):
        query_catalog(
            directory,
            "SELECT * FROM read_csv_auto('/private/etc/passwd')",
        )


def test_catalog_query_disables_extension_loading(tmp_path, monkeypatch):
    _, _, directory, _, _ = catalog_system(tmp_path, monkeypatch)
    settings = query_catalog(
        directory,
        "SELECT current_setting('autoinstall_known_extensions') AS auto_install, "
        "current_setting('autoload_known_extensions') AS auto_load, "
        "current_setting('enable_external_access') AS external_access",
    )
    assert settings.to_dicts() == [{
        "auto_install": False,
        "auto_load": False,
        "external_access": False,
    }]


def test_catalog_builder_rejects_table_name_collisions(tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    context = PipelineContext(
        tmp_path, "catalog",
        {"one": tmp_path, "two": tmp_path},
        {"one": {}, "two": {}},
        {"catalog": output},
    )
    with pytest.raises(ValueError, match="must be unique"):
        build_query_catalog(
            context, output_asset="catalog", tables={"one": "same", "two": "same"}
        )


def test_catalog_validator_detects_index_database_divergence(tmp_path, monkeypatch):
    system, catalog, directory, _, _ = catalog_system(tmp_path, monkeypatch)
    _, manifest = SnapshotStore(tmp_path).promoted(catalog)
    index_path = directory / "catalog.json"
    index = json.loads(index_path.read_text())
    index["tables"][0]["rows"] = 999
    index_path.write_bytes(canonical_json(index))
    with pytest.raises(ValueError, match="embedded catalog|row-count mismatch"):
        validate_query_catalog_snapshot(directory, manifest)


def test_catalog_database_contains_no_external_views(tmp_path, monkeypatch):
    _, _, directory, _, _ = catalog_system(tmp_path, monkeypatch)
    import duckdb

    connection = duckdb.connect(str(directory / DATABASE_ARTIFACT), read_only=True)
    try:
        rows = connection.execute(
            "SELECT table_name, table_type FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
    finally:
        connection.close()
    assert rows == [
        ("_strongtowns_catalog", "BASE TABLE"),
        ("one", "BASE TABLE"),
        ("two", "BASE TABLE"),
    ]


def test_catalog_materializes_geoparquet_without_spatial_extension(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "strongtowns_detroit.data.manifest.producer_state",
        lambda root: {"git_commit": "a" * 40, "dirty": False},
    )
    source = DataAsset(
        "source.points", Path("data/sources/points"),
        DatasetContract(
            "source.points", "1.0.0", required_columns={"id": "string"},
            primary_key=("id",), geometry_types=("Point",), crs="EPSG:4326",
            accepted_artifact="accepted.parquet",
        ),
    )
    catalog = catalog_asset()
    store = SnapshotStore(tmp_path)
    snapshot_id, staging = store.create_staging(source)
    gpd.GeoDataFrame(
        {"id": ["one", "two"]},
        geometry=[Point(-83.0, 42.0), Point(-83.1, 42.1)],
        crs="EPSG:4326",
    ).to_parquet(staging / "accepted.parquet", index=False)
    store.write_manifest(
        source, staging, snapshot_id,
        BuildMetadata(counts={"records": 2}, provenance_grade=ProvenanceGrade.LEGACY),
        [],
    )
    store.promote(source, staging, allow_legacy=True)

    def build(context):
        return {
            catalog.id: build_query_catalog(
                context, output_asset=catalog.id, tables={source.id: "points"}
            )
        }

    system = DataBuildSystem(
        tmp_path,
        (
            DataPipeline(
                "source", (), (source,),
                acquisition_policy=AcquisitionPolicy.PUBLIC_NETWORK,
            ),
            DataPipeline("catalog", (source.id,), (catalog,), build=build),
        ),
    )
    system.build(["catalog"])
    result = system.catalog_query(
        catalog.id, "SELECT count(*) AS rows, typeof(geometry) AS geometry_type FROM points GROUP BY 2"
    )
    assert result.to_dicts() == [{"rows": 2, "geometry_type": "GEOMETRY"}]
