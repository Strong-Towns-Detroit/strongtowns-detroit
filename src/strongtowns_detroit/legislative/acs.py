"""ACS variable definitions for state legislative district analysis.

Variables are grouped by topic so callers can request a subset and so the
metrics module can compute derived shares against known denominators.
"""

# ── Population & age (full B01001 brackets so we can build an age histogram) ─
POPULATION_VARS = {
    'B01003_001E': 'total_population',
    'B01001_001E': 'pop_total_for_age',
    # Male age brackets
    'B01001_003E': 'male_under_5',
    'B01001_004E': 'male_5_9',
    'B01001_005E': 'male_10_14',
    'B01001_006E': 'male_15_17',
    'B01001_007E': 'male_18_19',
    'B01001_008E': 'male_20',
    'B01001_009E': 'male_21',
    'B01001_010E': 'male_22_24',
    'B01001_011E': 'male_25_29',
    'B01001_012E': 'male_30_34',
    'B01001_013E': 'male_35_39',
    'B01001_014E': 'male_40_44',
    'B01001_015E': 'male_45_49',
    'B01001_016E': 'male_50_54',
    'B01001_017E': 'male_55_59',
    'B01001_018E': 'male_60_61',
    'B01001_019E': 'male_62_64',
    'B01001_020E': 'male_65_66',
    'B01001_021E': 'male_67_69',
    'B01001_022E': 'male_70_74',
    'B01001_023E': 'male_75_79',
    'B01001_024E': 'male_80_84',
    'B01001_025E': 'male_85_plus',
    # Female age brackets
    'B01001_027E': 'female_under_5',
    'B01001_028E': 'female_5_9',
    'B01001_029E': 'female_10_14',
    'B01001_030E': 'female_15_17',
    'B01001_031E': 'female_18_19',
    'B01001_032E': 'female_20',
    'B01001_033E': 'female_21',
    'B01001_034E': 'female_22_24',
    'B01001_035E': 'female_25_29',
    'B01001_036E': 'female_30_34',
    'B01001_037E': 'female_35_39',
    'B01001_038E': 'female_40_44',
    'B01001_039E': 'female_45_49',
    'B01001_040E': 'female_50_54',
    'B01001_041E': 'female_55_59',
    'B01001_042E': 'female_60_61',
    'B01001_043E': 'female_62_64',
    'B01001_044E': 'female_65_66',
    'B01001_045E': 'female_67_69',
    'B01001_046E': 'female_70_74',
    'B01001_047E': 'female_75_79',
    'B01001_048E': 'female_80_84',
    'B01001_049E': 'female_85_plus',
}

# 8 campaign-relevant age bins. Each maps to the male+female bracket
# columns whose values get summed for a tract.
AGE_BINS = [
    ('age_0_17',    ['under_5', '5_9', '10_14', '15_17']),
    ('age_18_24',   ['18_19', '20', '21', '22_24']),
    ('age_25_34',   ['25_29', '30_34']),
    ('age_35_44',   ['35_39', '40_44']),
    ('age_45_54',   ['45_49', '50_54']),
    ('age_55_64',   ['55_59', '60_61', '62_64']),
    ('age_65_74',   ['65_66', '67_69', '70_74']),
    ('age_75_plus', ['75_79', '80_84', '85_plus']),
]

# ── Race & Hispanic origin (B03002 — non-overlapping) ───────────────
RACE_VARS = {
    'B03002_001E': 'race_total',
    'B03002_003E': 'nh_white',
    'B03002_004E': 'nh_black',
    'B03002_005E': 'nh_aian',
    'B03002_006E': 'nh_asian',
    'B03002_007E': 'nh_nhpi',
    'B03002_008E': 'nh_other',
    'B03002_009E': 'nh_two_or_more',
    'B03002_012E': 'hispanic',
}

# ── Income & poverty ────────────────────────────────────────────────
INCOME_VARS = {
    'B19013_001E': 'median_household_income',
    'B17001_001E': 'poverty_universe',
    'B17001_002E': 'poverty_below',
}

# ── Education (population 25+) ──────────────────────────────────────
EDUCATION_VARS = {
    'B15003_001E': 'edu_total_25plus',
    'B15003_017E': 'edu_hs_diploma',
    'B15003_018E': 'edu_ged',
    'B15003_022E': 'edu_bachelors',
    'B15003_023E': 'edu_masters',
    'B15003_024E': 'edu_professional',
    'B15003_025E': 'edu_doctorate',
}

# ── Housing tenure & cost ───────────────────────────────────────────
HOUSING_VARS = {
    'B25002_001E': 'housing_units_total',
    'B25002_003E': 'housing_units_vacant',
    'B25003_001E': 'tenure_total',
    'B25003_002E': 'owner_occupied',
    'B25003_003E': 'renter_occupied',
    'B25077_001E': 'median_home_value',
    'B25064_001E': 'median_gross_rent',
}

# ── Employment & labor force ────────────────────────────────────────
EMPLOYMENT_VARS = {
    'B23025_001E': 'pop_16plus',
    'B23025_002E': 'in_labor_force',
    'B23025_005E': 'unemployed',
}

# ── Place of birth & language ───────────────────────────────────────
ORIGIN_VARS = {
    'B05002_001E': 'pob_total',
    'B05002_013E': 'foreign_born',
    'C16001_001E': 'lang_total_5plus',
    'C16001_002E': 'lang_english_only',
}

ALL_VAR_GROUPS = {
    'population': POPULATION_VARS,
    'race': RACE_VARS,
    'income': INCOME_VARS,
    'education': EDUCATION_VARS,
    'housing': HOUSING_VARS,
    'employment': EMPLOYMENT_VARS,
    'origin': ORIGIN_VARS,
}


def all_variables() -> dict[str, str]:
    """Flat {census_code: friendly_name} for every group."""
    merged: dict[str, str] = {}
    for group in ALL_VAR_GROUPS.values():
        merged.update(group)
    return merged
