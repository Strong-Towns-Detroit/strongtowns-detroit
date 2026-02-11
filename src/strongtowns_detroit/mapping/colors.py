"""Detroit map color palettes and display constants.

All colors are plain hex strings — no matplotlib dependency — so they can
be used with any plotting library (matplotlib, folium, plotly, etc.).
"""

# ── Geographic context layers ────────────────────────────────────────
WATER_FILL = '#c6e3f0'
WATER_EDGE = '#7fb3d5'
WATER_PARCEL = '#53A9D4'       # brighter blue used in parcel buildability maps
STREET = '#666666'
BOUNDARY = '#2c3e50'

# ── Parcel buildability ──────────────────────────────────────────────
BUILDABLE = '#0C2340'          # navy — meets current zoning
NOT_BUILDABLE = '#FA4616'      # orange — fails current zoning

# ── Housing burden ───────────────────────────────────────────────────
SHORTAGE = '#b82f23'           # red — price/income ratio > 3
ACCESSIBILITY_CRISIS = '#1d5782'  # blue — >50% renters cost-burdened
BOTH_ISSUES = '#6d29ac'        # purple — shortage + accessibility crisis
NEUTRAL = '#d9d9d9'            # gray — no issue / no data

# ── Housing burden category lookup ───────────────────────────────────
HOUSING_CATEGORY_COLORS = {
    'Neither': NEUTRAL,
    'Shortage Only': SHORTAGE,
    'Accessibility Only': ACCESSIBILITY_CRISIS,
    'Both Issues': BOTH_ISSUES,
    'No Data': NEUTRAL,
}

SHORTAGE_COLORS = {True: SHORTAGE, False: NEUTRAL}
ACCESSIBILITY_COLORS = {True: ACCESSIBILITY_CRISIS, False: NEUTRAL}

# ── Choropleth defaults ──────────────────────────────────────────────
BURDEN_CMAP = 'YlOrRd'
BURDEN_BINS = [20, 30, 40, 50, 60]
ALPHA_BLOCKGROUPS = 0.6

# ── Z-order layer stacking convention ────────────────────────────────
Z_WATER = 1
Z_DATA = 2
Z_STREETS = 3
Z_BOUNDARY = 4
