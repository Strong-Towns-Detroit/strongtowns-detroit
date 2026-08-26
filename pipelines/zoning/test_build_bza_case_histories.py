import pandas as pd

from build_bza_case_histories import build_histories, make_history_id


def row(occurrence_id, case_number, date, location="100 Main", category="parking_supply"):
    return {
        "occurrence_id": occurrence_id,
        "case_number": case_number,
        "meeting_date": date,
        "record_type": "minutes_case",
        "petitioner": "Petitioner",
        "location": location,
        "proposal": "Deficient parking",
        "relief_categories": category,
        "case_routes": "dimensional_variance",
        "classification_source": "direct",
        "relief_evidence": '{"parking_supply":["deficient parking"]}',
        "decision_status": "decided",
        "decision": "GRANTED",
        "decision_basis": "printed",
        "source_file": f"{date}.pdf",
    }


def test_repeated_occurrences_collapse_to_one_history():
    frame = pd.DataFrame([
        row("2020-01-01:1-20:1", "1-20", "2020-01-01"),
        row("2020-02-01:1-20:1", "1-20", "2020-02-01"),
    ])
    histories, occurrences, categories, audit = build_histories(
        frame, pd.DataFrame(columns=["occurrence_id", "history_discriminator"])
    )
    assert len(histories) == 1
    assert histories.iloc[0].appearance_count == 2
    assert len(occurrences) == 2
    assert len(categories) == 1
    assert audit["collapsed_occurrences"] == 1


def test_duplicate_printed_number_can_be_split_by_override():
    frame = pd.DataFrame([
        row("2019-11-26:76-19:1", "76-19", "2019-11-26", "6001 Cass"),
        row("2019-11-26:76-19:2", "76-19", "2019-11-26", "10345 W Eight Mile"),
    ])
    overrides = pd.DataFrame([
        {"occurrence_id": "2019-11-26:76-19:1", "history_discriminator": "cass"},
        {"occurrence_id": "2019-11-26:76-19:2", "history_discriminator": "eight-mile"},
    ])
    histories, _, _, audit = build_histories(frame, overrides)
    assert len(histories) == 2
    assert audit["unresolved_same_date_number_collisions"] == []


def test_history_id_is_stable():
    assert make_history_id(" 76-19 ", "cass") == make_history_id("76/19", "cass")


def test_case_review_replaces_unspecified_with_detailed_categories():
    frame = pd.DataFrame([
        row(
            "2020-01-01:1-20:1", "1-20", "2020-01-01",
            category="dimensional_relief_unspecified",
        )
    ])
    reviews = pd.DataFrame([{
        "case_history_id": make_history_id("1-20"),
        "printed_case_number": "1-20",
        "review_status": "classified",
        "categories": "parking_supply|setbacks_yards",
        "evidence": "Four spaces deficient; rear setback deficient",
    }])

    histories, _, categories, audit = build_histories(
        frame,
        pd.DataFrame(columns=["occurrence_id", "history_discriminator"]),
        reviews,
    )

    assert histories.iloc[0].relief_categories == "parking_supply|setbacks_yards"
    assert set(categories["category"]) == {"parking_supply", "setbacks_yards"}
    assert set(categories["classification_sources"]) == {"manual_case_review"}
    assert audit["relief_case_reviews"]["classified_histories"] == 1


def test_unresolved_case_review_preserves_unspecified_category():
    frame = pd.DataFrame([
        row(
            "2020-01-01:1-20:1", "1-20", "2020-01-01",
            category="dimensional_relief_unspecified",
        )
    ])
    reviews = pd.DataFrame([{
        "case_history_id": make_history_id("1-20"),
        "printed_case_number": "1-20",
        "review_status": "unresolved",
        "categories": "",
        "evidence": "The requested dimension is absent",
    }])

    histories, _, categories, audit = build_histories(
        frame,
        pd.DataFrame(columns=["occurrence_id", "history_discriminator"]),
        reviews,
    )

    assert histories.iloc[0].relief_categories == "dimensional_relief_unspecified"
    assert categories.iloc[0].category == "dimensional_relief_unspecified"
    assert audit["relief_case_reviews"]["unresolved_histories"] == 1
