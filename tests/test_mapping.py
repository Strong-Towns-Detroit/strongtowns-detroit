"""Tests for strongtowns_detroit.mapping (colors + layers)."""

import re
import pytest


# ── Color constants ──────────────────────────────────────────────────

class TestColors:
    """Verify color constants are valid hex and category lookups are consistent."""

    def test_all_hex_colors_valid(self):
        from strongtowns_detroit.mapping import colors

        hex_re = re.compile(r'^#[0-9A-Fa-f]{6}$')
        hex_attrs = [
            'WATER_FILL', 'WATER_EDGE', 'WATER_PARCEL',
            'STREET', 'BOUNDARY',
            'BUILDABLE', 'NOT_BUILDABLE',
            'SHORTAGE', 'ACCESSIBILITY_CRISIS', 'BOTH_ISSUES', 'NEUTRAL',
        ]
        for name in hex_attrs:
            val = getattr(colors, name)
            assert hex_re.match(val), f"{name}={val!r} is not a valid hex color"

    def test_housing_category_colors_keys(self):
        from strongtowns_detroit.mapping.colors import HOUSING_CATEGORY_COLORS

        expected_keys = {'Neither', 'Shortage Only', 'Accessibility Only', 'Both Issues', 'No Data'}
        assert set(HOUSING_CATEGORY_COLORS.keys()) == expected_keys

    def test_shortage_colors_boolean_keys(self):
        from strongtowns_detroit.mapping.colors import SHORTAGE_COLORS, ACCESSIBILITY_COLORS

        assert True in SHORTAGE_COLORS
        assert False in SHORTAGE_COLORS
        assert True in ACCESSIBILITY_COLORS
        assert False in ACCESSIBILITY_COLORS

    def test_z_order_ascending(self):
        from strongtowns_detroit.mapping.colors import Z_WATER, Z_DATA, Z_STREETS, Z_BOUNDARY

        assert Z_WATER < Z_DATA < Z_STREETS < Z_BOUNDARY

    def test_burden_bins_sorted(self):
        from strongtowns_detroit.mapping.colors import BURDEN_BINS

        assert BURDEN_BINS == sorted(BURDEN_BINS)
        assert len(BURDEN_BINS) == 5

    def test_alpha_in_range(self):
        from strongtowns_detroit.mapping.colors import ALPHA_BLOCKGROUPS

        assert 0.0 < ALPHA_BLOCKGROUPS <= 1.0


# ── Layer rendering ──────────────────────────────────────────────────

class TestMakePatchLegend:
    """Test the legend helper (lightweight — no GeoDataFrame needed)."""

    def test_returns_legend(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from strongtowns_detroit.mapping.layers import make_patch_legend

        fig, ax = plt.subplots()
        legend = make_patch_legend(ax, [
            ('#ff0000', 'Red'),
            ('#00ff00', 'Green'),
        ])
        assert legend is not None
        assert len(legend.get_texts()) == 2
        plt.close(fig)

    def test_empty_pairs(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from strongtowns_detroit.mapping.layers import make_patch_legend

        fig, ax = plt.subplots()
        legend = make_patch_legend(ax, [])
        assert legend is not None
        assert len(legend.get_texts()) == 0
        plt.close(fig)

    def test_alpha_forwarded(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from strongtowns_detroit.mapping.layers import make_patch_legend

        fig, ax = plt.subplots()
        legend = make_patch_legend(ax, [('#ff0000', 'Red')], alpha=0.5)
        patch = legend.get_patches()[0]
        assert patch.get_alpha() == 0.5
        plt.close(fig)


class TestAddGeographyLayers:
    """Test geographic layer rendering with minimal mock GeoDataFrames."""

    @pytest.fixture
    def simple_gdfs(self):
        """Create tiny GeoDataFrames for testing."""
        import geopandas as gpd
        from shapely.geometry import box, LineString, Polygon

        crs = 'EPSG:4326'
        boundary = gpd.GeoDataFrame(
            {'geometry': [box(-83.3, 42.25, -82.9, 42.45)]}, crs=crs,
        )
        water = gpd.GeoDataFrame(
            {'geometry': [box(-83.1, 42.3, -83.0, 42.35)]}, crs=crs,
        )
        edges = gpd.GeoDataFrame(
            {'geometry': [LineString([(-83.2, 42.3), (-83.0, 42.4)])]}, crs=crs,
        )
        ref = gpd.GeoDataFrame(
            {'geometry': [box(-83.3, 42.25, -82.9, 42.45)]}, crs=crs,
        )
        return boundary, water, edges, ref

    def test_renders_all_layers(self, simple_gdfs):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from strongtowns_detroit.mapping.layers import add_geography_layers

        boundary, water, edges, ref = simple_gdfs
        fig, ax = plt.subplots()
        add_geography_layers(ax, boundary, water, edges, ref)
        # Should have rendered without error; check children exist
        assert len(ax.get_children()) > 0
        plt.close(fig)

    def test_handles_none_layers(self, simple_gdfs):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from strongtowns_detroit.mapping.layers import add_geography_layers

        _, _, _, ref = simple_gdfs
        fig, ax = plt.subplots()
        # All None — should not raise
        add_geography_layers(ax, None, None, None, ref)
        plt.close(fig)

    def test_no_clip(self, simple_gdfs):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from strongtowns_detroit.mapping.layers import add_geography_layers

        boundary, water, edges, ref = simple_gdfs
        fig, ax = plt.subplots()
        add_geography_layers(ax, boundary, water, edges, ref, clip_to_bounds=False)
        plt.close(fig)

    def test_custom_colors(self, simple_gdfs):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from strongtowns_detroit.mapping.layers import add_geography_layers

        boundary, water, edges, ref = simple_gdfs
        fig, ax = plt.subplots()
        add_geography_layers(
            ax, boundary, water, edges, ref,
            water_color='#ff0000',
            street_color='#00ff00',
            boundary_color='#0000ff',
        )
        plt.close(fig)
