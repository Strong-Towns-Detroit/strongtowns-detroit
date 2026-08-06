import pandas as pd

from normalize_bza_outcomes import normalize_occurrence


def outcome(decision_status, decision):
    return normalize_occurrence(
        pd.Series({"decision_status": decision_status, "decision": decision})
    )[0]


def test_grant_and_reverse_are_positive():
    assert outcome("decided", "DIMENSIONAL VARIANCE GRANTED") == "granted_reversed"
    assert outcome("decided", "BSEED DENIAL REVERSED, USE GRANTED") == "granted_reversed"


def test_upheld_denial_is_negative():
    assert outcome("decided", "BSEED DENIAL UPHELD, USE DENIED") == "denied_upheld"


def test_procedural_and_dismissed_are_separate():
    assert outcome("postponed", "ADJOURNED WITHOUT DATE") == "procedural_unresolved"
    assert outcome("dismissed", "CASE DISMISSED") == "dismissed_withdrawn"


def test_conflicting_terms_are_not_forced():
    assert (
        outcome("decided", "BSEED DECISION REVERSED, USE DENIED")
        == "mixed_or_other_decided"
    )


def test_rehearing_and_standing_language():
    assert outcome("decided", "CASE BEING REHEARD DUE TO NEW INFORMATION") == (
        "procedural_unresolved"
    )
    assert outcome("decided", "AGGRIEVED PERSON STANDARD NOT MET") == "denied_upheld"


def test_overturned_denial_is_positive():
    assert outcome("decided", "BSEED DENIAL OVERTURNED WITH CONDITIONS") == (
        "granted_reversed"
    )
