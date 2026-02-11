"""Tests for strongtowns_detroit.config module."""

import json
import os

import pytest

from strongtowns_detroit.config import get_census_api_key, load_json_config


class TestGetCensusApiKey:
    def test_returns_key_from_env(self, monkeypatch):
        monkeypatch.setenv("CENSUS_API_KEY", "test-key-123")
        assert get_census_api_key() == "test-key-123"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("CENSUS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="CENSUS_API_KEY not set"):
            get_census_api_key()


class TestLoadJsonConfig:
    def test_loads_valid_json(self, tmp_path):
        data = {"R1": {"MinimumLotSizeInSqft": 4000}}
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))
        result = load_json_config(path)
        assert result == data

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_json_config(tmp_path / "nonexistent.json")
