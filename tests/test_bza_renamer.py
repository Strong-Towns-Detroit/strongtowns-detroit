"""Tests for parse_date() and convert_to_date() from rename_bza_minutes.py."""
import datetime
import pytest

from strongtowns_detroit.bza.renamer import parse_date, convert_to_date


class TestConvertToDate:
    """Tests for convert_to_date(month, day, year)."""

    def test_numeric_month(self):
        assert convert_to_date("8", "30", "2021") == datetime.date(2021, 8, 30)

    def test_full_month_name(self):
        assert convert_to_date("august", "30", "2021") == datetime.date(2021, 8, 30)

    def test_abbreviated_month(self):
        assert convert_to_date("sep", "15", "2020") == datetime.date(2020, 9, 15)

    def test_sept_abbreviation(self):
        assert convert_to_date("sept", "15", "2020") == datetime.date(2020, 9, 15)

    def test_invalid_day_returns_none(self):
        assert convert_to_date("2", "31", "2021") is None  # Feb 31 doesn't exist

    def test_invalid_month_string_returns_none(self):
        assert convert_to_date("notamonth", "15", "2021") is None


class TestParseDate:
    """Tests for parse_date(filename)."""

    # Pattern 1: Month_DD__YYYY
    def test_month_word_double_underscore(self):
        result = parse_date("AUGUST_30__2021.pdf")
        assert result == datetime.date(2021, 8, 30)

    def test_month_word_with_prefix(self):
        result = parse_date("Minutes-April_13__2021.pdf")
        assert result == datetime.date(2021, 4, 13)

    def test_month_abbreviation_in_filename(self):
        result = parse_date("Sept_15__2020.pdf")
        assert result == datetime.date(2020, 9, 15)

    # Pattern 2: MM-DD-YYYY
    def test_numeric_dash_format(self):
        result = parse_date("2-25-2020.pdf")
        assert result == datetime.date(2020, 2, 25)

    def test_numeric_underscore_format(self):
        result = parse_date("Minutes_10_8_2019.pdf")
        assert result == datetime.date(2019, 10, 8)

    # Pattern 3: 8-digit MMDDYYYY
    def test_eight_digit(self):
        result = parse_date("minutes12172019.pdf")
        assert result == datetime.date(2019, 12, 17)

    # Pattern 4: 7-digit (M-DD-YYYY)
    def test_seven_digit(self):
        result = parse_date("minutes_1232019.pdf")
        assert result == datetime.date(2019, 1, 23)

    # Edge cases
    def test_no_date_returns_none(self):
        result = parse_date("random_file.pdf")
        assert result is None

    def test_just_extension(self):
        result = parse_date(".pdf")
        assert result is None

    def test_case_insensitive(self):
        result = parse_date("JANUARY_1__2022.pdf")
        assert result == datetime.date(2022, 1, 1)
