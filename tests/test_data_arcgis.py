from __future__ import annotations

import json

import pytest

from strongtowns_detroit.data.arcgis import collect_layer


class Response:
    def __init__(self, payload, content_type="application/json"):
        self.payload = payload
        self.headers = {"content-type": content_type}
        self.text = json.dumps(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def request(self, method, url, **kwargs):
        assert self.payloads, f"unexpected request: {method} {url}"
        return Response(self.payloads.pop(0))


def metadata(last_edit=10):
    return {
        "objectIdField": "objectid",
        "geometryType": "esriGeometryPoint",
        "extent": {"spatialReference": {"wkid": 4326}},
        "editingInfo": {"lastEditDate": last_edit},
        "fields": [
            {"name": "objectid", "type": "esriFieldTypeOID", "nullable": False}
        ],
    }


def ids(values=(1, 2)):
    return {"objectIds": list(values)}


def features(values=(1, 2)):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"objectid": value},
                "geometry": {"type": "Point", "coordinates": [-83, 42]},
            }
            for value in values
        ],
    }


def test_arcgis_collection_reconciles_ids_and_fingerprints(tmp_path):
    session = Session([metadata(), ids(), features(), metadata(), ids()])
    output = tmp_path / "raw.geojson"
    result = collect_layer(
        "https://example.test/FeatureServer/0",
        output,
        session=session,
        cache_root=tmp_path / "cache",
    )
    assert result.feature_count == 2
    assert len(json.loads(output.read_text())["features"]) == 2


def test_arcgis_collection_rejects_source_changed_mid_download(tmp_path):
    session = Session([metadata(10), ids(), features(), metadata(11), ids()])
    with pytest.raises(ValueError, match="changed during collection"):
        collect_layer(
            "https://example.test/FeatureServer/0",
            tmp_path / "raw.geojson",
            session=session,
            cache_root=tmp_path / "cache",
        )


def test_arcgis_collection_rejects_different_returned_ids(tmp_path):
    session = Session([metadata(), ids(), features((1, 3))])
    with pytest.raises(ValueError, match="different from requested"):
        collect_layer(
            "https://example.test/FeatureServer/0",
            tmp_path / "raw.geojson",
            session=session,
            cache_root=tmp_path / "cache",
        )


def test_arcgis_cache_is_scoped_to_source_fingerprint(tmp_path):
    first = Session([metadata(10), ids(), features(), metadata(10), ids()])
    second = Session([metadata(11), ids(), features(), metadata(11), ids()])
    collect_layer("https://example.test/0", tmp_path / "one.json", session=first, cache_root=tmp_path / "cache")
    collect_layer("https://example.test/0", tmp_path / "two.json", session=second, cache_root=tmp_path / "cache")
    assert len([item for item in (tmp_path / "cache").iterdir() if item.is_dir()]) == 2


def test_arcgis_rejects_non_json_content_type(tmp_path):
    class HtmlSession:
        def request(self, method, url, **kwargs):
            return Response(metadata(), "text/html")

    with pytest.raises(ValueError, match="non-JSON content type"):
        collect_layer(
            "https://example.test/0", tmp_path / "raw.geojson",
            session=HtmlSession(), cache_root=tmp_path / "cache",
        )


def test_arcgis_cache_includes_query_parameters(tmp_path):
    first = Session([metadata(), ids(), features(), metadata(), ids()])
    second = Session([metadata(), ids(), features(), metadata(), ids()])
    collect_layer(
        "https://example.test/0", tmp_path / "one.json", session=first,
        cache_root=tmp_path / "cache", out_fields="objectid",
    )
    collect_layer(
        "https://example.test/0", tmp_path / "two.json", session=second,
        cache_root=tmp_path / "cache", out_fields="*",
    )
    assert len([item for item in (tmp_path / "cache").iterdir() if item.is_dir()]) == 2
