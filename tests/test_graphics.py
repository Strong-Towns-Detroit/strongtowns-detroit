"""Tests for the public strongtowns_detroit.graphics library."""

import json

import polars as pl
import pytest

from strongtowns_detroit.graphics.maps import _magnitude_legend_values

from strongtowns_detroit.graphics import (
    BarArrangement,
    BarChartStyle,
    BarOrientation,
    BarPattern,
    BarSeries,
    INSTAGRAM_PORTRAIT,
    INSTAGRAM_STORY,
    AspectRatio,
    Graphic,
    GraphicFormat,
    GraphicProject,
    GraphicTheme,
    LegendOrders,
    MapLegend,
    MobileMapInset,
    MobileMapInsetKind,
    MobileMapLayout,
    MobileMapSegment,
    MobileMapPocket,
    MOBILE_TYPOGRAPHY,
    MapMarkerStyle,
    NumericAxis,
    SvgComponent,
    SvgRegion,
    apply_layout_sidecar,
    bar_chart,
    bza_hearing_marker_area,
    bza_hearing_marker_radius,
    build_map_graphic,
    render_graphic_svg,
    render_graphic_canvas,
    write_graphic_bundle,
    write_graphic_variants,
    categorical_proportional_symbol_map,
)


def example_graphic() -> Graphic:
    return Graphic(
        title=(
            "Developers consistently propose far fewer parking spaces than "
            "the law requires."
        ),
        subtitle="Parking gaps by project type",
        visual=SvgComponent('<circle cx="50" cy="50" r="25"/>', 100, 100),
        notes=("A methodological note.",),
        sources=("Source: Detroit BZA minutes.",),
    )


def test_aspect_ratio_parsing_and_orientation() -> None:
    assert AspectRatio.parse("4:5") == INSTAGRAM_PORTRAIT
    assert AspectRatio.parse("16/9").orientation == "landscape"
    assert AspectRatio.parse("1").orientation == "square"
    assert AspectRatio.parse("3:4").orientation == "portrait"


def test_aspect_ratio_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValueError):
        AspectRatio(0, 5)


def test_svg_graphic_owns_title_wrapping_and_page_layout() -> None:
    svg = render_graphic_svg(example_graphic(), aspect_ratio=AspectRatio(16, 11))

    assert 'viewBox="0 0 1600 1100"' in svg
    assert 'class="graphic-title"' in svg
    assert "Developers consistently propose far fewer" in svg
    assert '<svg x="52"' in svg
    assert '<circle cx="50" cy="50" r="25"/>' in svg
    assert "A methodological note." in svg


def test_svg_component_supports_a_nonzero_viewbox_origin() -> None:
    graphic = Graphic(
        title="Map",
        visual=SvgComponent("<path/>", 1600, 800, min_y=180),
    )
    svg = render_graphic_svg(graphic)
    assert 'viewBox="0 180 1600 800"' in svg


def test_generic_map_builder_accepts_semantic_copy_and_metadata() -> None:
    visual = SvgComponent("<path/>", 100, 100)
    graphic = build_map_graphic(
        visual=visual,
        title="A specific map",
        subtitle="What it shows",
        sources=("Source text",),
        description="Accessible description",
        metadata={"maximum": 8},
    )

    assert graphic.visual is visual
    assert graphic.title == "A specific map"
    assert graphic.subtitle == "What it shows"
    assert graphic.sources == ("Source text",)
    assert graphic.description == "Accessible description"
    assert graphic.metadata == {"maximum": 8}


def test_bar_chart_uses_explicit_data_and_encoding() -> None:
    graphic = bar_chart(
        pl.DataFrame(
            {
                "category": ["Housing"],
                "proposed": [5],
                "remainder": [15],
                "annotation": ["5 proposed · 20 required"],
            }
        ),
        category="category",
        annotation="annotation",
        orientation=BarOrientation.HORIZONTAL,
        arrangement=BarArrangement.STACKED,
        series=(
            BarSeries("proposed", "Proposed", "#111111"),
            BarSeries(
                "remainder",
                "Required beyond proposal",
                "#cc0000",
                BarPattern.DIAGONAL,
            ),
        ),
        portrait_orientation=BarOrientation.VERTICAL,
        portrait_category_label_angle=-35,
        title="Parking",
        subtitle="One category",
        axis=NumericAxis(title="REQUIRED AND PROPOSED SPACES", tick_step=10),
        style=BarChartStyle(),
    )

    assert graphic.metadata == {
        "chart_type": "bar",
        "orientation": "horizontal",
        "portrait_orientation": "vertical",
        "arrangement": "stacked",
        "axis_maximum": 20,
    }
    assert "Housing" in graphic.visual.markup
    assert "5 proposed · 20 required" in graphic.visual.markup
    assert 'width="200.0"' in graphic.visual.markup
    assert 'width="600.0"' in graphic.visual.markup
    assert graphic.visual.portrait_variant is not None
    portrait = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)
    landscape = render_graphic_svg(graphic)
    assert 'viewBox="0 0 1450 1170"' in portrait
    assert 'viewBox="0 0 1450 620"' in landscape
    assert 'transform="rotate(-35 ' in portrait
    assert f"font-size:{MOBILE_TYPOGRAPHY.axis}px" in portrait
    assert f"font-size:{MOBILE_TYPOGRAPHY.legend}px" in portrait


def test_bar_chart_rejects_implicit_data_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        bar_chart(
            pl.DataFrame({"category": ["Housing"], "proposed": [5]}),
            category="category",
            orientation=BarOrientation.HORIZONTAL,
            arrangement=BarArrangement.STACKED,
            series=(
                BarSeries("proposed", "Proposed", "#111111"),
                BarSeries("remainder", "Remainder", "#cc0000"),
            ),
            title="Parking",
            subtitle="",
            axis=NumericAxis(title="SPACES", tick_step=10),
        )


def test_categorical_proportional_symbol_map_requires_explicit_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        categorical_proportional_symbol_map(
            pl.DataFrame({"easting": [-9250000.0], "northing": [5210000.0]}),
            basemap=None,
            title="Map",
            subtitle="",
            category_legend_heading="Category",
            magnitude_legend_heading="Magnitude",
        )


def test_categorical_map_rejects_implicit_category_labels_or_colors() -> None:
    data = pl.DataFrame(
        {
            "point_id": ["one", "two"],
            "easting": [-9250000.0, -9250100.0],
            "northing": [5210000.0, 5210100.0],
            "category": ["same", "same"],
            "category_label": ["First label", "Second label"],
            "color": ["#111111", "#111111"],
            "magnitude": [1, 2],
            "category_count": [1, 1],
        }
    )
    with pytest.raises(ValueError, match="exactly one label and color"):
        categorical_proportional_symbol_map(
            data,
            basemap=None,
            title="Map",
            subtitle="",
            category_legend_heading="Category",
            magnitude_legend_heading="Magnitude",
        )


def test_proportional_legend_levels_do_not_cluster_near_the_maximum() -> None:
    assert _magnitude_legend_values(5, None) == (6, 3, 1)
    assert _magnitude_legend_values(8, None) == (8, 4, 1)


def test_portrait_regions_stack_while_landscape_keeps_one_visual() -> None:
    visual = SvgComponent(
        '<rect width="100" height="100"/>',
        100,
        100,
        portrait_regions=(SvgRegion(0, 0, 60, 60), SvgRegion(60, 0, 40, 60)),
    )
    graphic = Graphic(title="Regions", visual=visual)
    portrait = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)
    landscape = render_graphic_svg(graphic)
    assert portrait.count('<rect width="100" height="100"/>') == 2
    assert 'viewBox="0 0 60 60"' in portrait
    assert 'viewBox="60 0 40 60"' in portrait
    assert landscape.count('<rect width="100" height="100"/>') == 1


def test_portrait_region_can_bleed_beyond_the_text_margin() -> None:
    visual = SvgComponent(
        "<path/>",
        100,
        100,
        portrait_regions=(SvgRegion(0, 0, 100, 50),),
        portrait_margin=0,
    )
    svg = render_graphic_svg(
        Graphic(title="Full-width map", visual=visual),
        aspect_ratio=INSTAGRAM_PORTRAIT,
    )
    assert '<svg x="0"' in svg
    assert 'width="1600"' in svg
    assert f".graphic-note{{font-size:{MOBILE_TYPOGRAPHY.minimum}px" in svg
    assert f".graphic-source{{font-size:{MOBILE_TYPOGRAPHY.minimum}px" in svg


def test_mobile_detroit_map_width_is_independent_of_source_viewbox() -> None:
    first = Graphic(
        title="First map",
        visual=SvgComponent(
            "<path/>", 100, 100,
            mobile_map_layout=MobileMapLayout(SvgRegion(0, 0, 100, 50)),
        ),
    )
    second = Graphic(
        title="Second map",
        visual=SvgComponent(
            "<path/>", 500, 500,
            mobile_map_layout=MobileMapLayout(SvgRegion(20, 30, 400, 200)),
        ),
    )
    for graphic in (first, second):
        svg = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)
    assert 'width="1570"' in svg
    assert 'overflow="visible"' in svg
    assert '<rect x="20" y="10" width="400" height="220"/>' in svg


def test_mobile_map_pockets_accept_independent_typed_insets() -> None:
    from strongtowns_detroit.graphics import map_on_mobile

    graphic = map_on_mobile(
        Graphic(title="Map", visual=SvgComponent("<path/>", 1080, 1080)),
        insets=(
            MobileMapInset.hero_statistic(
                pocket=MobileMapPocket.LOWER_RIGHT,
                value="$167K",
                label=("MEDIAN VALUE PER ACRE",),
            ),
        ),
    )
    svg = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)

    assert "$167K" in svg
    assert "MEDIAN VALUE PER ACRE" in svg
    assert "56%" not in svg
    assert MobileMapInsetKind.HERO_STATISTIC.value == "hero_statistic"


def test_mobile_map_pocket_accepts_automatically_wrapped_editorial_text() -> None:
    from strongtowns_detroit.graphics import map_on_mobile

    graphic = map_on_mobile(
        Graphic(title="Map", visual=SvgComponent("<path/>", 1080, 1080)),
        insets=(
            MobileMapInset.text_block(
                pocket=MobileMapPocket.LOWER_LEFT,
                text=(
                    "Beyond these visible cases, zoning also shapes housing "
                    "that is quietly redesigned to comply."
                ),
            ),
        ),
    )

    svg = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)

    assert MobileMapInsetKind.TEXT_BLOCK.value == "text_block"
    assert 'class="mobile-inset-text"' in svg
    assert "Beyond these visible cases," in svg
    assert 'data-layout-node="inset-lower-left"' in svg


def test_mobile_map_segment_is_a_sibling_after_the_legend() -> None:
    from strongtowns_detroit.graphics import map_on_mobile

    graphic = map_on_mobile(
        Graphic(title="Map", visual=SvgComponent("<path/>", 1080, 1080)),
        legend=MapLegend(
            heading="Types",
            items=(("One", 1, "#111111"),),
        ),
        segments=(
            MobileMapSegment(
                name="context",
                content=SvgComponent(
                    '<text class="context">Independent context</text>',
                    1080,
                    120,
                ),
            ),
        ),
    )
    svg = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)

    assert 'data-layout-node="map"' in svg
    assert 'data-layout-node="legend"' in svg
    assert 'data-layout-node="segment-context"' in svg
    assert svg.index('data-layout-node="legend"') < svg.index(
        'data-layout-node="segment-context"'
    )
    assert "Independent context" in svg
    assert 'clip-path="url(#mobile-map-layout-bounds)"' in svg


def test_mobile_map_effect_size_inset_scales_circle_area() -> None:
    from strongtowns_detroit.graphics import map_on_mobile

    graphic = map_on_mobile(
        Graphic(title="Map", visual=SvgComponent("<path/>", 1080, 1080)),
        insets=(
            MobileMapInset.effect_size_legend(
                pocket=MobileMapPocket.LOWER_LEFT,
                heading="HEARINGS PER CASE",
                levels=(("1", 1), ("4", 4)),
                radius_per_sqrt_unit=7,
            ),
        ),
    )
    svg = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)

    assert "HEARINGS PER CASE" in svg
    assert 'r="7.00"' in svg
    assert 'r="14.00"' in svg
    assert svg.count('cx="40"') == 2
    assert 'transform="translate(250 0)"' in svg


def test_counted_mobile_legend_supports_standard_ordering() -> None:
    from strongtowns_detroit.graphics import map_on_mobile

    base = Graphic(title="Map", visual=SvgComponent("<path/>", 1080, 1080))
    items = [
        ("One", 1, "#111111"),
        ("Three", 3, "#333333"),
        ("Two", 2, "#222222"),
    ]
    descending = map_on_mobile(
        base,
        legend=MapLegend(
            heading="Legend", items=items, order=LegendOrders.DESCENDING
        ),
    )
    ascending = map_on_mobile(
        base,
        legend=MapLegend(
            heading="Legend", items=items, order=LegendOrders.ASCENDING
        ),
    )

    assert descending.visual.markup.index(">Three</text>") < (
        descending.visual.markup.index(">Two</text>")
    ) < descending.visual.markup.index(">One</text>")
    assert ascending.visual.markup.index(">One</text>") < (
        ascending.visual.markup.index(">Two</text>")
    ) < ascending.visual.markup.index(">Three</text>")
    assert (
        f"font:{MOBILE_TYPOGRAPHY.local_minimum(1472 / 1080)}px Arial"
        in descending.visual.markup
    )


def test_counted_mobile_legend_accepts_a_custom_comparator() -> None:
    from strongtowns_detroit.graphics import map_on_mobile

    base = Graphic(title="Map", visual=SvgComponent("<path/>", 1080, 1080))
    graphic = map_on_mobile(
        base,
        legend=MapLegend(
            heading="Legend",
            items=[("Alpha", 3, "#111111"), ("Beta", 1, "#222222")],
            order=lambda left, right: -1 if left[0] > right[0] else 1,
        ),
    )

    assert graphic.visual.markup.index(">Beta</text>") < (
        graphic.visual.markup.index(">Alpha</text>")
    )


def test_bza_hearing_marker_area_matches_map_algorithm() -> None:
    assert bza_hearing_marker_area(1) == 100
    assert bza_hearing_marker_area(4) == 400
    assert bza_hearing_marker_area(8) == 800
    assert bza_hearing_marker_area(20) == 1000


def test_bza_hearing_marker_radius_converts_the_map_marker_to_svg_units() -> None:
    one = bza_hearing_marker_radius(
        1, raster_dpi=144, raster_width=1015, embedded_width=1015
    )
    eight = bza_hearing_marker_radius(
        8, raster_dpi=144, raster_width=1015, embedded_width=1015
    )

    assert one == 10
    assert eight == pytest.approx(10 * 8 ** 0.5)


def test_map_marker_style_validates_opacity_and_overlap() -> None:
    style = MapMarkerStyle(opacity=0.7, overlap_fraction=0.15)
    assert style.opacity == 0.7
    assert style.overlap_fraction == 0.15

    with pytest.raises(ValueError, match="opacity"):
        MapMarkerStyle(opacity=0)
    with pytest.raises(ValueError, match="overlap"):
        MapMarkerStyle(overlap_fraction=1)


def test_effect_size_leaders_fan_symmetrically_into_number_centers() -> None:
    from strongtowns_detroit.graphics import map_on_mobile

    graphic = map_on_mobile(
        Graphic(title="Map", visual=SvgComponent("<path/>", 1080, 1080)),
        insets=(
            MobileMapInset.effect_size_legend(
                pocket=MobileMapPocket.LOWER_LEFT,
                heading="HEARINGS PER CASE",
                levels=(("8", 8), ("4", 4), ("1", 1)),
                radius_per_sqrt_unit=1,
            ),
        ),
    )
    svg = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)

    assert "40,831.00 76,831.00 86,831.00" in svg
    assert 'dominant-baseline="middle"' in svg
    assert 'y="836.00" dominant-baseline="middle">4</text>' in svg
    assert (
        'data-layout-node="heading" x="360" y="775" text-anchor="end"'
        in svg
    )


def test_mobile_map_rejects_two_insets_in_one_pocket() -> None:
    from strongtowns_detroit.graphics import map_on_mobile

    first = MobileMapInset.hero_statistic(
        pocket=MobileMapPocket.LOWER_LEFT,
        value="1",
        label=("FIRST",),
    )
    second = MobileMapInset.hero_statistic(
        pocket=MobileMapPocket.LOWER_LEFT,
        value="2",
        label=("SECOND",),
    )
    with pytest.raises(ValueError, match="only one inset"):
        map_on_mobile(
            Graphic(title="Map", visual=SvgComponent("<path/>", 1080, 1080)),
            insets=(first, second),
        )


def test_svg_graphic_accepts_a_theme() -> None:
    svg = render_graphic_svg(
        example_graphic(),
        theme=GraphicTheme(background="#ffffff", accent="#ff0000"),
    )
    assert ".graphic-paper{fill:#ffffff}" in svg
    assert ".graphic-kicker" in svg
    assert "fill:#ff0000" in svg
    assert "STRONG TOWNS DETROIT" in svg
    assert "DETROIT LAND USE FORUM" not in svg
    assert 'class="graphic-brand-mark"' in svg
    assert "data:image/png;base64," in svg
    assert 'class="graphic-kicker" x="84" y="36.938"' in svg
    assert '>STRONG TOWNS DETROIT</text>' in svg


def test_portrait_titles_wrap_automatically_into_balanced_lines() -> None:
    graphic = Graphic(
        title=(
            "Only the wealthiest neighborhoods meet Detroit's 50ft minimum "
            "lot width"
        ),
        visual=SvgComponent("<g/>", 1, 1),
    )

    svg = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)

    assert "Only the wealthiest neighborhoods" in svg
    assert "meet Detroit&#x27;s 50ft minimum lot width" in svg


def test_title_tuple_supplies_explicit_lines() -> None:
    graphic = Graphic(
        title=("First explicit line", "Second explicit line"),
        visual=SvgComponent("<g/>", 1, 1),
    )

    svg = render_graphic_svg(graphic, aspect_ratio=INSTAGRAM_PORTRAIT)

    assert '<tspan x="64" y="126">First explicit line</tspan>' in svg
    assert '<tspan x="64" dy="77.76">Second explicit line</tspan>' in svg
    assert "<title id=\"title\">First explicit line Second explicit line</title>" in svg


def test_layout_sidecar_applies_only_to_semantic_nodes() -> None:
    svg = render_graphic_svg(example_graphic(), aspect_ratio=INSTAGRAM_PORTRAIT)
    edited = apply_layout_sidecar(
        svg,
        {
            "schema_version": 1,
            "nodes": {
                "graphic.title": {
                    "attributes": {"transform": "translate(0 12)"}
                }
            },
        },
    )

    assert 'data-layout-node="title" transform="translate(0 12)"' in edited


def test_layout_sidecar_rejects_unknown_nodes() -> None:
    svg = render_graphic_svg(example_graphic())
    with pytest.raises(ValueError, match="unknown nodes"):
        apply_layout_sidecar(
            svg,
            {
                "schema_version": 1,
                "nodes": {"graphic.missing": {"attributes": {"x": "1"}}},
            },
        )


def test_story_canvas_places_unchanged_feed_graphic_after_top_padding() -> None:
    svg = render_graphic_canvas(
        example_graphic(),
        canvas_aspect_ratio=INSTAGRAM_STORY,
        content_aspect_ratio=INSTAGRAM_PORTRAIT,
        content_top_padding=0.14,
    )
    assert 'viewBox="0 0 1600 2844"' in svg
    assert '<svg x="0" y="398.16" width="1600" height="2000">' in svg
    assert 'viewBox="0 0 1600 2000"' in svg


def test_svg_bundle_writes_html_and_svg_without_browser(tmp_path) -> None:
    written = write_graphic_bundle(
        tmp_path,
        "example",
        example_graphic(),
        formats={"html", "svg"},
    )

    assert set(written) == {"html", "svg"}
    assert "<main><svg" in written["html"].read_text()
    assert '<circle cx="50" cy="50" r="25"/>' in written["svg"].read_text()


def test_variants_use_one_graphic_with_multiple_ratios(tmp_path) -> None:
    written = write_graphic_variants(
        tmp_path,
        "parking",
        example_graphic(),
        {
            "conference": AspectRatio(16, 11),
            "instagram": INSTAGRAM_PORTRAIT,
        },
        formats={"html", "svg"},
    )

    assert set(written) == {"conference", "instagram"}
    assert 'viewBox="0 0 1600 1100"' in written["conference"]["svg"].read_text()
    assert 'viewBox="0 0 1600 2000"' in written["instagram"]["svg"].read_text()


def test_bundle_rejects_unknown_formats(tmp_path) -> None:
    with pytest.raises(ValueError, match="unsupported graphic formats"):
        write_graphic_bundle(
            tmp_path,
            "example",
            example_graphic(),
            formats={"webp"},
        )


def test_graphic_project_loads_definition_once_and_fans_out(tmp_path) -> None:
    source_root = tmp_path / "src"
    source_dir = source_root / "anything" / "the-user-wants"
    source_dir.mkdir(parents=True)
    marker = tmp_path / "build-count.txt"
    (source_dir / "unrelated_filename.py").write_text(
        "from pathlib import Path\n"
        "from strongtowns_detroit.graphics import (\n"
        "    Graphic, SvgComponent, graphic_definition,\n"
        ")\n"
        f"MARKER = Path({str(marker)!r})\n"
        "@graphic_definition('example')\n"
        "def build():\n"
        "    MARKER.write_text(MARKER.read_text() + 'x' "
        "if MARKER.exists() else 'x')\n"
        "    return {'example': Graphic('Example', SvgComponent('<g/>', 1, 1))}\n",
        encoding="utf-8",
    )
    layout_dir = source_root / "layout" / "example" / "instagram"
    layout_dir.mkdir(parents=True)
    (layout_dir / "example.json").write_text(
        '{"schema_version":1,"nodes":{"graphic.title":'
        '{"attributes":{"transform":"translate(0 9)"}}}}',
        encoding="utf-8",
    )
    project = GraphicProject(
        source_root,
        tmp_path / "output",
        formats=(GraphicFormat.INSTAGRAM_POST, GraphicFormat.INSTAGRAM_STORY),
        artifact_formats=("html", "svg"),
    )

    records = project.build()

    assert marker.read_text() == "x"
    assert len(records) == 2
    assert {record.target for record in records} == {"instagram", "instagram_story"}
    assert (tmp_path / "output" / "instagram" / "manifest.json").exists()
    assert (
        tmp_path / "output" / "instagram_story" / "example" / "example.svg"
    ).exists()
    instagram_svg = (
        tmp_path / "output" / "instagram" / "example" / "example.svg"
    ).read_text()
    assert 'data-layout-node="title" transform="translate(0 9)"' in instagram_svg


def test_graphic_project_rejects_unknown_format(tmp_path) -> None:
    project = GraphicProject(tmp_path / "src", tmp_path / "output")
    with pytest.raises(ValueError, match="unknown publishing format"):
        project.build(formats=["anything"])


def test_build_system_finds_project_and_automatically_discovers_graphics(
    tmp_path,
) -> None:
    from strongtowns_detroit.graphics import GraphicBuildSystem

    project_root = tmp_path / "projects" / "graphics"
    first = project_root / "src" / "user" / "picked" / "alpha.py"
    second = project_root / "src" / "another_place" / "beta.py"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text(
        "from strongtowns_detroit.graphics import graphic_definition\n"
        "@graphic_definition('first')\n"
        "def build(): return {}\n",
        encoding="utf-8",
    )
    second.write_text(
        "from strongtowns_detroit.graphics import graphic_definition\n"
        "@graphic_definition('second')\n"
        "def build(): return {}\n",
        encoding="utf-8",
    )

    system = GraphicBuildSystem.find(tmp_path)

    assert system.root == project_root
    assert [item.name for item in system.definitions()] == ["first", "second"]


def test_partial_build_merges_existing_manifest_entries(tmp_path) -> None:
    from strongtowns_detroit.graphics import GraphicBuildSystem

    project_root = tmp_path / "graphics"
    for name in ("first", "second"):
        definition = project_root / "src" / "definitions" / f"{name}.py"
        definition.parent.mkdir(parents=True, exist_ok=True)
        definition.write_text(
            "from strongtowns_detroit.graphics import (\n"
            "    Graphic, SvgComponent, graphic_definition,\n"
            ")\n"
            f"@graphic_definition({name!r})\n"
            f"def build(): return {{{name!r}: "
            f"Graphic({name.title()!r}, SvgComponent('<g/>', 1, 1))}}\n",
            encoding="utf-8",
        )
    system = GraphicBuildSystem(
        project_root,
        formats=(GraphicFormat.INSTAGRAM_POST,),
        artifact_formats=("svg",),
    )
    system.build()

    system.build(sources=["first"])

    manifest = json.loads(
        (project_root / "output" / "instagram" / "manifest.json").read_text()
    )
    assert [entry["source"] for entry in manifest["graphics"]] == [
        "first",
        "second",
    ]
