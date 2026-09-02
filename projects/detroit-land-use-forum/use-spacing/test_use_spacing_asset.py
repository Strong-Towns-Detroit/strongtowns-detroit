import pytest

from build_use_spacing_asset import (
    DATA,
    FALSE_POSITIVES,
    SPACING_VALUES,
    final_outcome,
    spacing_cases,
)

pytestmark = pytest.mark.skipif(
    not (DATA / "case_histories.csv").is_file(),
    reason="reviewed BZA data must be materialized in strongtowns-data",
)


def test_spacing_audit_counts():
    cases = spacing_cases()
    valid = cases[~cases["audit_status"].eq("not_spacing_case")]
    numeric = valid[valid["audit_status"].eq("explicit_pair")].copy()

    assert len(cases) == 52
    assert len(FALSE_POSITIVES) == 1
    assert len(valid) == 51
    assert len(numeric) == len(SPACING_VALUES) == 37
    assert valid["audit_status"].eq("not_stated").sum() == 14
    assert (numeric["actual_distance_ft"] < numeric["required_distance_ft"]).all()


def test_spacing_outcomes_and_medians():
    cases = spacing_cases()
    numeric = cases[cases["audit_status"].eq("explicit_pair")].copy()
    numeric["outcome_label"] = numeric["final_outcome"].map(final_outcome)

    assert numeric["outcome_label"].value_counts().to_dict() == {
        "Denied": 22,
        "Granted": 12,
        "Other": 3,
    }
    assert round(
        numeric.loc[
            numeric["outcome_label"].eq("Granted"), "distance_share"
        ].median(),
        3,
    ) == 0.421
    assert round(
        numeric.loc[
            numeric["outcome_label"].eq("Denied"), "distance_share"
        ].median(),
        4,
    ) == 0.5695
