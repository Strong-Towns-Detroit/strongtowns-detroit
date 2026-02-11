"""Tests for check_compliance() — unified function and script wrappers."""
import math
import pandas as pd
import pytest

# Import the unified function directly
from strongtowns_detroit.parcels.compliance import check_compliance as unified_check

# Import the two script wrappers under aliases
from calculate_buildable import (
    check_compliance as cb_check_compliance,
    PROPOSED_MIN_SQFT as CB_PROPOSED_MIN_SQFT,
    PROPOSED_MIN_DWELLING_SQFT as CB_PROPOSED_MIN_DWELLING_SQFT,
    CURRENT_MIN_DWELLING_ASSUMPTION as CB_CURRENT_MIN_DWELLING_ASSUMPTION,
)
from merge_and_calculate import (
    check_compliance as mc_check_compliance,
    PROPOSED_MIN_SQFT as MC_PROPOSED_MIN_SQFT,
    PROPOSED_MIN_DWELLING_SQFT as MC_PROPOSED_MIN_DWELLING_SQFT,
    CURRENT_MIN_DWELLING_ASSUMPTION as MC_CURRENT_MIN_DWELLING_ASSUMPTION,
)


# Shared fixture: zoning restrictions with three districts
@pytest.fixture
def sample_restrictions():
    return {
        "R1": {"MinimumLotSizeInSqft": 4000, "MinimumLotWidthInFt": 40},
        "R2": {"MinimumLotSizeInSqft": 3000, "MinimumLotWidthInFt": 30},
        "B4": {"MinimumLotSizeInSqft": 2000, "MinimumLotWidthInFt": None},
    }


# ──────────────────────────────────────────────
# Constants sanity checks
# ──────────────────────────────────────────────
class TestConstants:
    def test_proposed_min_sqft_matches(self):
        assert CB_PROPOSED_MIN_SQFT == MC_PROPOSED_MIN_SQFT == 1500

    def test_proposed_min_dwelling_matches(self):
        assert CB_PROPOSED_MIN_DWELLING_SQFT == MC_PROPOSED_MIN_DWELLING_SQFT == 500

    def test_current_min_dwelling_matches(self):
        assert CB_CURRENT_MIN_DWELLING_ASSUMPTION == MC_CURRENT_MIN_DWELLING_ASSUMPTION == 1000


# ──────────────────────────────────────────────
# calculate_buildable version
# ──────────────────────────────────────────────
class TestCalculateBuildableCompliance:
    """Tests for check_compliance from calculate_buildable.py.

    This version reads 'zoning_district', 'shape_area', 'frontage', 'total_floor_area'.
    """

    def _make_row(self, **overrides):
        defaults = {
            "zoning_district": "R1",
            "shape_area": 5000,
            "frontage": 50,
            "total_floor_area": 1200,
        }
        defaults.update(overrides)
        return defaults

    def test_fully_compliant_parcel(self, sample_restrictions):
        row = self._make_row()
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_sqft"] is False
        assert result["violates_current_min_width"] is False
        assert result["violates_proposed_min_sqft"] is False
        assert result["violates_proposed_min_dwelling"] is False
        assert result["is_buildable_current_zoning"] is True

    def test_below_proposed_min_sqft(self, sample_restrictions):
        row = self._make_row(shape_area=1000)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_proposed_min_sqft"] is True

    def test_above_proposed_min_sqft(self, sample_restrictions):
        row = self._make_row(shape_area=2000)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_proposed_min_sqft"] is False

    def test_below_current_zoning_min_sqft(self, sample_restrictions):
        """Parcel at 3500 sqft in R1 (min=4000) should violate current."""
        row = self._make_row(shape_area=3500)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_sqft"] is True
        assert result["is_buildable_current_zoning"] is False

    def test_width_violation(self, sample_restrictions):
        """Frontage 35 in R1 (min=40) should violate width."""
        row = self._make_row(frontage=35)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_width"] is True
        assert result["is_buildable_current_zoning"] is False

    def test_no_width_requirement(self, sample_restrictions):
        """B4 has MinimumLotWidthInFt=None, so width should not violate."""
        row = self._make_row(zoning_district="B4", frontage=10)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_width"] is False

    def test_floor_area_below_proposed_dwelling(self, sample_restrictions):
        row = self._make_row(total_floor_area=400)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_proposed_min_dwelling"] is True

    def test_floor_area_below_current_dwelling_assumption(self, sample_restrictions):
        row = self._make_row(total_floor_area=800)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_dwelling_assumption"] is True
        # But should NOT violate proposed (800 > 500)
        assert result["violates_proposed_min_dwelling"] is False

    def test_nan_sqft_no_violation(self, sample_restrictions):
        """NaN/zero area should not trigger violations (guard: sqft > 0)."""
        row = self._make_row(shape_area=0)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_sqft"] is False
        assert result["violates_proposed_min_sqft"] is False

    def test_unknown_district(self, sample_restrictions):
        """Unknown district: no zoning violations, still buildable."""
        row = self._make_row(zoning_district="ZZZZZ")
        result = cb_check_compliance(row, sample_restrictions)
        assert result["zoning_min_sqft"] is None
        assert result["violates_current_min_sqft"] is False
        assert result["is_buildable_current_zoning"] is True

    def test_nan_district(self, sample_restrictions):
        """NaN district: same as unknown."""
        row = self._make_row(zoning_district=float("nan"))
        result = cb_check_compliance(row, sample_restrictions)
        assert result["zoning_min_sqft"] is None
        assert result["is_buildable_current_zoning"] is True

    def test_exact_at_threshold_not_violating(self, sample_restrictions):
        """Exactly at current min (4000 sqft for R1) should NOT violate (uses strict <)."""
        row = self._make_row(shape_area=4000)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_sqft"] is False

    def test_just_below_threshold_violates(self, sample_restrictions):
        """One below current min should violate."""
        row = self._make_row(shape_area=3999)
        result = cb_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_sqft"] is True

    def test_zoning_min_sqft_populated(self, sample_restrictions):
        row = self._make_row(zoning_district="R2")
        result = cb_check_compliance(row, sample_restrictions)
        assert result["zoning_min_sqft"] == 3000
        assert result["zoning_min_width"] == 30


# ──────────────────────────────────────────────
# merge_and_calculate version
# ──────────────────────────────────────────────
class TestMergeAndCalculateCompliance:
    """Tests for check_compliance from merge_and_calculate.py.

    This version reads 'zoning', uses total_square_footage with fallback chain,
    and does NOT check width or set is_buildable_current_zoning.
    """

    def _make_row(self, **overrides):
        defaults = {
            "zoning": "R1",
            "total_square_footage": 5000,
            "total_floor_area": 1200,
        }
        defaults.update(overrides)
        return defaults

    def test_fully_compliant_parcel(self, sample_restrictions):
        row = self._make_row()
        result = mc_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_sqft"] is False
        assert result["violates_proposed_min_sqft"] is False

    def test_below_proposed_min_sqft(self, sample_restrictions):
        row = self._make_row(total_square_footage=1000)
        result = mc_check_compliance(row, sample_restrictions)
        assert result["violates_proposed_min_sqft"] is True

    def test_below_current_zoning_min_sqft(self, sample_restrictions):
        row = self._make_row(total_square_footage=3500)
        result = mc_check_compliance(row, sample_restrictions)
        assert result["violates_current_min_sqft"] is True

    def test_fallback_to_shape_area(self, sample_restrictions):
        """When total_square_footage is 0, should fall back to shape_area."""
        row = self._make_row(total_square_footage=0, shape_area=1000)
        result = mc_check_compliance(row, sample_restrictions)
        assert result["violates_proposed_min_sqft"] is True  # 1000 < 1500

    def test_fallback_nan_to_shape_area(self, sample_restrictions):
        """When total_square_footage is NaN, should fall back to shape_area."""
        row = self._make_row(total_square_footage=float("nan"), shape_area=5000)
        result = mc_check_compliance(row, sample_restrictions)
        assert result["violates_proposed_min_sqft"] is False

    def test_suffixed_column_fallback(self, sample_restrictions):
        """The merge creates suffixed columns; _csv variant takes priority."""
        row = {
            "zoning": "R1",
            "total_square_footage_csv": 5000,
            "total_square_footage_geo": 1000,
            "total_floor_area": 1200,
        }
        result = mc_check_compliance(row, sample_restrictions)
        # Should use _csv value (5000), which is above R1's 4000
        assert result["violates_current_min_sqft"] is False

    def test_no_width_key_in_result(self, sample_restrictions):
        """merge_and_calculate version does not check width."""
        row = self._make_row()
        result = mc_check_compliance(row, sample_restrictions)
        assert "violates_current_min_width" not in result.index

    def test_dwelling_violations(self, sample_restrictions):
        row = self._make_row(total_floor_area=400)
        result = mc_check_compliance(row, sample_restrictions)
        assert result["violates_proposed_min_dwelling"] is True
        assert result["violates_current_min_dwelling_assumption"] is True

    def test_unknown_district(self, sample_restrictions):
        row = self._make_row(zoning="UNKNOWN")
        result = mc_check_compliance(row, sample_restrictions)
        assert result["zoning_min_sqft"] is None
        assert result["violates_current_min_sqft"] is False


# ──────────────────────────────────────────────
# Unified function — parameterized behavior
# ──────────────────────────────────────────────
class TestUnifiedCompliance:
    """Tests for the unified check_compliance with explicit parameter variations."""

    @pytest.fixture
    def restrictions(self):
        return {
            "R1": {"MinimumLotSizeInSqft": 4000, "MinimumLotWidthInFt": 40},
        }

    def test_width_col_none_excludes_width_keys(self, restrictions):
        """When width_col=None, width keys should not appear in result."""
        row = {"zoning_district": "R1", "shape_area": 5000, "total_floor_area": 1200}
        result = unified_check(row, restrictions, width_col=None)
        assert "violates_current_min_width" not in result.index
        assert "zoning_min_width" not in result.index

    def test_width_col_set_includes_width_keys(self, restrictions):
        """When width_col is set, width keys appear."""
        row = {"zoning_district": "R1", "shape_area": 5000, "frontage": 50, "total_floor_area": 1200}
        result = unified_check(row, restrictions, width_col='frontage')
        assert "violates_current_min_width" in result.index
        assert "zoning_min_width" in result.index

    def test_include_buildable_false_excludes_key(self, restrictions):
        """By default, is_buildable_current_zoning is not in output."""
        row = {"zoning_district": "R1", "shape_area": 5000, "total_floor_area": 1200}
        result = unified_check(row, restrictions)
        assert "is_buildable_current_zoning" not in result.index

    def test_include_buildable_true_includes_key(self, restrictions):
        row = {"zoning_district": "R1", "shape_area": 5000, "total_floor_area": 1200}
        result = unified_check(row, restrictions, include_buildable=True)
        assert "is_buildable_current_zoning" in result.index
        assert result["is_buildable_current_zoning"] is True

    def test_area_cols_fallback_chain(self, restrictions):
        """First non-zero column in area_cols wins."""
        row = {"zoning_district": "R1", "col_a": 0, "col_b": float("nan"), "col_c": 1000, "total_floor_area": 1200}
        result = unified_check(row, restrictions, area_cols=('col_a', 'col_b', 'col_c'))
        assert result["violates_proposed_min_sqft"] is True  # 1000 < 1500

    def test_area_cols_first_nonzero_wins(self, restrictions):
        """When first column has a good value, later columns are ignored."""
        row = {"zoning_district": "R1", "col_a": 5000, "col_b": 500, "total_floor_area": 1200}
        result = unified_check(row, restrictions, area_cols=('col_a', 'col_b'))
        assert result["violates_proposed_min_sqft"] is False  # 5000 >= 1500

    def test_custom_district_col(self, restrictions):
        """Supports custom column names for district."""
        row = {"my_zone": "R1", "shape_area": 3000, "total_floor_area": 1200}
        result = unified_check(row, restrictions, district_col='my_zone')
        assert result["violates_current_min_sqft"] is True  # 3000 < 4000
