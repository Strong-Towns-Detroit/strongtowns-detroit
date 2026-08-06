"""Reusable travel-time / isochrone accessibility toolkit.

Place-parameterized and mode-parameterized (drive / walk / bike), Detroit-agnostic.
One shared core (network build + cache, travel-time labeling, the many-origins ->
nearest-of-many-destinations primitive, isochrone polygons) powers three applications:

    1. generate_isochrones  -- reachability polygons from origin point(s).
    2. walkability_score     -- score points by travel-time access to amenities.
    3. warehouse_siting      -- rank candidate sites by drive time to destinations.

Conventions follow the rest of the repo: GeoDataFrame in / out, CRS handled via
geo.loader.sync_crs, GPKG writes via geo.streets.save_layer, maps via
mapping.layers.add_geography_layers + mapping.colors.

OSMnx 2.x API only (features_from_*, ox.routing.*, ox.distance.nearest_nodes).

Key correctness notes (see also the module-level gotchas in the design):
  * Drive graphs are DIRECTED (one-way streets): time(A->B) != time(B->A). The shared
    ``nearest_time_to_any`` primitive therefore runs multi-source Dijkstra FROM the
    destinations on the REVERSED graph, so the result is genuinely origin->destination
    time. Getting this backwards returns plausible-but-wrong numbers.
  * Walk/bike graphs must NOT trust OSM ``maxspeed`` (those are car limits). We force a
    uniform speed before computing travel times.
  * Unreached nodes come back as +inf -- callers floor scores to 0 / surface as
    ``n_unreached`` rather than dropping them.
"""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox

# ── Mode configuration ───────────────────────────────────────────────
# Walk / bike: OSM maxspeed tags are meaningless (they are car speed limits), so we
# force a uniform edge speed. Drive is omitted -> trust OSM maxspeed via add_edge_speeds.
MODE_SPEEDS_KPH = {'walk': 4.8, 'bike': 15.0}
VALID_MODES = ('drive', 'walk', 'bike')


# ── Network build + cache ────────────────────────────────────────────
def _slug(place=None, point=None, dist=None) -> str:
    """Stable filename slug for a place string/list or a point+dist query."""
    if place is not None:
        key = place if isinstance(place, str) else '+'.join(place)
    else:
        key = f"pt_{point[0]:.5f}_{point[1]:.5f}_d{int(dist)}"
    # keep it readable but bounded; hash the tail to avoid collisions / bad chars
    safe = ''.join(c if c.isalnum() else '_' for c in key)[:60]
    h = hashlib.sha1(key.encode()).hexdigest()[:8]
    return f"{safe}_{h}"


def add_travel_times(G, mode):
    """Annotate every edge with a ``travel_time`` (seconds) attribute.

    drive     -> ox.routing.add_edge_speeds (reads OSM maxspeed) then add_edge_travel_times.
    walk/bike -> force uniform speed_kph = MODE_SPEEDS_KPH[mode] BEFORE add_edge_travel_times
                 (do NOT trust car maxspeed tags on a walk/bike network).
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    if mode == 'drive':
        G = ox.routing.add_edge_speeds(G)
    else:
        speed = MODE_SPEEDS_KPH[mode]
        for _, _, data in G.edges(data=True):
            data['speed_kph'] = speed
    G = ox.routing.add_edge_travel_times(G)
    return G


def build_network(place=None, *, point=None, dist=None, mode='drive', simplify=True):
    """Download an OSM network and label it with travel times.

    Provide EITHER ``place`` (str or list[str]) OR ``point=(lat, lon)`` + ``dist`` (metres).
    Returns an UNprojected (EPSG:4326) MultiDiGraph with an edge ``travel_time`` (seconds).
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    if place is None and point is None:
        raise ValueError("provide either place= or point=+dist=")
    if point is not None and dist is None:
        raise ValueError("point= requires dist= (metres)")

    if place is not None:
        G = ox.graph_from_place(place, network_type=mode, simplify=simplify)
    else:
        lat, lon = point
        G = ox.graph_from_point((lat, lon), dist=dist, network_type=mode, simplify=simplify)

    return add_travel_times(G, mode)


def load_or_build_network(place=None, *, point=None, dist=None, mode='drive',
                          cache_dir='./cache', reuse_graphml=None):
    """Return a travel-time-labeled network, using a graphml cache when possible.

    Cache key = f"{slug(place|point)}_{mode}.graphml" under ``cache_dir``.

    ``reuse_graphml`` : optional path to a pre-downloaded graph (e.g. the repo's cached
    Detroit DRIVE graph). It is a *Detroit-only speed shortcut* and is honored ONLY when
    BOTH (a) ``mode='drive'`` (walk/bike need their own network topology and cannot reuse a
    drive graph) AND (b) the requested point/place actually falls inside that graph's node
    bounding box. If the requested location is OUTSIDE the reuse graph (e.g. a Columbus OH
    drive query against the Detroit graph), the reuse graphml is IGNORED with a warning and
    the correct network is built for the requested place/mode. This prevents silently
    returning (and caching under the wrong key) the wrong city's network.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{_slug(place, point, dist)}_{mode}.graphml"

    if cache_path.exists():
        G = ox.load_graphml(cache_path)
        if not _has_travel_times(G):
            G = add_travel_times(G, mode)
        return G

    if reuse_graphml is not None and mode == 'drive' and Path(reuse_graphml).exists():
        Greuse = ox.load_graphml(reuse_graphml)
        min_lon, min_lat, max_lon, max_lat = _graph_node_bbox(Greuse)
        ll = _query_lonlat(place, point)
        inside = (ll is not None
                  and min_lon <= ll[0] <= max_lon
                  and min_lat <= ll[1] <= max_lat)
        if inside:
            G = Greuse
            if not _has_travel_times(G):
                G = add_travel_times(G, mode)
            # Persist under the canonical cache key so subsequent runs are fast.
            ox.save_graphml(G, cache_path)
            return G
        where = f"point {tuple(point)}" if point is not None else f"place {place!r}"
        warnings.warn(
            f"reuse_graphml {str(reuse_graphml)!r} does NOT cover the requested {where} "
            f"(reuse-graph node bbox lon[{min_lon:.4f},{max_lon:.4f}] "
            f"lat[{min_lat:.4f},{max_lat:.4f}]); ignoring it and building the correct "
            f"'{mode}' network for the requested location.",
            stacklevel=2,
        )
        # fall through to a real build below.

    G = build_network(place, point=point, dist=dist, mode=mode)
    ox.save_graphml(G, cache_path)
    return G


def _graph_node_bbox(G):
    """(min_lon, min_lat, max_lon, max_lat) over a graph's node x/y coordinates."""
    xs = [d['x'] for _, d in G.nodes(data=True)]
    ys = [d['y'] for _, d in G.nodes(data=True)]
    return min(xs), min(ys), max(xs), max(ys)


def _query_lonlat(place=None, point=None):
    """Best-effort (lon, lat) for a query, used for reuse-graph containment checks.

    ``point`` -> exact (lon, lat). ``place`` -> geocoded centroid (a network call). Returns
    ``None`` if a place string cannot be geocoded, in which case the caller conservatively
    declines to reuse a provided graphml and builds the network fresh instead.
    """
    if point is not None:
        lat, lon = point
        return float(lon), float(lat)
    q = place if isinstance(place, str) else place[0]
    try:
        lat, lon = ox.geocode(q)
        return float(lon), float(lat)
    except Exception:  # noqa: BLE001 -- geocode may fail offline / on an unknown place
        return None


def _has_travel_times(G) -> bool:
    for _, _, data in G.edges(data=True):
        return 'travel_time' in data
    return False


# ── OSM context (water etc.) for map underlays ───────────────────────
_WATER_TAGS = {
    'natural': ['water', 'bay', 'strait', 'wetland'],
    'water': True,
    'waterway': ['river', 'canal', 'stream', 'riverbank'],
    'landuse': ['reservoir', 'basin'],
}


def fetch_water(place=None, *, point=None, dist=None, tags=_WATER_TAGS):
    """Fetch OSM water features for a region, to underlay isochrone maps.

    Supply the SAME region as the network (place OR point+dist). Returns a
    GeoDataFrame in EPSG:4326 (polygons for lakes/rivers, lines for waterways),
    or None if nothing is found / the query fails (water is optional context).
    """
    import osmnx as ox

    try:
        if point is not None:
            gdf = ox.features_from_point((point[0], point[1]), tags=tags, dist=dist)
        elif place is not None:
            gdf = ox.features_from_place(place, tags=tags)
        else:
            return None
    except Exception as e:  # noqa: BLE001 — water is best-effort context
        warnings.warn(f"fetch_water: no water features returned ({e})")
        return None
    if gdf is None or len(gdf) == 0:
        return None
    gdf = gdf[gdf.geometry.notna()]
    if gdf.crs is not None:
        gdf = gdf.to_crs('EPSG:4326')
    return gdf


# ── Node snapping ────────────────────────────────────────────────────
def snap_points(G, points, *, max_snap_m=1000.0, return_dist=False, label='point'):
    """Snap (lat, lon) coordinates to nearest graph nodes (single vectorized call).

    ``points`` : iterable of (lat, lon). Returns a list of node ids (parallel to input),
    or ``(nodes, dists_m)`` when ``return_dist=True`` where ``dists_m`` are the great-circle
    snap distances in metres (the graph is unprojected, so ox uses a haversine BallTree).

    ``max_snap_m`` : distance guard (metres). If any point snaps farther than this, emit a
    WARNING (not a hard error) naming the offending indices and distances. Without this a
    destination outside the network boundary (e.g. a suburb the graph does not cover) snaps
    to the nearest edge node and is silently reported reachable / within-threshold, so its
    travel time is understated. Pass ``max_snap_m=None`` to disable the check.

    Note: snapping introduces up to ~one-block error; an amenity nearer than the snap
    distance can read time 0, and a point across a barrier can snap to the wrong side.
    """
    pts = list(points)
    if not pts:
        return ([], []) if return_dist else []
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    nodes, dists = ox.distance.nearest_nodes(G, X=lons, Y=lats, return_dist=True)
    # nearest_nodes returns scalars for a single query, array-likes otherwise.
    if np.isscalar(nodes):
        nodes = [nodes]
        dists = [float(dists)]
    else:
        nodes = list(nodes)
        dists = [float(d) for d in dists]

    if max_snap_m is not None:
        far = [(i, dists[i]) for i in range(len(dists)) if dists[i] > max_snap_m]
        if far:
            detail = ', '.join(f"#{i} ({d:.0f} m)" for i, d in far)
            warnings.warn(
                f"{len(far)} {label}(s) snapped >{max_snap_m:.0f} m to the nearest network "
                f"node and may lie outside the network boundary (their travel times are "
                f"understated): {detail}",
                stacklevel=2,
            )
    if return_dist:
        return nodes, dists
    return nodes


# ── Core travel-time primitives ──────────────────────────────────────
def travel_times_from(G, source_nodes, *, cutoff_s=None):
    """Shortest travel time (seconds) FROM any of ``source_nodes`` to every reachable node.

    Multi-source Dijkstra on ``G`` as given. Returns {node: seconds}. Nodes beyond
    ``cutoff_s`` (or in a disconnected component) are simply absent from the dict.
    """
    sources = list(dict.fromkeys(source_nodes))  # de-dupe, preserve order
    return nx.multi_source_dijkstra_path_length(
        G, sources, cutoff=cutoff_s, weight='travel_time'
    )


def nearest_time_to_any(G, dest_nodes, query_nodes, *, cutoff_s=None):
    """THE SHARED PRIMITIVE: for each query node, travel time to its NEAREST destination.

    Correct for directed (one-way) drive graphs: we run multi-source Dijkstra FROM the
    destinations on ``G.reverse()``. On the reversed graph, dest->X equals X->dest on the
    original graph, i.e. genuine origin->destination time. Walk/bike graphs are effectively
    bidirectional but use the same code path.

    Complexity is O(one Dijkstra) regardless of how many query nodes there are -- this is
    what makes scoring 100k+ parcels tractable (never one Dijkstra per parcel).

    Returns a float ndarray parallel to ``query_nodes``; unreached -> np.inf (seconds).
    """
    Grev = G.reverse(copy=False)
    dist = nx.multi_source_dijkstra_path_length(
        Grev, list(dict.fromkeys(dest_nodes)), cutoff=cutoff_s, weight='travel_time'
    )
    return np.array([dist.get(q, np.inf) for q in query_nodes], dtype=float)


def time_matrix(G, source_nodes, target_nodes, *, cutoff_s=None):
    """Full (n_sources x n_targets) travel-time matrix in seconds.

    One Dijkstra per source (few sources assumed, e.g. candidate warehouse sites), each
    indexed at the targets. Unreached cells -> np.inf.
    """
    rows = []
    for s in source_nodes:
        dist = nx.single_source_dijkstra_path_length(
            G, s, cutoff=cutoff_s, weight='travel_time'
        )
        rows.append([dist.get(t, np.inf) for t in target_nodes])
    return np.array(rows, dtype=float)


# ── Isochrone polygons ───────────────────────────────────────────────
def isochrone_polygon(G, center_node, max_s, *, method='buffer',
                      edge_buffer_m=25, alpha=None, close_m=80,
                      chaikin_iters=2, simplify_m=15, min_area_frac=0.01):
    """Build a reachability polygon for travel time <= ``max_s`` seconds from a node.

    method='buffer' (default) : union of reachable EDGE geometries, buffered ~25 m in the
        local UTM projection then dissolved. This is the *honest* reach -- it follows the
        street network rather than filling unreachable gaps.
    method='alpha'  : concave (alpha) hull of reachable node points -- a smoother middle
        ground. Requires shapely 2.x ``concave_hull``.
    method='convex' : convex hull of reachable node points. OFFERED but OVERSTATES reach
        (bridges gaps the network never crosses); never the default.
    method='smooth' : morphologically close the reachable edges in local UTM, then use
        Chaikin corner cutting and simplification for a clean, classic isochrone outline.
        ``close_m`` controls how far gaps may be joined; tiny disconnected pieces smaller
        than ``min_area_frac`` of total area are discarded.

    Returns a shapely (Multi)Polygon in EPSG:4326.
    """
    import geopandas as gpd
    from shapely.geometry import Point
    valid_methods = {'buffer', 'alpha', 'convex', 'smooth'}
    if method not in valid_methods:
        raise ValueError(f"method must be one of {sorted(valid_methods)}, got {method!r}")
    if method == 'smooth':
        if close_m <= 0:
            raise ValueError("close_m must be positive")
        if chaikin_iters < 0:
            raise ValueError("chaikin_iters must be non-negative")
        if simplify_m < 0:
            raise ValueError("simplify_m must be non-negative")
        if not 0 <= min_area_frac < 1:
            raise ValueError("min_area_frac must be in [0, 1)")

    reachable = travel_times_from(G, [center_node], cutoff_s=max_s)
    reachable_nodes = set(reachable)
    if not reachable_nodes:
        return None

    # Work in a local UTM so buffers/hulls use metres.
    node_gdf = gpd.GeoDataFrame(
        {'node': list(reachable_nodes)},
        geometry=[Point(G.nodes[n]['x'], G.nodes[n]['y']) for n in reachable_nodes],
        crs='EPSG:4326',
    )
    utm = node_gdf.estimate_utm_crs()
    node_gdf = node_gdf.to_crs(utm)

    if method == 'convex':
        return _to_wgs84(node_gdf.geometry.union_all().convex_hull, utm)

    if method == 'alpha':
        pts = node_gdf.geometry.union_all()
        ratio = 0.4 if alpha is None else alpha
        try:
            hull = pts.concave_hull(ratio=ratio)
        except AttributeError:
            hull = pts.convex_hull
        return _to_wgs84(hull, utm)

    # Buffer and smooth both start from reachable edges. A one-node/tiny reachable set
    # has no edges, so fall back to buffered nodes instead of asking OSMnx to convert an
    # empty edge table.
    sub = G.subgraph(reachable_nodes)
    edges = None
    if sub.number_of_edges():
        edges = ox.graph_to_gdfs(sub, nodes=False, edges=True)
        if edges.crs is None:
            edges = edges.set_crs('EPSG:4326')
        edges = edges.to_crs(utm)

    if method == 'smooth':
        if edges is None or edges.empty:
            poly = node_gdf.geometry.buffer(edge_buffer_m).union_all()
        else:
            dilated = edges.geometry.buffer(
                close_m, join_style='round', cap_style='round'
            ).union_all()
            poly = dilated.buffer(-close_m, join_style='round')
            if poly.is_empty:
                poly = edges.geometry.buffer(edge_buffer_m).union_all()
        poly = _drop_slivers(poly, min_area_frac)
        poly = _smooth_rings(poly, chaikin_iters)
        poly = poly.simplify(simplify_m, preserve_topology=True)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return _to_wgs84(poly, utm)

    poly = (edges.geometry.buffer(edge_buffer_m).union_all()
            if edges is not None and not edges.empty else None)
    if poly is None or poly.is_empty:
        poly = node_gdf.geometry.buffer(edge_buffer_m).union_all()
    return _to_wgs84(poly, utm)


def _drop_slivers(geom, min_area_frac):
    """Discard tiny disconnected polygon pieces while retaining real islands."""
    from shapely.geometry import MultiPolygon

    if geom.is_empty or geom.geom_type != 'MultiPolygon' or min_area_frac <= 0:
        return geom
    total_area = geom.area
    parts = [part for part in geom.geoms
             if part.area >= min_area_frac * total_area]
    if not parts:
        parts = [max(geom.geoms, key=lambda part: part.area)]
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def _chaikin(coords, iterations):
    """Corner-cut a closed coordinate ring without expanding its envelope."""
    points = list(coords)
    if len(points) < 4 or iterations == 0:
        return points
    # Work without the duplicate closing coordinate, then explicitly close each result.
    points = points[:-1]
    for _ in range(iterations):
        refined = []
        for i, point in enumerate(points):
            nxt = points[(i + 1) % len(points)]
            refined.extend([
                (0.75 * point[0] + 0.25 * nxt[0],
                 0.75 * point[1] + 0.25 * nxt[1]),
                (0.25 * point[0] + 0.75 * nxt[0],
                 0.25 * point[1] + 0.75 * nxt[1]),
            ])
        points = refined
    return points + [points[0]]


def _smooth_rings(geom, iterations):
    """Apply Chaikin smoothing to every exterior and interior polygon ring."""
    from shapely.geometry import MultiPolygon, Polygon

    if geom.is_empty or iterations == 0:
        return geom

    def smooth_polygon(poly):
        exterior = _chaikin(poly.exterior.coords, iterations)
        interiors = [_chaikin(ring.coords, iterations) for ring in poly.interiors]
        return Polygon(exterior, interiors)

    if geom.geom_type == 'Polygon':
        return smooth_polygon(geom)
    if geom.geom_type == 'MultiPolygon':
        return MultiPolygon([smooth_polygon(poly) for poly in geom.geoms])
    return geom


def _to_wgs84(geom, src_crs):
    import geopandas as gpd
    return gpd.GeoSeries([geom], crs=src_crs).to_crs('EPSG:4326').iloc[0]


# ── Application A: amenity accessibility / walkability ────────────────
AMENITY_TAGS = {
    'grocery':    {'shop': ['supermarket', 'grocery', 'greengrocer']},
    'transit':    {'highway': 'bus_stop',
                   'railway': ['station', 'tram_stop', 'subway_entrance'],
                   'public_transport': ['platform', 'station']},
    'park':       {'leisure': ['park', 'garden', 'playground']},
    'school':     {'amenity': ['school', 'kindergarten']},
    'pharmacy':   {'amenity': 'pharmacy'},
    'restaurant': {'amenity': ['restaurant', 'cafe', 'fast_food']},
    # 'jobs' has NO OSM tag -- use LEHD LODES WAC instead; intentionally omitted.
}
DEFAULT_HALFLIFE_MIN = {'grocery': 5, 'transit': 5, 'park': 5,
                        'school': 10, 'pharmacy': 7, 'restaurant': 5}
DEFAULT_WEIGHTS = {'grocery': 3, 'transit': 2, 'park': 1,
                   'school': 2, 'pharmacy': 1, 'restaurant': 1}


def fetch_amenities(place_or_poly, category, *, tags=None):
    """Fetch amenity POINTS for one category as a GeoDataFrame (EPSG:4326).

    ``place_or_poly`` : a place string/list (-> features_from_place) or a shapely polygon
    (-> features_from_polygon). Polygon amenities (parks/schools) are reduced to centroids
    so everything snaps as a point.
    """
    tags = tags or AMENITY_TAGS
    if category not in tags or tags[category] is None:
        raise ValueError(f"no OSM tag mapping for category {category!r}")

    cat_tags = tags[category]
    if hasattr(place_or_poly, 'geom_type'):  # shapely geometry
        feats = ox.features_from_polygon(place_or_poly, tags=cat_tags)
    else:
        feats = ox.features_from_place(place_or_poly, tags=cat_tags)

    if len(feats) == 0:
        return feats
    feats = feats.reset_index()
    # Reduce polygons/lines to representative points.
    geom = feats.geometry
    pts = geom.copy()
    mask = geom.geom_type != 'Point'
    if mask.any():
        # representative_point() is always inside the polygon (centroid can fall outside).
        pts.loc[mask] = geom.loc[mask].representative_point()
    feats = feats.set_geometry(pts)
    feats = feats[feats.geometry.notna() & ~feats.geometry.is_empty]
    return feats.to_crs('EPSG:4326') if feats.crs else feats.set_crs('EPSG:4326')


def score_accessibility(points_gdf, G, *, categories, mode='walk',
                        place_or_poly=None,
                        halflife=None, weights=None, cutoff_min=None, decay='exp'):
    """Score each point by travel-time access to amenities. Returns an enriched copy.

    For each category: fetch amenities, snap them to the network, compute each point's
    travel time to the NEAREST amenity via ``nearest_time_to_any`` (ONE reverse-graph
    Dijkstra per category), convert to a 0-1 score via exponential decay
    (score = 0.5 ** (t / halflife)) or linear (max(0, 1 - t / cutoff)).

    Composite ``walkability_score`` (0-100) = 100 * sum(w_c * s_c) / sum(w_c) over the
    categories actually found. Also emits ``weakest_category`` so a location that is good
    on average but missing (say) grocery is visible, not hidden by the mean.

    Adds columns: time_<cat> (minutes), score_<cat> (0-1), walkability_score, weakest_category.
    Points are snapped ONCE and reused across all categories.
    """
    halflife = halflife or DEFAULT_HALFLIFE_MIN
    weights = weights or DEFAULT_WEIGHTS
    cutoff_s = cutoff_min * 60 if cutoff_min else None
    if place_or_poly is None:
        # Default the amenity search region to the points' convex hull (buffered a little).
        hull = points_gdf.to_crs('EPSG:4326').geometry.union_all().convex_hull
        place_or_poly = hull.buffer(0.02)  # ~2 km in degrees, generous margin

    out = points_gdf.copy()
    pts_wgs = out.to_crs('EPSG:4326')
    query_nodes = snap_points(G, [(geom.y, geom.x) for geom in pts_wgs.geometry])

    score_cols = {}
    used_weights = {}
    for cat in categories:
        try:
            amen = fetch_amenities(place_or_poly, cat)
        except Exception as exc:  # noqa: BLE001 -- category may be empty / unmapped
            print(f"  [warn] {cat}: {exc}")
            continue
        if amen is None or len(amen) == 0:
            print(f"  [warn] {cat}: 0 amenities found")
            continue
        amen_nodes = snap_points(G, [(g.y, g.x) for g in amen.geometry])
        t_sec = nearest_time_to_any(G, amen_nodes, query_nodes, cutoff_s=cutoff_s)
        t_min = t_sec / 60.0
        out[f'time_{cat}'] = t_min
        if decay == 'linear':
            tmax = cutoff_min or (halflife.get(cat, 5) * 4)
            s = np.clip(1.0 - t_min / tmax, 0.0, 1.0)
        else:  # exponential half-life decay (default)
            hl = halflife.get(cat, 5)
            s = np.where(np.isfinite(t_min), 0.5 ** (t_min / hl), 0.0)
        out[f'score_{cat}'] = s
        score_cols[cat] = s
        used_weights[cat] = weights.get(cat, 1)
        print(f"  {cat}: {len(amen)} amenities | "
              f"median access {np.nanmedian(t_min[np.isfinite(t_min)]):.1f} min")

    if score_cols:
        wsum = sum(used_weights.values())
        composite = sum(used_weights[c] * score_cols[c] for c in score_cols) / wsum
        out['walkability_score'] = 100.0 * composite
        stacked = np.vstack([score_cols[c] for c in score_cols])
        cats = list(score_cols)
        weakest_idx = np.argmin(stacked, axis=0)
        out['weakest_category'] = [cats[i] for i in weakest_idx]
    else:
        out['walkability_score'] = 0.0
        out['weakest_category'] = None
    return out


# ── Application B: warehouse siting ──────────────────────────────────
def site_destination_matrix(G, sites, destinations, *, cutoff_min=None,
                            max_snap_m=1000.0, return_snap=False):
    """(n_sites x n_destinations) drive-time matrix in MINUTES.

    ``sites`` / ``destinations`` : iterables of (lat, lon). One Dijkstra per site
    (few sites assumed) via ``time_matrix``. Unreached -> np.inf. Both sets are snapped with
    a ``max_snap_m`` guard (warns on points beyond it). When ``return_snap=True`` returns
    ``(M, site_snap_m, dest_snap_m)`` so callers can surface far-outside points.
    """
    cutoff_s = cutoff_min * 60 if cutoff_min else None
    site_nodes, site_snap = snap_points(G, sites, max_snap_m=max_snap_m,
                                        return_dist=True, label='site')
    dest_nodes, dest_snap = snap_points(G, destinations, max_snap_m=max_snap_m,
                                        return_dist=True, label='destination')
    M = time_matrix(G, site_nodes, dest_nodes, cutoff_s=cutoff_s) / 60.0
    if return_snap:
        return M, site_snap, dest_snap
    return M


def rank_sites(G, sites, destinations, *, site_ids=None, weights=None,
               threshold_min=30, objective='weighted_mean', cutoff_min=None,
               max_snap_m=1000.0):
    """Rank candidate sites by drive time to a set of destinations.

    Returns a pandas DataFrame with one row per site and NON-collapsible metrics so the
    Pareto tradeoff stays visible:
        max_time            worst-case destination (minutes)
        weighted_mean_time  volume-weighted typical time
        pct_within_threshold volume-weighted coverage within ``threshold_min``
        p90_time            90th-percentile time
        n_unreached         destinations with no route
        site_snap_m         how far the site itself snapped to the network (metres)

    ``weights`` : optional per-destination volumes (parallel to ``destinations``).
    ``objective`` in {'max', 'weighted_mean', 'pct_within'} sets the sort order only --
    every column is kept so a low-mean site with a terrible max is not silently preferred.
    ``max_snap_m`` : snap-distance guard -- sites/destinations that snap farther than this
    trigger a warning (destinations outside the network boundary would otherwise be reported
    reachable), and each site's own snap distance is surfaced in the ``site_snap_m`` column.
    """
    import pandas as pd

    dests = list(destinations)
    n_dest = len(dests)
    w = np.ones(n_dest) if weights is None else np.asarray(weights, dtype=float)
    if len(w) != n_dest:
        raise ValueError("weights must be parallel to destinations")

    M, site_snap, _dest_snap = site_destination_matrix(  # minutes
        G, sites, dests, cutoff_min=cutoff_min, max_snap_m=max_snap_m, return_snap=True)

    rows = []
    for i, row in enumerate(M):
        finite = np.isfinite(row)
        n_unreached = int((~finite).sum())
        wf = w[finite]
        rf = row[finite]
        wsum = wf.sum() if wf.sum() > 0 else 1.0
        within = (rf <= threshold_min)
        rows.append({
            'site_id': (site_ids[i] if site_ids is not None else i),
            'max_time': float(rf.max()) if finite.any() else np.inf,
            'weighted_mean_time': float((wf * rf).sum() / wsum) if finite.any() else np.inf,
            'pct_within_threshold': float(100.0 * (wf[within].sum() / w.sum())),
            'p90_time': float(np.percentile(rf, 90)) if finite.any() else np.inf,
            'n_unreached': n_unreached,
            'site_snap_m': round(float(site_snap[i]), 1),
        })
    df = pd.DataFrame(rows)

    sort_key = {'max': ('max_time', True),
                'weighted_mean': ('weighted_mean_time', True),
                'pct_within': ('pct_within_threshold', False)}[objective]
    # Push sites with unreached destinations toward the bottom regardless of objective.
    df = df.sort_values(
        by=['n_unreached', sort_key[0]], ascending=[True, sort_key[1]]
    ).reset_index(drop=True)
    return df
