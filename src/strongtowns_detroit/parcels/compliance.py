"""Unified parcel zoning compliance checker."""

import pandas as pd

from strongtowns_detroit.constants import (
    PROPOSED_MIN_SQFT,
    PROPOSED_MIN_DWELLING_SQFT,
    CURRENT_MIN_DWELLING_ASSUMPTION,
)


def check_compliance(
    row,
    zoning_restrictions,
    *,
    district_col='zoning_district',
    area_cols=('shape_area',),
    floor_area_col='total_floor_area',
    width_col=None,
    include_buildable=False,
):
    """Check a parcel row against zoning and preemption thresholds.

    Parameters
    ----------
    row : dict-like
        A row of parcel data (e.g. from DataFrame.apply).
    zoning_restrictions : dict
        Mapping of district name -> {MinimumLotSizeInSqft, MinimumLotWidthInFt}.
    district_col : str
        Column name for the zoning district.
    area_cols : tuple of str
        Column names to try for lot area, in priority order.
        First non-NaN, non-zero value wins.
    floor_area_col : str
        Column name for dwelling floor area.
    width_col : str or None
        Column name for lot width/frontage. None skips width checking.
    include_buildable : bool
        If True, include 'is_buildable_current_zoning' in output.
    """
    district = row.get(district_col)

    res = {
        'zoning_min_sqft': None,
        'violates_current_min_sqft': False,
        'violates_proposed_min_sqft': False,
        'violates_proposed_min_dwelling': False,
        'violates_current_min_dwelling_assumption': False,
    }

    if width_col is not None:
        res['zoning_min_width'] = None
        res['violates_current_min_width'] = False

    if include_buildable:
        res['is_buildable_current_zoning'] = False

    # Resolve lot area from the fallback chain
    sqft = 0
    for col in area_cols:
        val = row.get(col, None)
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            try:
                val = float(val)
            except (ValueError, TypeError):
                val = 0
            if val != 0:
                sqft = val
                break

    # Resolve width
    width = 0
    if width_col is not None:
        try:
            width = float(row.get(width_col, 0) or 0)
        except (ValueError, TypeError):
            width = 0

    # Resolve floor area
    try:
        floor_area = float(row.get(floor_area_col, 0) or 0)
    except (ValueError, TypeError):
        floor_area = 0

    # Proposed checks
    if sqft > 0 and sqft < PROPOSED_MIN_SQFT:
        res['violates_proposed_min_sqft'] = True

    if floor_area > 0 and floor_area < PROPOSED_MIN_DWELLING_SQFT:
        res['violates_proposed_min_dwelling'] = True

    if floor_area > 0 and floor_area < CURRENT_MIN_DWELLING_ASSUMPTION:
        res['violates_current_min_dwelling_assumption'] = True

    # Current zoning checks
    current_sqft_pass = True
    current_width_pass = True

    if pd.notna(district) and district in zoning_restrictions:
        restrictions = zoning_restrictions[district]
        min_sqft_req = restrictions['MinimumLotSizeInSqft']
        res['zoning_min_sqft'] = min_sqft_req

        if width_col is not None:
            min_width_req = restrictions['MinimumLotWidthInFt']
            res['zoning_min_width'] = min_width_req
            if min_width_req is not None:
                if width > 0 and width < min_width_req:
                    res['violates_current_min_width'] = True
                    current_width_pass = False

        if min_sqft_req is not None:
            if sqft > 0 and sqft < min_sqft_req:
                res['violates_current_min_sqft'] = True
                current_sqft_pass = False

    if include_buildable:
        res['is_buildable_current_zoning'] = current_sqft_pass and current_width_pass

    return pd.Series(res)
