import io
import json
from unittest.mock import patch

from enrich_bza_intake_dates import (
    normalized_case_number,
    request_records,
    score_candidate,
)


def test_normalized_case_number():
    assert normalized_case_number("BZA 5-2019") == "5-19"
    assert normalized_case_number("05/19") == "5-19"


def test_strong_candidate_requires_more_than_address():
    record = {
        "customId": "PLN-123",
        "description": "Board of Zoning Appeals case 5-19",
        "type": {"value": "Planning/Zoning/Board of Zoning Appeals/NA"},
        "addresses": [{
            "streetStart": 7250,
            "streetName": "Mack",
            "streetSuffix": {"text": "Avenue"},
            "streetAddress": "7250 Mack Avenue",
        }],
    }
    scored = score_candidate("5-19", 7250, "MACK", record)
    assert scored["address_score"] == 80
    assert scored["case_number_score"] == 15
    assert scored["record_type_score"] == 20
    assert scored["suggested_disposition"] == "strong_candidate"


def test_address_only_is_held_for_review():
    record = {
        "customId": "PLN-123",
        "type": {"value": "Planning/Site Plan Review/NA/NA"},
        "addresses": [{
            "streetStart": 7250,
            "streetName": "Mack",
            "streetAddress": "7250 Mack",
        }],
    }
    scored = score_candidate("5-19", 7250, "MACK", record)
    assert scored["total_score"] == 80
    assert scored["suggested_disposition"] == "review"


def test_anonymous_request_has_required_accela_headers():
    response = io.BytesIO(json.dumps({"status": 200, "result": []}).encode())
    response.__enter__ = lambda value: value
    response.__exit__ = lambda *args: None
    with patch("urllib.request.urlopen", return_value=response) as opened:
        request_records(
            "https://example.test/v4/search/records",
            {"module": "Planning"},
            token="",
            app_id="citizen-app",
            agency="DETROIT",
            environment="PROD",
            limit=10,
        )
    request = opened.call_args.args[0]
    assert request.get_header("X-accela-appid") == "citizen-app"
    assert request.get_header("X-accela-agency") == "DETROIT"
    assert request.get_header("X-accela-environment") == "PROD"
    assert request.get_header("Authorization") is None
