import json
from pathlib import Path

import pytest

from strongtowns_detroit.data.archive import DataArchive, PREFIX
from strongtowns_detroit.data.model import ArchiveTier, DataAsset, DatasetContract


def archived_asset() -> DataAsset:
    return DataAsset(
        "source.example",
        Path("data/sources/example"),
        DatasetContract("source.example", "1.0.0"),
        ArchiveTier.SOURCE,
    )


class Client:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.uploads = []
        self.objects = {}

    def upload_file(self, path, bucket, key):
        if self.fail:
            raise RuntimeError("upload failed")
        self.uploads.append((path, bucket, key))
        self.objects[key] = Path(path).read_bytes()

    def download_file(self, bucket, key, path):
        Path(path).write_bytes(self.objects[key])


def setup_archive(tmp_path):
    path = tmp_path / "data/sources/example/snapshots/one"
    path.mkdir(parents=True)
    (path / "data.bin").write_bytes(b"source bytes")
    return DataArchive(tmp_path, (archived_asset(),))


def test_archive_push_is_dry_run_by_default(tmp_path):
    archive = setup_archive(tmp_path)
    result = archive.push(["source"])
    assert result["files"] == 1
    assert not archive.manifest_path.exists()


def test_archive_manifest_is_written_only_after_all_uploads(tmp_path, monkeypatch):
    archive = setup_archive(tmp_path)
    monkeypatch.setenv("R2_BUCKET", "bucket")
    monkeypatch.setattr("strongtowns_detroit.data.archive._client", lambda: Client(fail=True))
    with pytest.raises(RuntimeError, match="upload failed"):
        archive.push(["source"], apply=True)
    assert not archive.manifest_path.exists()


def test_archive_round_trip_verifies_hashes(tmp_path, monkeypatch):
    archive = setup_archive(tmp_path)
    client = Client()
    monkeypatch.setenv("R2_BUCKET", "bucket")
    monkeypatch.setattr("strongtowns_detroit.data.archive._client", lambda: client)
    archive.push(["source"], apply=True)
    source = tmp_path / "data/sources/example/snapshots/one/data.bin"
    source.unlink()
    result = archive.pull(["source"], apply=True)
    assert result["files"] == 1
    assert source.read_bytes() == b"source bytes"


def test_archive_rejects_path_traversal_in_manifest(tmp_path):
    archive = DataArchive(tmp_path, (archived_asset(),))
    archive.manifest_path.parent.mkdir(parents=True)
    archive.manifest_path.write_text(json.dumps({
        "manifest_version": "1.0.0",
        "prefix": PREFIX,
        "entries": {
            f"{PREFIX}/../outside": {
                "path": "../outside",
                "dataset_id": "source.example",
                "tier": "source",
                "size": 1,
                "sha256": "0" * 64,
            }
        },
    }))
    with pytest.raises(ValueError, match="unsafe archive path"):
        archive.pull(["source"])
