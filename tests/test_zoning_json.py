"""Tests for parse_zoning_csv() from build_use_code.py."""
from pathlib import Path
import pytest

from strongtowns_detroit.parcels.zoning_json import parse_zoning_csv

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_CSV = str(FIXTURES_DIR / "sample_zoning_csv.csv")


class TestParseZoningCsv:
    def test_returns_three_tuple(self):
        result, use_categories, specific_uses = parse_zoning_csv(SAMPLE_CSV)
        assert isinstance(result, dict)
        assert isinstance(use_categories, list)
        assert isinstance(specific_uses, list)

    def test_categories_found(self):
        result, use_categories, _ = parse_zoning_csv(SAMPLE_CSV)
        assert "Residential" in use_categories
        assert "Commercial" in use_categories

    def test_contd_suffix_stripped(self):
        """'Residential (cont'd)' should merge into 'Residential'."""
        result, use_categories, _ = parse_zoning_csv(SAMPLE_CSV)
        # Should NOT have a separate "Residential (cont'd)" key
        assert "Residential (cont'd)" not in result
        # Live/work unit (from the cont'd section) should be under Residential
        assert "Live/work unit" in result["Residential"]

    def test_by_right_permission(self):
        result, _, _ = parse_zoning_csv(SAMPLE_CSV)
        sf_dwelling = result["Residential"]["Single-family detached dwelling"]
        assert "by_right" in sf_dwelling
        assert "R1" in sf_dwelling["by_right"]
        assert "R6" in sf_dwelling["by_right"]

    def test_conditional_permission(self):
        result, _, _ = parse_zoning_csv(SAMPLE_CSV)
        townhouse = result["Residential"]["Townhouse/rowhouse"]
        assert "conditional" in townhouse
        assert "R3" in townhouse["conditional"]
        assert "by_right" in townhouse
        assert "R4" in townhouse["by_right"]

    def test_mixed_permission_c_r(self):
        """C/R should map to 'by_right_subject_to_conditions'."""
        result, _, _ = parse_zoning_csv(SAMPLE_CSV)
        live_work = result["Residential"]["Live/work unit"]
        assert "by_right_subject_to_conditions" in live_work
        assert "R4" in live_work["by_right_subject_to_conditions"]

    def test_empty_permissions_excluded(self):
        """Uses with no R/C entries in any district should not appear."""
        result, _, _ = parse_zoning_csv(SAMPLE_CSV)
        # All entries in the fixture have at least one permission
        for category in result.values():
            for use, perms in category.items():
                assert len(perms) > 0

    def test_specific_uses_list(self):
        _, _, specific_uses = parse_zoning_csv(SAMPLE_CSV)
        assert "Single-family detached dwelling" in specific_uses
        assert "Restaurant" in specific_uses
