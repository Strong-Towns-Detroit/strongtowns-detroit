"""Tests for parse_meeting_date() and parse_cases() from create_bza_dataset_from_minutes.py."""
from pathlib import Path
import pytest

from strongtowns_detroit.bza.parser import parse_meeting_date, parse_cases

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_bza_text():
    return (FIXTURES_DIR / "sample_bza_text.txt").read_text()


# ──────────────────────────────────────────────
# parse_meeting_date
# ──────────────────────────────────────────────
class TestParseMeetingDate:
    def test_standard_format(self):
        assert parse_meeting_date("2025-01-14_bza_minutes.pdf") == "2025-01-14"

    def test_no_date_returns_unknown(self):
        assert parse_meeting_date("random_minutes.pdf") == "Unknown"

    def test_date_only(self):
        assert parse_meeting_date("2023-06-20.pdf") == "2023-06-20"


# ──────────────────────────────────────────────
# parse_cases
# ──────────────────────────────────────────────
class TestParseCases:
    def test_finds_all_three_cases(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        assert len(cases) == 3

    def test_case_number_extracted(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        numbers = [c["case_number"] for c in cases]
        assert "01-25" in numbers
        assert "02-25" in numbers
        assert "03-25" in numbers

    def test_petitioner_from_bza_petitioner_label(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        case1 = next(c for c in cases if c["case_number"] == "01-25")
        assert "John Smith" in case1["petitioner"]

    def test_petitioner_from_petitioner_label(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        case2 = next(c for c in cases if c["case_number"] == "02-25")
        assert "Jane Doe" in case2["petitioner"]

    def test_applicant_label_also_works(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        case3 = next(c for c in cases if c["case_number"] == "03-25")
        assert "Robert Johnson" in case3["petitioner"]

    def test_location_extracted(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        case1 = next(c for c in cases if c["case_number"] == "01-25")
        assert "1234 Woodward Ave" in case1["location"]

    def test_granted_decision_detected(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        case1 = next(c for c in cases if c["case_number"] == "01-25")
        assert "GRANTED" in case1["decision"].upper()

    def test_denied_decision_detected(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        case2 = next(c for c in cases if c["case_number"] == "02-25")
        assert "DENIED" in case2["decision"].upper()

    def test_meeting_date_propagated(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        assert all(c["meeting_date"] == "2025-01-14" for c in cases)

    def test_source_file_propagated(self, sample_bza_text):
        cases = parse_cases(sample_bza_text, "2025-01-14", "test.pdf")
        assert all(c["source_file"] == "test.pdf" for c in cases)

    def test_empty_text_returns_no_cases(self):
        cases = parse_cases("", "2025-01-14", "test.pdf")
        assert cases == []

    def test_text_without_case_pattern(self):
        cases = parse_cases("Just some random meeting notes.", "2025-01-14", "test.pdf")
        assert cases == []
