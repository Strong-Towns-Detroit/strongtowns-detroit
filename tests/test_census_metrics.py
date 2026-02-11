"""Tests for _calculate_metrics() from detroit_census_fetcher.py."""
import pandas as pd
import pytest

from strongtowns_detroit.census.fetcher import DetroitCensusFetcher


@pytest.fixture
def sample_df():
    """DataFrame with known values for metrics calculation."""
    return pd.DataFrame([{
        "total_renters": 1000,
        "renters_30_35pct": 100,
        "renters_35_40pct": 80,
        "renters_40_50pct": 70,
        "renters_50plus_pct": 200,
        "total_owners": 500,
        "owners_mtg_30_35pct": 30,
        "owners_mtg_35_40pct": 20,
        "owners_mtg_40_50pct": 15,
        "owners_mtg_50plus_pct": 35,
        "owners_nomtg_30_35pct": 10,
        "owners_nomtg_35_40pct": 8,
        "owners_nomtg_40_50pct": 7,
        "owners_nomtg_50plus_pct": 25,
        "median_home_value": 150000,
        "median_household_income": 40000,
    }])


@pytest.fixture
def fetcher(mocker):
    """Create a fetcher with mocked Census API setup."""
    mocker.patch("strongtowns_detroit.census.fetcher.tc.set_census_api_key")
    return DetroitCensusFetcher(api_key="fake_key")


class TestCalculateMetrics:
    def test_renter_burden_30plus(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # 100 + 80 + 70 + 200 = 450
        assert sample_df["renters_burden_30plus"].iloc[0] == 450

    def test_pct_renters_30plus(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # 450 / 1000 * 100 = 45.0
        assert sample_df["pct_renters_30plus"].iloc[0] == 45.0

    def test_owner_burden_30plus(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # mtg: 30+20+15+35 = 100, nomtg: 10+8+7+25 = 50 => 150
        assert sample_df["owners_burden_30plus"].iloc[0] == 150

    def test_pct_owners_30plus(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # 150 / 500 * 100 = 30.0
        assert sample_df["pct_owners_30plus"].iloc[0] == 30.0

    def test_combined_burden(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # total_households = 1000 + 500 = 1500
        # burden_30plus_all = 450 + 150 = 600
        # pct = 600 / 1500 * 100 = 40.0
        assert sample_df["total_households"].iloc[0] == 1500
        assert sample_df["burden_30plus_all"].iloc[0] == 600
        assert sample_df["pct_burden_30plus_all"].iloc[0] == 40.0

    def test_severe_burden_50plus(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # renters_50plus = 200, owners_50plus = 35 + 25 = 60
        assert sample_df["renters_burden_50plus"].iloc[0] == 200
        assert sample_df["owners_burden_50plus"].iloc[0] == 60
        assert sample_df["burden_50plus_all"].iloc[0] == 260

    def test_price_income_ratio(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # 150000 / 40000 = 3.75
        assert sample_df["price_income_ratio"].iloc[0] == 3.75

    def test_housing_shortage_flag(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # ratio > 3 => True
        assert bool(sample_df["housing_shortage"].iloc[0]) is True

    def test_renter_accessibility_crisis(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # pct_renters_30plus = 45.0, which is NOT > 50
        assert bool(sample_df["renter_accessibility_crisis"].iloc[0]) is False

    def test_housing_category_shortage_only(self, fetcher, sample_df):
        fetcher._calculate_metrics(sample_df)
        # housing_shortage=True, renter_accessibility_crisis=False => 'Shortage Only'
        assert sample_df["housing_category"].iloc[0] == "Shortage Only"

    def test_housing_category_both_issues(self, fetcher):
        """When both shortage and accessibility crisis are true."""
        df = pd.DataFrame([{
            "total_renters": 100,
            "renters_30_35pct": 20,
            "renters_35_40pct": 10,
            "renters_40_50pct": 10,
            "renters_50plus_pct": 20,
            "total_owners": 50,
            "owners_mtg_30_35pct": 5,
            "owners_mtg_35_40pct": 3,
            "owners_mtg_40_50pct": 2,
            "owners_mtg_50plus_pct": 5,
            "owners_nomtg_30_35pct": 2,
            "owners_nomtg_35_40pct": 1,
            "owners_nomtg_40_50pct": 1,
            "owners_nomtg_50plus_pct": 3,
            "median_home_value": 200000,
            "median_household_income": 30000,
        }])
        fetcher._calculate_metrics(df)
        # renters 30+ = 60/100 = 60% > 50 => crisis
        # ratio = 200000/30000 = 6.67 > 3 => shortage
        assert df["housing_category"].iloc[0] == "Both Issues"
