import pytest

from build_parking_by_type_asset import PARKING_AUDIT, build_svg, classified_cases, summarize

pytestmark = pytest.mark.skipif(
    not PARKING_AUDIT.is_file(),
    reason="generated parking audit must be materialized for these integration tests",
)


def test_all_parking_histories_have_one_type():
    cases = classified_cases()
    assert len(cases) == 62
    assert cases["project_type"].notna().all()
    assert cases["case_history_id"].is_unique
    assert cases["project_type"].nunique() == 6


def test_project_type_numeric_totals_reconcile():
    cases = classified_cases()
    summary = summarize(cases)

    assert summary["histories"].sum() == 62
    assert summary["numeric_histories"].sum() == 35
    assert summary["required"].sum() == 1741
    assert summary["proposed"].sum() == 666
    assert summary["gap"].sum() == 1075


def test_selected_category_results():
    summary = summarize(classified_cases()).set_index("project_type")
    community = summary.loc["Community & institutional"]
    gathering = summary.loc["Food, drink & gathering"]

    assert community["histories"] == 11
    assert community["gap"] == 461
    assert gathering["histories"] == 20
    assert round(gathering["median_gap_share"], 3) == 0.847


def test_chart_uses_a_horizontal_axis_and_inline_comparisons():
    cases = classified_cases()
    svg = build_svg(cases, summarize(cases))

    assert "TOTAL PARKING SPACES" in svg
    assert ">0</text>" in svg
    assert ">800</text>" in svg
    assert "Developers consistently propose far fewer" in svg
    assert "parking spaces than the law requires." in svg
    assert 'class="graphic-title"' in svg
    assert "Of 62 parking-related BZA cases" not in svg
    assert "91 spaces proposed · 405 required by law" in svg
    assert "cases reported counts" not in svg
    assert ">PROPOSED</text>" not in svg
    assert ">REQUIRED</text>" not in svg
