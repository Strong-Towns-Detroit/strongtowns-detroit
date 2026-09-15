"""Resolve BZA evidence through this project's existing immutable data lock."""
from pathlib import Path
from strongtowns_data import bza
from .repositories import data_repository


def dataset():
    root = Path(__file__).resolve().parents[2]
    return bza.open(lock=root / "strongtowns-data.lock.json", repository=data_repository())


def data_directory():
    return dataset().directory
