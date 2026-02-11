"""Tests for ZoningMapper pure methods from zoning_use_mapper.py."""
import pandas as pd
import pytest


class TestExtractSpecificUses:
    def test_basic_extraction(self):
        # Import here to avoid triggering SentenceTransformer load at module level
        # We'll test the static logic without needing the model
        from strongtowns_detroit.parcels.semantic_mapper import ZoningMapper

        # We need to test extract_specific_uses without loading a model.
        # Create instance with mocked model.
        mapper = ZoningMapper.__new__(ZoningMapper)  # skip __init__

        zoning_data = {
            "Residential": {
                "Single-family": {"by_right": ["R1"]},
                "Duplex": {"conditional": ["R1"]},
            },
            "Commercial": {
                "Retail": {"by_right": ["B4"]},
            },
        }

        result = mapper.extract_specific_uses(zoning_data)
        assert len(result) == 3
        assert ("Residential", "Single-family") in result
        assert ("Residential", "Duplex") in result
        assert ("Commercial", "Retail") in result

    def test_empty_data(self):
        from strongtowns_detroit.parcels.semantic_mapper import ZoningMapper

        mapper = ZoningMapper.__new__(ZoningMapper)
        result = mapper.extract_specific_uses({})
        assert result == []


class TestGetTopMatches:
    @pytest.fixture
    def mapper(self):
        from strongtowns_detroit.parcels.semantic_mapper import ZoningMapper

        return ZoningMapper.__new__(ZoningMapper)

    @pytest.fixture
    def similarity_df(self):
        """Synthetic similarity scores for testing thresholds."""
        return pd.DataFrame([
            {"use_item": "HOUSE", "use_category": "Residential", "specific_use": "Single-family", "similarity": 0.90},
            {"use_item": "HOUSE", "use_category": "Residential", "specific_use": "Duplex", "similarity": 0.65},
            {"use_item": "HOUSE", "use_category": "Commercial", "specific_use": "Retail", "similarity": 0.30},
            {"use_item": "SHOP", "use_category": "Commercial", "specific_use": "Retail", "similarity": 0.85},
            {"use_item": "SHOP", "use_category": "Residential", "specific_use": "Single-family", "similarity": 0.20},
        ])

    def test_high_confidence_matches(self, mapper, similarity_df):
        matches = mapper.get_top_matches(similarity_df, high_threshold=0.75, medium_threshold=0.60)
        assert "HOUSE" in matches["high_confidence"]
        assert matches["high_confidence"]["HOUSE"][0]["specific_use"] == "Single-family"

    def test_medium_confidence_matches(self, mapper, similarity_df):
        matches = mapper.get_top_matches(similarity_df, high_threshold=0.75, medium_threshold=0.60)
        assert "HOUSE" in matches["medium_confidence"]
        assert matches["medium_confidence"]["HOUSE"][0]["specific_use"] == "Duplex"

    def test_low_confidence_matches(self, mapper, similarity_df):
        matches = mapper.get_top_matches(similarity_df, high_threshold=0.75, medium_threshold=0.60)
        assert "HOUSE" in matches["low_confidence"]

    def test_top_k_limits_results(self, mapper, similarity_df):
        matches = mapper.get_top_matches(similarity_df, top_k=1)
        # With top_k=1, only the best match per item
        house_total = (
            len(matches["high_confidence"].get("HOUSE", []))
            + len(matches["medium_confidence"].get("HOUSE", []))
            + len(matches["low_confidence"].get("HOUSE", []))
        )
        assert house_total == 1


class TestGenerateMapping:
    def test_basic_mapping(self):
        from strongtowns_detroit.parcels.semantic_mapper import ZoningMapper

        mapper = ZoningMapper.__new__(ZoningMapper)

        matches = {
            "high_confidence": {
                "HOUSE": [
                    {"specific_use": "Single-family", "use_category": "Residential", "similarity": 0.90}
                ]
            },
            "medium_confidence": {},
            "low_confidence": {},
        }

        mapping = mapper.generate_mapping(matches)
        assert "HOUSE" in mapping
        assert mapping["HOUSE"]["confidence"] == "high"
        assert mapping["HOUSE"]["specific_use"] == "Single-family"

    def test_multiple_high_matches(self):
        from strongtowns_detroit.parcels.semantic_mapper import ZoningMapper

        mapper = ZoningMapper.__new__(ZoningMapper)

        matches = {
            "high_confidence": {
                "HOUSE": [
                    {"specific_use": "Single-family", "use_category": "Residential", "similarity": 0.92},
                    {"specific_use": "Duplex", "use_category": "Residential", "similarity": 0.80},
                ]
            },
            "medium_confidence": {},
            "low_confidence": {},
        }

        mapping = mapper.generate_mapping(matches)
        # Multiple matches => list of specific_uses
        assert isinstance(mapping["HOUSE"]["specific_use"], list)
        assert len(mapping["HOUSE"]["specific_use"]) == 2

    def test_empty_matches(self):
        from strongtowns_detroit.parcels.semantic_mapper import ZoningMapper

        mapper = ZoningMapper.__new__(ZoningMapper)
        matches = {"high_confidence": {}, "medium_confidence": {}, "low_confidence": {}}
        mapping = mapper.generate_mapping(matches)
        assert mapping == {}
