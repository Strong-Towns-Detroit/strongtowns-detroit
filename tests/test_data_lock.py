import json
import re
from pathlib import Path


def test_published_data_inputs_are_content_addressed():
    lock = json.loads(
        (Path(__file__).parents[1] / "strongtowns-data.lock.json").read_text()
    )

    assert lock["lock_version"] == "1.0.0"
    ids = [item["dataset_id"] for item in lock["assets"]]
    assert len(ids) == len(set(ids))
    assert all(item["snapshot_id"] for item in lock["assets"])
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", item["manifest_sha256"])
        for item in lock["assets"]
    )
