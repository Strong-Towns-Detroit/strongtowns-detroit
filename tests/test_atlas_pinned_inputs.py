"""Exercise public JSON generation using real temporary snapshot manifests."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, LineString, box
from strongtowns_data.models import DataAsset, DataAssetRef, DatasetModel, BuildMetadata
from strongtowns_data.pipelines.snapshots import SnapshotStore, sha256
from strongtowns_data.repository import DataLock

SCRIPTS = Path(__file__).parents[1] / "sites/land-forum/scripts"


@pytest.fixture
def atlas(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("atlas_fixture_builder", SCRIPTS / "build_bza_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pinned_atlas(tmp_path, monkeypatch, atlas):
    import atlas_inputs
    store = SnapshotStore(tmp_path)
    assets, references = {}, []
    for dataset in {dataset for dataset, _ in atlas_inputs.REQUIREMENTS.values()}:
        asset = DataAsset(dataset, Path("datasets") / dataset, DatasetModel(dataset, "1.0.0"))
        assets[dataset] = asset
        snapshot, staging = store.create_staging(asset)
        for alias, (owner, artifact) in atlas_inputs.REQUIREMENTS.items():
            if owner != dataset:
                continue
            target = staging / artifact
            target.parent.mkdir(parents=True, exist_ok=True)
            if alias == "histories":
                pd.DataFrame([dict(case_history_id="case-1", printed_case_number="17-24", location="Detroit", petitioner="Applicant", proposal="A duplex", final_outcome="granted", first_meeting_date="2024-01-01", last_meeting_date="2024-01-01", appearance_count=1)]).to_csv(target, index=False)
            elif alias == "occurrences":
                pd.DataFrame([dict(case_history_id="case-1", meeting_date="2024-01-01", decision_status="decided", decision="Granted", source_file="minutes.pdf", source_url="https://example.org/minutes.pdf")]).to_csv(target, index=False)
            elif alias == "applications":
                pd.DataFrame([dict(case_history_id="case-1", category="lot_dimensions", relief_categories="lot_dimensions")]).to_csv(target, index=False)
            elif alias == "sites":
                gpd.GeoDataFrame([dict(case_history_id="case-1", site_id="site-1", parcel_id="p1", address="1 Test Street")], geometry=[Point(-83.1, 42.36)], crs=4326).to_file(target, driver="GPKG")
            elif alias == "roads":
                gpd.GeoDataFrame([dict(road_class="major", road_width_m=20, width_source="fixture")], geometry=[LineString([(-83.1, 42.35), (-83.1, 42.37)])], crs=4326).to_file(target, driver="GeoJSON")
            else:
                gpd.GeoDataFrame(geometry=[box(-83.2, 42.3, -83, 42.4)], crs=4326).to_file(target, driver="GeoJSON")
        store.write_manifest(asset, staging, snapshot, BuildMetadata(), [], producer={"git_commit": "fixture", "dirty": False})
        source = store.promote(asset, staging)
        references.append(DataAssetRef(dataset, snapshot, sha256(source / "manifest.json")))
    lock_path = tmp_path / "lock.json"
    DataLock(tuple(references)).write(lock_path)
    monkeypatch.setattr(atlas_inputs.DataBuildSystem, "find", lambda _: SimpleNamespace(root=tmp_path, assets=assets))
    return lock_path, tmp_path / "public"


def test_preflight_is_read_only_and_build_uses_only_pinned_artifacts(atlas, pinned_atlas):
    lock, output = pinned_atlas
    original_lock = lock.read_bytes()
    atlas.main(["--lock", str(lock), "--output", str(output), "--check"])
    assert not output.exists()
    atlas.main(["--lock", str(lock), "--output", str(output)])
    cases = json.loads((output / "bza-cases.json").read_text())
    assert cases[0]["address"] == "1 Test Street"
    assert cases[0]["hearings"][0]["sourceUrl"] == "https://example.org/minutes.pdf"
    assert json.loads((output / "bza-map.json").read_text())[0]["caseIds"] == ["case-1"]
    assert len(json.loads((output / "detroit-context.geojson").read_text())["features"]) == 2
    assert len(json.loads((output / "bza-provenance.json").read_text())["inputs"]) == 3
    assert lock.read_bytes() == original_lock


def test_missing_pins_fail_before_output(atlas, pinned_atlas):
    lock, output = pinned_atlas
    DataLock(()).write(lock)
    with pytest.raises(ValueError, match="never fetches or changes locks"):
        atlas.main(["--lock", str(lock), "--output", str(output)])
    assert not output.exists()


def test_source_url_does_not_guess_or_accept_active_content(atlas):
    assert atlas.source_url("minutes.pdf") is None
    assert atlas.source_url("javascript:alert(1)") is None


def test_studio_keeps_unmapped_and_undated_records_and_content_address(atlas, tmp_path):
    import hashlib
    base = dict(id="case-1", caseNumber="17-24", address="Detroit", location="Detroit", petitioner="Applicant", proposal="", category="height", categoryLabel="Height", outcome="granted_reversed", outcomeLabel="Request granted", firstDate="2024-01-01", lastDate="2024-02-01", hearings=[], lat=42.36, lon=-83.1, appearances=3)
    unknown = dict(base, id="case-2", category=None, outcome="", lat=None, lon=None, firstDate="", lastDate="")
    atlas.write_studio_bundle([base, unknown], {"test": {"snapshot_id": "pinned", "manifest_sha256": "a" * 64}}, tmp_path)
    destination = tmp_path / "bza-studio"
    latest = json.loads((destination / "latest.json").read_text())
    payload = (destination / f"{latest['bundle']}.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == latest["bundle"]
    bundle = json.loads(payload)
    assert len(bundle["cases"]) == 2
    assert bundle["cases"][1]["mapped"] is False
    assert bundle["cases"][1]["category"] == "unspecified"
    assert bundle["cases"][1]["outcome"] == "unclassified"
    assert bundle["coverage"] == {"firstDate": "2024-01-01", "lastDate": "2024-02-01"}
    comparison = json.loads((destination / "comparison.json").read_text())
    assert comparison["undatedCases"] == 1
    atlas.write_studio_bundle([unknown, base], {"test": {"snapshot_id": "pinned", "manifest_sha256": "a" * 64}}, tmp_path)
    assert json.loads((destination / "latest.json").read_text()) == latest
    atlas.write_studio_bundle([base], {}, tmp_path)
    assert (destination / f"{latest['bundle']}.json").read_bytes() == payload


def test_studio_preserves_known_categories_from_primary_request_helper(atlas, tmp_path):
    record = dict(id="parking-case", category="parking", categoryLabel="Request not specified", outcome="granted_reversed", outcomeLabel="Request granted", firstDate="2024-01-01", lastDate="2024-01-01", hearings=[], lat=42, lon=-83)
    atlas.write_studio_bundle([record], {}, tmp_path, {"parking": "Parking"})
    latest = json.loads((tmp_path / "bza-studio/latest.json").read_text())
    case = json.loads((tmp_path / "bza-studio" / f"{latest['bundle']}.json").read_text())["cases"][0]
    assert case["category"] == "parking"
    assert case["categoryLabel"] == "Parking"


def test_studio_only_preserves_existing_atlas(atlas, pinned_atlas):
    lock, output = pinned_atlas
    atlas.main(["--lock", str(lock), "--output", str(output)])
    original = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    atlas.main(["--lock", str(lock), "--output", str(output), "--studio-only"])
    assert original == {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    assert (output / "bza-studio/latest.json").exists()


def test_parcel_index_shards_preserve_identifiers_and_stay_within_output(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import build_parcel_tiles
    build_parcel_tiles.write_parcel_index({"000001": [-83, 42], "000002": [-84, 43], "../x": [-85, 44]}, tmp_path)
    directory = json.loads((tmp_path / "parcel-index.json").read_text())
    assert directory["version"] == 1
    assert len(directory["shards"]) == 2
    shard = tmp_path / "parcel-index" / Path(directory["shards"]["00000"]).name
    assert json.loads(shard.read_text()) == {"000001": [-83, 42], "000002": [-84, 43]}
    assert len(list((tmp_path / "parcel-index").glob("*.json"))) == 2
