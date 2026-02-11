"""Configuration helpers: API keys from .env, JSON config loading."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv


def get_census_api_key() -> str:
    """Load Census API key from .env file or environment."""
    load_dotenv()
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise ValueError("CENSUS_API_KEY not set. Add it to .env or environment.")
    return key


def load_json_config(path: str | Path) -> dict:
    """Load a JSON configuration file."""
    with open(path) as f:
        return json.load(f)
