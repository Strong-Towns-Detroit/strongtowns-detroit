"""Fast, offline unit tests for the isochrone/accessibility core.

These tests exercise the shared primitives on tiny SYNTHETIC networkx graphs (no OSM
download), so they run in well under a second. They require the REAL osmnx (for
``add_edge_speeds`` / ``nearest_nodes`` / ``graph_to_gdfs``); when osmnx is mocked (the repo
root ``tests/conftest.py`` replaces it with a MagicMock) or absent, the whole module skips.

Run with the osmnx venv:

    PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python -m pytest \
        pipelines/isochrones/tests -q
"""

import warnings

import pytest

# Skip cleanly when osmnx is unavailable or mocked (the repo-root tests/conftest.py replaces
# it with a MagicMock). Guard BEFORE importing networkx/numpy/the core so a bare env that
# lacks these deps skips instead of erroring at collection.
ox = pytest.importorskip("osmnx")
if type(ox).__module__.split(".")[0] == "unittest":  # MagicMock stand-in
    pytest.skip("real osmnx required for isochrone tests", allow_module_level=True)

import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402

from strongtowns_detroit.geo.isochrones import (  # noqa: E402
    add_travel_times,
    isochrone_polygon,
    nearest_time_to_any,
    snap_points,
    travel_times_from,
)

# ── Synthetic graph builders ─────────────────────────────────────────
_LAT0, _LON0 = 42.3300, -83.0500  # near downtown Detroit; any real lat/lon works


def _oneway_graph():
    """Two nodes, a single directed edge 0 -> 1 (a one-way street)."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    G.add_node(0, x=_LON0, y=_LAT0)
    G.add_node(1, x=_LON0 + 0.001, y=_LAT0)
    G.add_edge(0, 1, key=0, length=100.0, travel_time=60.0)
    return G


def _chain_graph(n=15, length_m=200.0, maxspeed="30 mph"):
    """Bidirectional chain 0<->1<->...<->n along a latitude line, with OSM-ish tags."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    for i in range(n + 1):
        G.add_node(i, x=_LON0 + i * 0.002, y=_LAT0)
    for i in range(n):
        for u, v in ((i, i + 1), (i + 1, i)):
            G.add_edge(u, v, key=0, length=length_m,
                       highway="residential", maxspeed=maxspeed)
    return G


def _grid_graph(side=5, step=0.001, tt=30.0):
    """side x side grid, 4-neighbour bidirectional edges, uniform travel_time ``tt`` s."""
    G = nx.MultiDiGraph(crs="epsg:4326")

    def nid(r, c):
        return r * side + c

    for r in range(side):
        for c in range(side):
            G.add_node(nid(r, c), x=_LON0 + c * step, y=_LAT0 + r * step)
    for r in range(side):
        for c in range(side):
            for dr, dc in ((0, 1), (1, 0)):
                nr, nc = r + dr, c + dc
                if nr < side and nc < side:
                    a, b = nid(r, c), nid(nr, nc)
                    G.add_edge(a, b, key=0, length=100.0, travel_time=tt)
                    G.add_edge(b, a, key=0, length=100.0, travel_time=tt)
    return G


# ── 1. Reverse-Dijkstra primitive is genuinely directed ──────────────
def test_reverse_dijkstra_directed_on_oneway():
    G = _oneway_graph()

    # Origin 0 CAN reach destination 1 (edge points 0 -> 1).
    to_1 = nearest_time_to_any(G, dest_nodes=[1], query_nodes=[0, 1])
    assert to_1[0] == pytest.approx(60.0)
    assert to_1[1] == pytest.approx(0.0)

    # Origin 1 CANNOT reach destination 0 on a one-way street -> inf (asymmetry).
    to_0 = nearest_time_to_any(G, dest_nodes=[0], query_nodes=[0, 1])
    assert to_0[0] == pytest.approx(0.0)
    assert np.isinf(to_0[1])

    # Sanity: the raw forward primitive is also asymmetric.
    assert travel_times_from(G, [0]).get(1) == pytest.approx(60.0)
    assert 0 not in travel_times_from(G, [1])


# ── 2. Isochrone area is monotonic in the time budget ────────────────
def test_isochrone_area_monotonic_with_time():
    G = _grid_graph(side=6, tt=30.0)
    center = 6 * 3 + 3  # a middle node

    def area_km2(max_s):
        poly = isochrone_polygon(G, center, max_s, method="buffer")
        import geopandas as gpd
        gs = gpd.GeoSeries([poly], crs="EPSG:4326")
        return gs.to_crs(gs.estimate_utm_crs()).area.iloc[0] / 1e6

    a_small = area_km2(30)    # only immediate neighbours
    a_mid = area_km2(90)
    a_large = area_km2(1000)  # whole grid reachable
    assert a_small < a_mid < a_large


def test_smooth_isochrone_is_monotonic_and_close_to_buffer():
    G = _grid_graph(side=9, tt=30.0)
    center = 9 * 4 + 4

    def area_m2(max_s, method):
        import geopandas as gpd
        poly = isochrone_polygon(
            G, center, max_s, method=method, close_m=120,
            chaikin_iters=2, simplify_m=5,
        )
        gs = gpd.GeoSeries([poly], crs="EPSG:4326")
        return gs.to_crs(gs.estimate_utm_crs()).area.iloc[0]

    smooth = [area_m2(seconds, "smooth") for seconds in (30, 90, 1000)]
    baseline = [area_m2(seconds, "buffer") for seconds in (30, 90, 1000)]

    assert smooth[0] < smooth[1] < smooth[2]
    # Synthetic grids are denser and smaller than the real drive graph, so use broad
    # fidelity bounds here; the cached-network acceptance check provides real-world tuning.
    assert all(0.45 <= s / b <= 2.0 for s, b in zip(smooth, baseline))


def test_smooth_isochrone_handles_single_reachable_node():
    G = _oneway_graph()
    poly = isochrone_polygon(G, 1, 1, method="smooth")
    assert poly is not None
    assert not poly.is_empty
    assert poly.is_valid


# ── 3. walk < bike < drive reach ordering ────────────────────────────
def test_mode_reach_ordering():
    def reach_count(mode, cutoff_s=300.0):
        G = add_travel_times(_chain_graph(), mode)
        reached = travel_times_from(G, [0], cutoff_s=cutoff_s)
        return len(reached)

    n_walk = reach_count("walk")
    n_bike = reach_count("bike")
    n_drive = reach_count("drive")
    assert n_walk < n_bike < n_drive


# ── 4. Snap-distance guard warns beyond max_snap_m ───────────────────
def test_snap_guard_warns_beyond_threshold():
    G = _grid_graph(side=5)

    # A point right on a node snaps ~0 m: no warning.
    on_node = (_LAT0, _LON0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes an error
        nodes, dists = snap_points(G, [on_node], max_snap_m=1000.0, return_dist=True)
    assert dists[0] < 50.0
    assert len(nodes) == 1

    # A point ~5.5 km away (offset ~0.05 deg lat) snaps far: warning fires.
    far = (_LAT0 + 0.05, _LON0)
    with pytest.warns(UserWarning, match="outside the network boundary"):
        nodes2, dists2 = snap_points(G, [far], max_snap_m=1000.0, return_dist=True)
    assert dists2[0] > 1000.0

    # Guard disabled -> no warning even for the far point.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        snap_points(G, [far], max_snap_m=None)
