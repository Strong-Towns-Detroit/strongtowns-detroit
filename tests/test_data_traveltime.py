from __future__ import annotations

from datetime import datetime, timezone

import geopandas as gpd
import pytest
import requests
from shapely.geometry import Point

from strongtowns_detroit.data.traveltime import (
    TravelTimeBatchError,
    build_request_ledger,
    execute_request_ledger,
)


def anchors():
    return gpd.GeoDataFrame(
        {
            "anchor_id": ["a", "b", "c"],
            "parcel_id": ["1", "2", "3"],
            "review_status": ["not_required", "required", "rejected"],
        },
        geometry=[Point(-83, 42), Point(-83.1, 42.1), Point(-83.2, 42.2)],
        crs="EPSG:4326",
    )


def ledger(include_required=False):
    return build_request_ledger(
        anchors(), directions=("arrival", "departure"), mode="walking",
        horizon_seconds=3600,
        reference_time=datetime(2026, 8, 26, 16, tzinfo=timezone.utc),
        include_required=include_required,
    )


def test_request_ledger_is_deterministic_and_records_required_override():
    first, blocked = ledger()
    second, _ = ledger()
    assert list(first.request_id) == list(second.request_id)
    assert len(first) == 2
    assert set(blocked.review_status) == {"required", "rejected"}
    included, _ = ledger(include_required=True)
    assert len(included) == 4
    assert included.required_override.sum() == 2
    assert "c" not in set(included.anchor_id)


class Response:
    def __init__(self, search_id=None, *, status=200, malformed=False):
        self.status_code = status
        self.headers = {}
        self.text = "bad" if malformed else ""
        self.search_id = search_id
        self.malformed = malformed

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        if self.malformed:
            raise ValueError("bad JSON")
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"search_id": self.search_id},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-83, 42], [-83, 42.01], [-82.99, 42.01], [-83, 42]]],
                },
            }],
        }


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_traveltime_success_reconciles_every_request_and_keeps_secrets_out_of_raw(tmp_path):
    requests_frame, _ = ledger()
    session = Session([Response(value) for value in requests_frame.provider_search_id])
    run = execute_request_ledger(
        requests_frame, tmp_path, app_id="secret-app", api_key="secret-key", session=session
    )
    assert set(run.results.request_id) == set(requests_frame.request_id)
    assert not len(run.errors)
    raw = "".join(path.read_text() for path in tmp_path.glob("*.json"))
    assert "secret-app" not in raw and "secret-key" not in raw


def test_traveltime_retries_rate_limit_and_honors_success(tmp_path, monkeypatch):
    frame, _ = build_request_ledger(
        anchors().iloc[:1], directions=("departure",), mode="walking",
        horizon_seconds=3600,
        reference_time=datetime(2026, 8, 26, 16, tzinfo=timezone.utc),
    )
    session = Session([Response(status=429), Response(frame.iloc[0].provider_search_id)])
    monkeypatch.setattr("strongtowns_detroit.data.traveltime.time.sleep", lambda _: None)
    run = execute_request_ledger(frame, tmp_path, app_id="a", api_key="k", session=session)
    assert run.retries == 1


def test_traveltime_rejects_unexpected_provider_id(tmp_path):
    frame, _ = build_request_ledger(
        anchors().iloc[:1], directions=("departure",), mode="walking",
        horizon_seconds=3600,
        reference_time=datetime(2026, 8, 26, 16, tzinfo=timezone.utc),
    )
    with pytest.raises(TravelTimeBatchError, match="unexpected provider search ID"):
        execute_request_ledger(
            frame, tmp_path, app_id="a", api_key="k", session=Session([Response("wrong")])
        )


def test_traveltime_malformed_response_never_promotes(tmp_path):
    frame, _ = build_request_ledger(
        anchors().iloc[:1], directions=("departure",), mode="walking",
        horizon_seconds=3600,
        reference_time=datetime(2026, 8, 26, 16, tzinfo=timezone.utc),
    )
    with pytest.raises(TravelTimeBatchError, match="malformed"):
        execute_request_ledger(
            frame, tmp_path, app_id="a", api_key="k",
            session=Session([Response(malformed=True)]),
        )
