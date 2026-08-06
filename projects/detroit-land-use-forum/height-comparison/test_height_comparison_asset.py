from build_height_comparison_asset import height_cases


def test_height_audit_counts_and_duplicate():
    cases = height_cases()
    valid = cases[
        ~cases["audit_status"].eq("same_project_predecessor")
    ]
    numeric = valid[valid["audit_status"].eq("explicit_pair")]

    assert len(cases) == 18
    assert len(valid) == 17
    assert len(numeric) == 10
    assert valid["audit_status"].eq("not_stated").sum() == 7


def test_height_outcomes():
    cases = height_cases()
    valid = cases[
        ~cases["audit_status"].eq("same_project_predecessor")
    ]

    assert valid["final_outcome"].eq("granted_reversed").sum() == 15
    assert valid["final_outcome"].eq("denied_upheld").sum() == 0
    assert (
        ~valid["final_outcome"].isin(["granted_reversed", "denied_upheld"])
    ).sum() == 2


def test_explicit_height_pairs():
    numeric = height_cases().query("audit_status == 'explicit_pair'")
    assert (numeric["proposed_height_ft"] > numeric["allowed_height_ft"]).all()
    assert round(numeric["excess_share"].median(), 3) == 0.271
