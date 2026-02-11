"""Preemption analysis utilities."""

import pandas as pd


def is_vacant(desc):
    """Determine if a parcel use-code description indicates vacancy."""
    if pd.isna(desc):
        return True
    d = desc.upper()
    return 'VACANT' in d or 'NO BLDG' in d or 'IMPROVED NO BLDG' in d
