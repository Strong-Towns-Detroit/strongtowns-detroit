"""Tests for the Detroit parcel data fetcher."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from strongtowns_detroit.parcels.fetcher import (
    fetch_geojson,
    fetch_csv,
    query_parcels,
    query_to_geojson,
    _hub_download,
    _FEATURE_SERVER,
    _HUB_DOWNLOAD,
)


def _make_hub_response(content, *, content_type="application/geo+json", consumed=False):
    """Helper to build a mock requests.Response for Hub download tests."""
    mock_resp = MagicMock()
    mock_resp.headers = {
        "content-type": content_type,
        "content-length": str(len(content)),
    }
    mock_resp.content = content
    mock_resp._content_consumed = consumed
    mock_resp.iter_content.return_value = [content]
    return mock_resp


def _make_pending_response():
    """Hub response when an export is still being generated."""
    body = b'{"message":"generating","status":"Pending","created":"2026-01-01"}'
    return _make_hub_response(body, content_type="application/json", consumed=True)


# ──────────────────────────────────────────────
# _hub_download (polling + streaming)
# ──────────────────────────────────────────────
class TestHubDownload:
    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    def test_immediate_download(self, mock_get, tmp_path):
        mock_get.return_value = _make_hub_response(b'{"type":"FeatureCollection"}')

        out = tmp_path / "test.geojson"
        result = _hub_download("https://example.com/data", out)

        assert result == out
        assert out.read_bytes() == b'{"type":"FeatureCollection"}'

    @patch("strongtowns_detroit.parcels.fetcher.time.sleep")
    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    def test_polls_then_downloads(self, mock_get, mock_sleep, tmp_path):
        real_data = b"col1,col2\na,b\n"
        mock_get.side_effect = [
            _make_pending_response(),
            _make_pending_response(),
            _make_hub_response(real_data, content_type="text/csv"),
        ]

        out = tmp_path / "data.csv"
        result = _hub_download("https://example.com/csv", out, poll_interval=1)

        assert result == out
        assert out.read_bytes() == real_data
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("strongtowns_detroit.parcels.fetcher.time.sleep")
    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    def test_raises_on_max_polls(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_pending_response()

        with pytest.raises(TimeoutError, match="not ready"):
            _hub_download(
                "https://example.com/data",
                tmp_path / "out",
                max_poll_attempts=3,
                poll_interval=1,
            )

    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    def test_creates_parent_dirs(self, mock_get, tmp_path):
        mock_get.return_value = _make_hub_response(b"data")

        out = tmp_path / "sub" / "dir" / "file.geojson"
        _hub_download("https://example.com/data", out)

        assert out.exists()


# ──────────────────────────────────────────────
# fetch_geojson / fetch_csv
# ──────────────────────────────────────────────
class TestFetchGeojson:
    @patch("strongtowns_detroit.parcels.fetcher._hub_download")
    def test_calls_hub_with_geojson_url(self, mock_dl, tmp_path):
        mock_dl.return_value = tmp_path / "out.geojson"

        fetch_geojson(tmp_path / "out.geojson")

        url = mock_dl.call_args[0][0]
        assert "geojson" in url
        assert _HUB_DOWNLOAD in url


class TestFetchCsv:
    @patch("strongtowns_detroit.parcels.fetcher._hub_download")
    def test_calls_hub_with_csv_url(self, mock_dl, tmp_path):
        mock_dl.return_value = tmp_path / "out.csv"

        fetch_csv(tmp_path / "out.csv")

        url = mock_dl.call_args[0][0]
        assert "csv" in url
        assert _HUB_DOWNLOAD in url


# ──────────────────────────────────────────────
# query_parcels (paginated FeatureServer)
# ──────────────────────────────────────────────
class TestQueryParcels:
    def _make_response(self, features, exceeded=False):
        mock_resp = MagicMock()
        data = {"type": "FeatureCollection", "features": features}
        if exceeded:
            data["exceededTransferLimit"] = True
        mock_resp.json.return_value = data
        return mock_resp

    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    @patch("strongtowns_detroit.parcels.fetcher.time.sleep")
    def test_single_page(self, mock_sleep, mock_get):
        features = [{"type": "Feature", "properties": {"parcel_id": "001"}}]
        mock_get.return_value = self._make_response(features)

        result = query_parcels(where="1=1")

        assert len(result) == 1
        assert result[0]["properties"]["parcel_id"] == "001"

    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    @patch("strongtowns_detroit.parcels.fetcher.time.sleep")
    def test_pagination(self, mock_sleep, mock_get):
        page1 = [{"type": "Feature", "properties": {"id": i}} for i in range(1000)]
        page2 = [{"type": "Feature", "properties": {"id": 1000}}]

        mock_get.side_effect = [
            self._make_response(page1, exceeded=True),
            self._make_response(page2, exceeded=False),
        ]

        result = query_parcels(where="1=1")

        assert len(result) == 1001
        assert mock_get.call_count == 2
        # Check resultOffset was used in second call
        second_call_params = mock_get.call_args_list[1][1]["params"]
        assert second_call_params["resultOffset"] == 1000

    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    @patch("strongtowns_detroit.parcels.fetcher.time.sleep")
    def test_max_records(self, mock_sleep, mock_get):
        page = [{"type": "Feature", "properties": {"id": i}} for i in range(1000)]
        mock_get.return_value = self._make_response(page, exceeded=True)

        result = query_parcels(where="1=1", max_records=500)

        assert len(result) == 500

    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    @patch("strongtowns_detroit.parcels.fetcher.time.sleep")
    def test_empty_response_stops(self, mock_sleep, mock_get):
        mock_get.return_value = self._make_response([])

        result = query_parcels(where="zoning_district='FAKE'")

        assert result == []

    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    @patch("strongtowns_detroit.parcels.fetcher.time.sleep")
    def test_where_clause_passed(self, mock_sleep, mock_get):
        mock_get.return_value = self._make_response([])

        query_parcels(where="zoning_district='R1'")

        params = mock_get.call_args[1]["params"]
        assert params["where"] == "zoning_district='R1'"

    @patch("strongtowns_detroit.parcels.fetcher.requests.get")
    @patch("strongtowns_detroit.parcels.fetcher.time.sleep")
    def test_geometry_toggle(self, mock_sleep, mock_get):
        mock_get.return_value = self._make_response([])

        query_parcels(return_geometry=False)

        params = mock_get.call_args[1]["params"]
        assert params["returnGeometry"] == "false"


# ──────────────────────────────────────────────
# query_to_geojson
# ──────────────────────────────────────────────
class TestQueryToGeojson:
    @patch("strongtowns_detroit.parcels.fetcher.query_parcels")
    def test_writes_geojson_file(self, mock_query, tmp_path):
        mock_query.return_value = [
            {"type": "Feature", "properties": {"parcel_id": "001"}}
        ]

        out = tmp_path / "output.geojson"
        result = query_to_geojson(out, where="1=1")

        assert result == out
        data = json.loads(out.read_text())
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        assert data["name"] == "Parcels"

    @patch("strongtowns_detroit.parcels.fetcher.query_parcels")
    def test_passes_kwargs(self, mock_query, tmp_path):
        mock_query.return_value = []

        query_to_geojson(
            tmp_path / "out.geojson",
            where="zoning_district='R2'",
            max_records=10,
        )

        mock_query.assert_called_once_with(
            where="zoning_district='R2'", max_records=10
        )
