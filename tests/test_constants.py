"""Tests for strongtowns_detroit.constants — cross-checks against source files."""

from strongtowns_detroit.constants import (
    PROPOSED_MIN_SQFT,
    PROPOSED_MIN_DWELLING_SQFT,
    CURRENT_MIN_DWELLING_ASSUMPTION,
    RESIDENTIAL_ZONES,
    TARGET_KEYS,
    DUPLEX_KEYS,
    MULTI_FAMILY_KEYS,
    ADU_KEYS,
)
from calculate_buildable import (
    PROPOSED_MIN_SQFT as CB_PROPOSED_MIN_SQFT,
    PROPOSED_MIN_DWELLING_SQFT as CB_PROPOSED_MIN_DWELLING_SQFT,
    CURRENT_MIN_DWELLING_ASSUMPTION as CB_CURRENT_MIN_DWELLING_ASSUMPTION,
)
from merge_and_calculate import (
    PROPOSED_MIN_SQFT as MC_PROPOSED_MIN_SQFT,
    PROPOSED_MIN_DWELLING_SQFT as MC_PROPOSED_MIN_DWELLING_SQFT,
    CURRENT_MIN_DWELLING_ASSUMPTION as MC_CURRENT_MIN_DWELLING_ASSUMPTION,
)


class TestConstantsCrossCheck:
    """Verify centralized constants match the values in both script files."""

    def test_proposed_min_sqft(self):
        assert PROPOSED_MIN_SQFT == CB_PROPOSED_MIN_SQFT == MC_PROPOSED_MIN_SQFT == 1500

    def test_proposed_min_dwelling(self):
        assert PROPOSED_MIN_DWELLING_SQFT == CB_PROPOSED_MIN_DWELLING_SQFT == MC_PROPOSED_MIN_DWELLING_SQFT == 500

    def test_current_min_dwelling(self):
        assert CURRENT_MIN_DWELLING_ASSUMPTION == CB_CURRENT_MIN_DWELLING_ASSUMPTION == MC_CURRENT_MIN_DWELLING_ASSUMPTION == 1000


class TestResidentialZones:
    def test_contains_expected_zones(self):
        assert set(RESIDENTIAL_ZONES) == {'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'SD1', 'SD2'}

    def test_order_preserved(self):
        assert RESIDENTIAL_ZONES[0] == 'R1'
        assert RESIDENTIAL_ZONES[-1] == 'SD2'


class TestUseCodeKeys:
    def test_duplex_keys_subset_of_target(self):
        assert all(k in TARGET_KEYS for k in DUPLEX_KEYS)

    def test_multi_family_keys_subset_of_target(self):
        assert all(k in TARGET_KEYS for k in MULTI_FAMILY_KEYS)

    def test_adu_keys_subset_of_target(self):
        assert all(k in TARGET_KEYS for k in ADU_KEYS)

    def test_no_overlap_between_groups(self):
        assert not set(DUPLEX_KEYS) & set(MULTI_FAMILY_KEYS)
        assert not set(DUPLEX_KEYS) & set(ADU_KEYS)
        assert not set(MULTI_FAMILY_KEYS) & set(ADU_KEYS)
