import pandas as pd

from recover_bza_sites_from_base_units import build_recoveries


def test_base_units_secondary_address_recovers_current_parcel():
    candidates = pd.DataFrame([{
        "case_history_id": "case-1", "site_key": "8009:E JEFFERSON",
        "number": 8009, "street": "E JEFFERSON",
    }])
    matched = pd.DataFrame(columns=["case_history_id"])
    base_units = pd.DataFrame([{
        "parcel_id": "17000050.", "street_number": 8009,
        "street_prefix": "E", "street_name": "Jefferson",
        "street_type": "Ave",
    }])
    parcels = pd.DataFrame([{"parcel_id": "17000050."}])
    overrides, audit = build_recoveries(
        candidates, matched, base_units, parcels
    )
    assert len(audit) == 1
    assert overrides.iloc[0]["parcel_id"] == "17000050."


def test_already_matched_history_is_not_recovered_again():
    candidates = pd.DataFrame([{
        "case_history_id": "case-1", "site_key": "1:MAIN",
        "number": 1, "street": "MAIN",
    }])
    matched = pd.DataFrame([{"case_history_id": "case-1"}])
    base_units = pd.DataFrame([{
        "parcel_id": "1.", "street_number": 1, "street_prefix": "",
        "street_name": "Main", "street_type": "St",
    }])
    parcels = pd.DataFrame([{"parcel_id": "1."}])
    overrides, audit = build_recoveries(
        candidates, matched, base_units, parcels
    )
    assert overrides.empty
    assert audit.empty
