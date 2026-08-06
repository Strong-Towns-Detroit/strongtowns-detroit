from classify_bza_relief import RELIEF_RULES, classify, normalize_text


def labels(text: str) -> list[str]:
    return classify(normalize_text(text), RELIEF_RULES)[0]


def test_boilerplate_minimum_setbacks_is_not_a_setback_request():
    text = (
        "The Board shall be authorized to hear dimensional variance requests "
        "for matters beyond the scope of BSEED's 10% administrative adjustments "
        "for a variance of the minimum setbacks. Deficient parking."
    )
    assert "setbacks_yards" not in labels(text)
    assert "parking_supply" in labels(text)


def test_short_distance_is_not_automatically_use_spacing():
    assert "use_spacing_separation" not in labels(
        "The screening wall is located within 20 feet of the building."
    )


def test_radial_spacing_is_classified():
    assert "use_spacing_separation" in labels(
        "A spacing variance is required because the use is within 1,000 radial feet."
    )


def test_case_can_have_multiple_relief_categories():
    result = labels(
        "Deficient front setback, excessive lot coverage, and deficient parking."
    )
    assert {"setbacks_yards", "lot_coverage", "parking_supply"}.issubset(result)
