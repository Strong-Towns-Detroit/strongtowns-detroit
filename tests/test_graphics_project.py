"""Tests for the one-source, multiple-target graphics project."""

from pathlib import Path

from projects.graphics import build as BUILD
from strongtowns_detroit.graphics.cli import main as graphics_main

ROOT = Path(__file__).resolve().parents[1]
GRAPHICS_ROOT = BUILD.SOURCE_ROOT / "graphics"


def test_expected_graphic_families_are_in_neutral_source_tree():
    names = {
        path.stem
        for path in GRAPHICS_ROOT.glob("*.py")
        if path.name != "__init__.py"
    }
    assert names == {
        "assessed_value_per_acre",
        "bza_cases_map",
        "bza_proposed_use_map",
        "campus_martius_accessibility",
        "minimum_lot_area",
        "minimum_lot_width",
        "parking_gaps_by_project_type",
        "residential_setback_envelope",
    }


def test_discovery_identity_comes_from_library_registration_not_paths():
    definitions = BUILD.SYSTEM.definitions()

    assert {item.name for item in definitions} == {
        path.stem for path in GRAPHICS_ROOT.glob("*.py")
    }
    assert all(item.module is not None for item in definitions)


def test_each_graphic_definition_owns_its_editorial_copy():
    required_fields = ("title=", "subtitle=", "sources=", "description=")
    for definition in GRAPHICS_ROOT.glob("*.py"):
        if definition.name == "__init__.py":
            continue
        source = "".join(definition.read_text().split())
        missing = [field for field in required_fields if field not in source]
        assert not missing, f"{definition} delegates editorial copy: {missing}"
        assert "replace(" not in source, (
            f"{definition} rewrites a built Graphic instead of using its renderer API"
        )


def test_bza_point_maps_share_the_polars_driven_library_renderer():
    for name in ("bza_cases_map", "bza_proposed_use_map"):
        source = (GRAPHICS_ROOT / f"{name}.py").read_text()
        assert "categorical_proportional_symbol_map(" in source
        assert "pl.DataFrame(records)" in source


def test_parking_chart_declares_its_data_and_encoding_in_the_graphic_file():
    source = (GRAPHICS_ROOT / "parking_gaps_by_project_type.py").read_text()

    assert "bar_chart(" in source
    assert 'column="proposed_or_provided"' in source
    assert 'column="required_beyond_proposal"' in source
    assert "CATEGORY_ORDER" in source
    assert "group_by(\"project_type\")" in source
    assert "axis=NumericAxis(" in source
    assert "legend_alignment=ChartAlignment.RIGHT" in source
    assert "orientation=BarOrientation.HORIZONTAL" in source
    assert "portrait_orientation=BarOrientation.VERTICAL" in source
    assert "portrait_category_label_angle=-35" in source
    assert "arrangement=BarArrangement.STACKED" in source
    assert "series=(" in source
    assert "style=BarChartStyle(" in source
    assert "summarize(" not in source


def test_publishing_targets_own_aspect_ratio_and_pixel_width():
    from strongtowns_detroit.graphics import GRAPHIC_FORMAT_SPECS, GraphicFormat

    instagram = GRAPHIC_FORMAT_SPECS[GraphicFormat.INSTAGRAM_POST]
    story = GRAPHIC_FORMAT_SPECS[GraphicFormat.INSTAGRAM_STORY]
    conference = GRAPHIC_FORMAT_SPECS[GraphicFormat.LAND_USE_CONFERENCE]
    assert instagram.aspect_ratio.css == "4/5" and instagram.png_width == 1080
    assert story.aspect_ratio.css == "9/16" and story.png_width == 1080
    assert story.content_aspect_ratio.css == "4/5"
    assert story.content_top_padding == 0.14
    assert conference.aspect_ratio.css == "16/11" and conference.png_width == 3200


def test_unknown_source_is_rejected():
    try:
        BUILD.run(sources=["does_not_exist"])
    except ValueError as error:
        assert "unknown graphic sources" in str(error)
    else:
        raise AssertionError("missing source should fail")


def test_cli_lists_automatically_discovered_graphics(capsys):
    result = graphics_main(["--project", str(BUILD.HERE), "list"])

    assert result == 0
    assert "bza_cases_map" in capsys.readouterr().out.splitlines()


def test_build_system_prefers_nested_graphics_project_from_repository_root():
    from strongtowns_detroit.graphics import GraphicBuildSystem

    assert GraphicBuildSystem.find(ROOT).root == BUILD.HERE
