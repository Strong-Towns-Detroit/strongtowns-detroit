"""Tests for compare_networks() from osmnx_detroit_simplification_enhanced.py."""
from unittest.mock import MagicMock
import pytest

from strongtowns_detroit.geo.streets import compare_networks


def _make_mock_graph(num_nodes, num_edges):
    """Create a mock graph with specified node/edge counts."""
    g = MagicMock()
    g.nodes = list(range(num_nodes))
    g.edges = list(range(num_edges))
    return g


class TestCompareNetworks:
    def test_reduction_percentages(self):
        original = _make_mock_graph(1000, 2000)
        simplified = _make_mock_graph(500, 1200)

        result = compare_networks(original, simplified)

        assert result["original_nodes"] == 1000
        assert result["original_edges"] == 2000
        assert result["simplified_nodes"] == 500
        assert result["simplified_edges"] == 1200
        assert result["node_reduction_pct"] == pytest.approx(50.0)
        assert result["edge_reduction_pct"] == pytest.approx(40.0)

    def test_no_reduction(self):
        original = _make_mock_graph(100, 200)
        simplified = _make_mock_graph(100, 200)

        result = compare_networks(original, simplified)

        assert result["node_reduction_pct"] == pytest.approx(0.0)
        assert result["edge_reduction_pct"] == pytest.approx(0.0)
