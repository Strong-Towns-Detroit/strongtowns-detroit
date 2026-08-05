from build_parking_by_type_asset import classified_cases, summarize


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
