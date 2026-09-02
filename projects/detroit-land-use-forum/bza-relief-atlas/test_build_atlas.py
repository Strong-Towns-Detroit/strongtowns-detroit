import pandas as pd
import pytest

from build_atlas import (
    ACCESSIBLE_BLUE,
    DATA,
    OUTCOME_LABELS,
    PURPLE,
    SITE_RENDER_MODES,
    annular_marker,
    concrete_assignments,
    displace_overlapping_points,
    primary_relief_categories,
    plot_case_sites,
)

requires_reviewed_data = pytest.mark.skipif(
    not (DATA / "atlas_applications.csv").is_file(),
    reason="reviewed BZA data must be materialized in strongtowns-data",
)


def test_granted_outcome_uses_blue():
    colors = {key: color for key, _, color in OUTCOME_LABELS}
    assert colors["granted_reversed"] == ACCESSIBLE_BLUE
    assert colors["mixed_or_other_decided"] == PURPLE
    assert len(set(colors.values())) == len(colors)


@requires_reviewed_data
def test_concrete_assignments_use_categories_and_unique_histories():
    applications = pd.read_csv(DATA / "atlas_applications.csv")
    concrete = concrete_assignments(applications)

    assert len(concrete) == 531
    assert concrete["case_history_id"].nunique() == 382
    assert concrete["category"].nunique() == 20
    assert "dimensional_relief_unspecified" not in set(concrete["category"])
    assert "request_not_stated" not in set(concrete["category"])
    assert "hardship_relief" in set(concrete["category"])


def test_annular_marker_has_outer_and_inner_boundaries():
    marker = annular_marker(0, 180)

    assert len(marker.vertices) > 20
    radii = (marker.vertices[:, 0] ** 2 + marker.vertices[:, 1] ** 2) ** 0.5
    assert radii.max() == pytest.approx(1.0)
    assert 0.5 < radii[radii > 0].min() < 0.6


@requires_reviewed_data
def test_primary_relief_uses_first_concrete_recorded_category():
    applications = pd.read_csv(DATA / "atlas_applications.csv")
    primary = primary_relief_categories(applications)

    assert primary["bza-03-23-cdc3a2629c"] == (
        "administrative_or_community_appeal"
    )


def test_primary_relief_rolls_detailed_parking_up_for_display():
    applications = pd.DataFrame([
        {
            "case_history_id": "parking-case",
            "category": "parking_layout",
            "relief_categories": "parking_layout",
        }
    ])

    assert primary_relief_categories(applications)["parking-case"] == "parking"


def test_displacement_is_bounded():
    import geopandas as gpd
    from shapely.geometry import Point

    points = gpd.GeoSeries(
        [Point(0, 0), Point(0, 0), Point(0, 0)],
        index=["a", "b", "c"],
    )
    placed, maximum = displace_overlapping_points(
        points, minimum_separation=10, maximum_displacement=20
    )

    assert placed.shape == (3, 2)
    assert maximum <= 20.000001


def test_displacement_can_allow_scaled_symbol_overlap():
    import geopandas as gpd
    import numpy as np
    from shapely.geometry import Point

    points = gpd.GeoSeries([Point(0, 0), Point(0, 0)], index=["a", "b"])
    placed, _ = displace_overlapping_points(
        points,
        symbol_radii=np.array([10.0, 10.0]),
        overlap_fraction=0.10,
        maximum_displacement=20,
    )

    separation = np.linalg.norm(placed[0] - placed[1])
    assert 18 <= separation < 20


def test_site_render_modes_are_explicit():
    assert SITE_RENDER_MODES == {"dots", "parcels", "both"}
    with pytest.raises(ValueError, match="Unknown site render mode"):
        plot_case_sites(None, None, "#000000", "unknown")
