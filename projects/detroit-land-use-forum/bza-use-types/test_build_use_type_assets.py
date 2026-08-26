import pandas as pd

from build_use_type_assets import selected_cases


def test_selected_cases_deduplicates_and_groups_insufficient_detail_with_other():
    frame = pd.DataFrame([
        {"case_history_id": "a", "confidence": "high",
         "project_type_family": "housing"},
        {"case_history_id": "a", "confidence": "high",
         "project_type_family": "housing"},
        {"case_history_id": "b", "confidence": "medium",
         "project_type_family": "unclear"},
        {"case_history_id": "c", "confidence": "low",
         "project_type_family": "vehicle_oriented"},
    ])
    result = selected_cases(frame)
    assert result["case_history_id"].tolist() == ["a", "b", "c"]
    assert result["display_family"].tolist() == [
        "housing", "other", "other"
    ]
