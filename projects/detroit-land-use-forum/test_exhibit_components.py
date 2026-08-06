from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from exhibit_components import (  # noqa: E402
    LegendItem,
    forum_css,
    ghost_hatch_pattern,
    html_document,
    map_frame,
    metric_block,
    source_lines,
    swatch_legend,
    title_block,
)


def test_title_and_source_text_are_escaped() -> None:
    block = title_block("Lots & widths", "A < B")
    footer = source_lines(["Source: A & B"])
    assert "Lots &amp; widths" in block
    assert "A &lt; B" in block
    assert "A &amp; B" in footer


def test_legend_is_composable_and_positioned() -> None:
    legend = swatch_legend(
        [LegendItem("Fails", "#c83a3a"), LegendItem("Meets", "#0c2340")],
        positions=(67, 345),
    )
    assert 'x="67"' in legend
    assert 'x="345"' in legend
    assert "Fails" in legend and "Meets" in legend


def test_map_frame_and_metric_sidebar_have_stable_guides() -> None:
    frame = map_frame("data:image/jpeg;base64,abc")
    metric = metric_block("69%", ["BELOW MINIMUM"], "200 of 300 parcels")
    assert 'x="48" y="205" width="1015" height="680"' in frame
    assert 'class="metric" x="1120" y="270"' in metric
    assert "200 of 300 parcels" in metric
    metric_without_detail = metric_block("97%", ["LESS TAX"], None)
    assert 'class="note"' not in metric_without_detail


def test_css_and_wireframe_expose_semantic_classes() -> None:
    css = forum_css(title_size=45, extra_sans=(".row-label",))
    pattern = ghost_hatch_pattern()
    assert ".title{font-size:45px" in css
    assert ".row-label" in css
    assert 'id="ghost-parking"' in pattern
    assert 'patternUnits="userSpaceOnUse"' in pattern


def test_html_wrapper_uses_requested_canvas() -> None:
    document = html_document(
        "Example", "<svg/>", width=1450, height=1100
    )
    assert "width:min(100%,1450px)" in document
    assert "size:14.5in 11in" in document
    assert "<main><svg/></main>" in document
