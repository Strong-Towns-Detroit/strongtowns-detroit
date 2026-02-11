"""Tests for is_vacant() and preemption mask logic from analyze_preemption.py."""
import math
import pandas as pd
import pytest

from strongtowns_detroit.parcels.preemption import is_vacant


class TestIsVacant:
    def test_nan_is_vacant(self):
        assert is_vacant(float("nan")) is True

    def test_none_is_vacant(self):
        assert is_vacant(None) is True

    def test_vacant_keyword(self):
        assert is_vacant("VACANT LAND") is True

    def test_no_bldg_keyword(self):
        assert is_vacant("NO BLDG ON SITE") is True

    def test_improved_no_bldg(self):
        assert is_vacant("IMPROVED NO BLDG") is True

    def test_single_family_not_vacant(self):
        assert is_vacant("SINGLE FAMILY") is False

    def test_case_insensitive(self):
        assert is_vacant("vacant lot") is True
        assert is_vacant("Vacant Land") is True

    def test_duplex_not_vacant(self):
        assert is_vacant("DUPLEX") is False


class TestPreemptionMask:
    """Test the lot_size_saved_by_preemption logic as used in analyze_preemption."""

    def test_saved_by_preemption(self):
        """Parcel violates current but NOT proposed => saved."""
        df = pd.DataFrame({
            "violates_current_min_sqft": [True],
            "violates_proposed_min_sqft": [False],
        })
        mask = df["violates_current_min_sqft"] & ~df["violates_proposed_min_sqft"]
        assert bool(mask.iloc[0]) is True

    def test_not_saved_still_too_small(self):
        """Parcel violates both current AND proposed => not saved."""
        df = pd.DataFrame({
            "violates_current_min_sqft": [True],
            "violates_proposed_min_sqft": [True],
        })
        mask = df["violates_current_min_sqft"] & ~df["violates_proposed_min_sqft"]
        assert bool(mask.iloc[0]) is False

    def test_already_compliant(self):
        """Parcel doesn't violate current => not 'saved'."""
        df = pd.DataFrame({
            "violates_current_min_sqft": [False],
            "violates_proposed_min_sqft": [False],
        })
        mask = df["violates_current_min_sqft"] & ~df["violates_proposed_min_sqft"]
        assert bool(mask.iloc[0]) is False

    def test_bulk_mask(self):
        """Multiple rows with mixed results."""
        df = pd.DataFrame({
            "violates_current_min_sqft": [True, True, False, False],
            "violates_proposed_min_sqft": [False, True, False, True],
        })
        mask = df["violates_current_min_sqft"] & ~df["violates_proposed_min_sqft"]
        assert mask.tolist() == [True, False, False, False]
