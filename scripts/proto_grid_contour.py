"""Prototype: grid + iso-contour isochrone polygon (ORS-like smooth filled blob).

WHY THE OBVIOUS VERSION FAILS (measured, see report):
  Interpolating the node travel-times with griddata and contouring at max_s reproduces the
  CONVEX HULL -- inside the node cloud's hull the linear interpolant is < max_s everywhere,
  so the max_s contour is the hull boundary. Network shape has to be injected separately by
  masking cells that are too far from the reachable network. Masking on distance-to-nearest
  -NODE fails too: node spacing is ~90 m in the core but kilometres along freeways, so any
  single radius either fragments the fringe tentacles (r=60 -> 62 parts, covers only 38% of
  the honest buffer) or balloons the core (r=130 -> 2.0x the buffer area). And Gaussian
  blur + 0.5 threshold ERASES thin ribbons (a 160 m-wide freeway ribbon blurred at sigma=100
  never reaches 0.5), which is what drove coverage down.

THE METHOD THAT WORKS -- distance-to-EDGE field + exact-disk morphological closing:
  1. Reachable set: travel_times_from(G, [center], cutoff_s) -> {node: seconds}.
  2. Take the reachable subgraph's EDGE geometries (continuous road centrelines -- dense in
     the core AND continuous along freeways, which is exactly what node points are not),
     project to local UTM, segmentize to ~SAMPLE_M, and build a cKDTree over the samples.
  3. Rasterize D = distance from each grid cell to the nearest reachable road centreline.
  4. Fill the blocks WITHOUT inflating the outer edge, via a morphological CLOSING of the
     road footprint {D <= r} by radius c. Closing = dilate-then-erode; it is an increasing
     operator, so it can only ADD area, it never erases a thin freeway ribbon, and its outer
     boundary returns to where it started -- it fills only concavities narrower than 2c
     (i.e. street blocks). Because dilating {D<=r} by c is just {D <= r+c}, the whole closing
     collapses to ONE exact-disk erosion via a Euclidean distance transform:
         A = (D <= r + c);   closed = EDT(A) > c
     which is O(cells) and needs no structuring element.
  5. Round the remaining corners with a MILD Gaussian on the now-thick field (sigma << c, so
     nothing thin is destroyed) and contour at 0.5.
  6. Polygonize with even-odd fill so interior rings become HOLES, drop specks, simplify.

Net effect: the boundary sits ~r metres outside the outermost reachable road (honest), block
interiors are filled (smooth blob, no street-hair), freeway tentacles survive intact, and the
area lands near the honest buffer baseline rather than the convex hull.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import osmnx as ox
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter, distance_transform_edt

sys.path.insert(0, "/Users/johnbolt/strongtowns-detroit/src")
from strongtowns_data.geo.isochrones import (
    load_or_build_network, travel_times_from, isochrone_polygon,
)

CACHE = "/Users/johnbolt/strongtowns-detroit/cache"
REUSE = f"{CACHE}/pt_42_47912__83_08475_d25000_a3b03b6a_drive.graphml"
CENTER_LATLON = (42.479124, -83.0847521)  # Madison Heights
MAX_S = 600.0  # 10 minutes
OUT_PNG = "/Users/johnbolt/strongtowns-detroit/output/proto_grid-contour.png"

# ---- tunables ----
CELL_M = 25.0        # raster resolution (metres)
SAMPLE_M = 20.0      # centreline densification step for the KD-tree
ROAD_R_M = 40.0      # half-width of the honest road footprint -> sets the outer boundary
CLOSE_M = 130.0      # closing radius: fills street blocks narrower than 2*CLOSE_M
SIGMA_M = 45.0       # mild corner-rounding Gaussian (keep << CLOSE_M)
SIMPLIFY_M = 12.0
MIN_AREA_FRAC = 0.004   # drop islands below this fraction of the main blob
MIN_HOLE_FRAC = 0.0015  # drop pinprick holes


# ── core ────────────────────────────────────────────────────────────────
def edge_samples(G, reachable_nodes, utm, sample_m=SAMPLE_M):
    """Dense (x, y) samples along every reachable road centreline, in UTM metres."""
    sub = G.subgraph(reachable_nodes)
    edges = ox.graph_to_gdfs(sub, nodes=False, edges=True)
    if edges.crs is None:
        edges = edges.set_crs("EPSG:4326")
    geom = edges.to_crs(utm).geometry
    geom = geom.segmentize(sample_m)  # shapely 2.x: insert vertices every sample_m
    coords = geom.get_coordinates()
    return coords[["x", "y"]].to_numpy()


def distance_field(samples, *, cell_m, pad_m):
    """Rasterize D = distance to the nearest road centreline sample."""
    minx, maxx = samples[:, 0].min() - pad_m, samples[:, 0].max() + pad_m
    miny, maxy = samples[:, 1].min() - pad_m, samples[:, 1].max() + pad_m
    nx_ = max(2, int(np.ceil((maxx - minx) / cell_m)) + 1)
    ny_ = max(2, int(np.ceil((maxy - miny) / cell_m)) + 1)
    gx = minx + np.arange(nx_) * cell_m
    gy = miny + np.arange(ny_) * cell_m
    GX, GY = np.meshgrid(gx, gy)
    tree = cKDTree(samples)
    d, _ = tree.query(np.column_stack([GX.ravel(), GY.ravel()]), workers=-1)
    return GX, GY, d.reshape(GX.shape)


def contour_polys(GX, GY, F, level):
    """Extract the `level` contour and polygonize every closed ring."""
    fig = plt.figure()
    cs = plt.contour(GX, GY, F, levels=[level])
    plt.close(fig)
    polys = []
    for path in cs.get_paths():
        v, codes = path.vertices, path.codes
        if codes is None:
            rings = [v]
        else:
            rings, start = [], 0
            for i, c in enumerate(codes):
                if c == 1 and i > start:  # MOVETO starts a new subpath
                    rings.append(v[start:i])
                    start = i
            rings.append(v[start:])
        for r in rings:
            if len(r) < 4:
                continue
            p = Polygon(r)
            if not p.is_valid:
                p = p.buffer(0)
            if p.is_empty or p.area == 0:
                continue
            polys.append(p)
    return polys


def assemble(polys):
    """Even-odd fill: XOR rings largest-first so nested rings become holes."""
    if not polys:
        return None
    polys = sorted(polys, key=lambda p: p.area, reverse=True)
    geom = polys[0]
    for p in polys[1:]:
        geom = geom.symmetric_difference(p)
    if geom.is_empty:
        geom = unary_union(polys)
    return geom.buffer(0)


def cleanup(geom, *, simplify_m, min_area_frac, min_hole_frac):
    """Drop specks/pinpricks and lightly simplify. No buffering -> no area inflation."""
    parts = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    main = max(p.area for p in parts)
    kept = []
    for p in parts:
        if p.area < min_area_frac * main:
            continue
        holes = [r for r in p.interiors if Polygon(r).area >= min_hole_frac * main]
        kept.append(Polygon(p.exterior, holes))
    geom = MultiPolygon(kept) if len(kept) > 1 else kept[0]
    return geom.simplify(simplify_m).buffer(0)


def isochrone_grid_contour(D, GX, GY, *, cell_m=CELL_M, road_r=ROAD_R_M, close_m=CLOSE_M,
                           sigma_m=SIGMA_M, simplify_m=SIMPLIFY_M,
                           min_area_frac=MIN_AREA_FRAC, min_hole_frac=MIN_HOLE_FRAC):
    """THE METHOD. D = distance-to-road raster; returns a shapely polygon in the same CRS."""
    # Morphological closing of {D <= road_r} by close_m, done exactly via one EDT.
    # dilate({D<=r}, c) == {D <= r+c}; then erode by c.
    A = D <= (road_r + close_m)
    if close_m > 0:
        eroded = distance_transform_edt(A, sampling=cell_m) > close_m
    else:
        eroded = A
    F = eroded.astype(np.float32)
    # mild rounding on the already-thick field
    if sigma_m > 0:
        F = gaussian_filter(F, sigma=sigma_m / cell_m, mode="constant", cval=0.0)
    polys = contour_polys(GX, GY, F, 0.5)
    geom = assemble(polys)
    if geom is None or geom.is_empty:
        return None
    return cleanup(geom, simplify_m=simplify_m, min_area_frac=min_area_frac,
                   min_hole_frac=min_hole_frac)


# ── driver ──────────────────────────────────────────────────────────────
def describe(g):
    parts = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
    return len(parts), sum(len(p.interiors) for p in parts)


def main():
    print("loading network ...")
    G = load_or_build_network(point=CENTER_LATLON, dist=25000, mode="drive",
                              cache_dir=CACHE, reuse_graphml=REUSE)
    center = ox.distance.nearest_nodes(G, X=CENTER_LATLON[1], Y=CENTER_LATLON[0])
    print(f"center node {center}; graph {G.number_of_nodes()} nodes")

    t0 = time.perf_counter()
    reach = travel_times_from(G, [center], cutoff_s=MAX_S)
    t_dijkstra = time.perf_counter() - t0
    print(f"reachable nodes within {MAX_S:.0f}s: {len(reach)}  ({t_dijkstra:.2f}s dijkstra)")

    node_gdf = gpd.GeoDataFrame(
        geometry=[Point(G.nodes[n]["x"], G.nodes[n]["y"]) for n in reach], crs="EPSG:4326")
    utm = node_gdf.estimate_utm_crs()
    node_gdf = node_gdf.to_crs(utm)
    xs = node_gdf.geometry.x.to_numpy()
    ys = node_gdf.geometry.y.to_numpy()

    # baselines
    buf_wgs = isochrone_polygon(G, center, MAX_S, method="buffer")
    conv_wgs = isochrone_polygon(G, center, MAX_S, method="convex")
    buf_utm = gpd.GeoSeries([buf_wgs], crs="EPSG:4326").to_crs(utm).iloc[0]
    conv_utm = gpd.GeoSeries([conv_wgs], crs="EPSG:4326").to_crs(utm).iloc[0]
    buf_area, conv_area = buf_utm.area / 1e6, conv_utm.area / 1e6
    print(f"buffer baseline: {buf_area:.2f} km^2   convex: {conv_area:.2f} km^2")

    t0 = time.perf_counter()
    samples = edge_samples(G, set(reach), utm)
    GX, GY, D = distance_field(samples, cell_m=CELL_M, pad_m=ROAD_R_M + CLOSE_M + 4 * CELL_M)
    t_field = time.perf_counter() - t0
    print(f"{len(samples)} centreline samples; grid {D.shape} ({t_field:.2f}s)")

    if os.environ.get("SWEEP"):
        for rr in (25, 40, 55):
            for cc in (90, 130, 170):
                g = isochrone_grid_contour(D, GX, GY, road_r=rr, close_m=cc)
                a = g.area / 1e6
                np_, nh = describe(g)
                cov = g.intersection(buf_utm).area / buf_utm.area
                print(f"  road_r={rr:3d} close={cc:3d} -> {a:7.2f} km^2  "
                      f"ratio {a/buf_area:.3f}  cover {cov:.3f}  parts={np_} holes={nh}")
        return

    t0 = time.perf_counter()
    proto = isochrone_grid_contour(D, GX, GY)
    t_poly = time.perf_counter() - t0
    area = proto.area / 1e6
    np_, nh = describe(proto)
    cov = proto.intersection(buf_utm).area / buf_utm.area
    print(f"prototype: {area:.2f} km^2  ratio-to-buffer {area/buf_area:.3f}  "
          f"covers {cov*100:.1f}% of buffer  parts={np_} holes={nh}  ({t_poly:.2f}s)")

    # ---- render ----
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.scatter(xs, ys, s=1.0, c="#9aa0a6", alpha=0.45, zorder=1, label="reachable nodes")

    def outline(g, color, lw, label, z, ls="-"):
        parts = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
        first = True
        for p in parts:
            ax.plot(*p.exterior.xy, color=color, lw=lw, ls=ls, zorder=z,
                    label=label if first else None)
            for r in p.interiors:
                ax.plot(*r.xy, color=color, lw=lw * 0.8, ls="--", zorder=z)
            first = False

    for p in (list(proto.geoms) if isinstance(proto, MultiPolygon) else [proto]):
        ax.fill(*p.exterior.xy, color="#2a9d8f", alpha=0.28, zorder=2)
        for r in p.interiors:
            ax.fill(*r.xy, color="white", alpha=1.0, zorder=2.1)
    outline(proto, "#1d7870", 2.4, "prototype (grid + contour)", 5)
    outline(buf_utm, "#e76f51", 0.8, "buffer baseline (honest)", 3)
    outline(conv_utm, "#264653", 1.2, "convex hull (overstates)", 4, ls=":")

    ax.set_aspect("equal")
    ax.set_title(
        "Grid distance-field + iso-contour isochrone — 10-min drive, Madison Heights MI\n"
        f"prototype {area:.1f} km²   vs buffer baseline {buf_area:.1f} km² "
        f"(ratio {area/buf_area:.2f}, covers {cov*100:.0f}%)   vs convex hull {conv_area:.1f} km²\n"
        f"cell={CELL_M:.0f}m  road_r={ROAD_R_M:.0f}m  close={CLOSE_M:.0f}m  sigma={SIGMA_M:.0f}m",
        fontsize=11)
    ax.legend(loc="upper right", framealpha=0.92, markerscale=8)
    ax.set_xlabel("UTM easting (m)")
    ax.set_ylabel("UTM northing (m)")
    fig.savefig(OUT_PNG, dpi=130, bbox_inches="tight")
    print(f"wrote {OUT_PNG}")
    print(f"SUMMARY proto_km2={area:.4f} buffer_km2={buf_area:.4f} convex_km2={conv_area:.4f} "
          f"nodes={len(reach)} parts={np_} holes={nh} cover={cov:.4f} "
          f"t_dijkstra={t_dijkstra:.2f} t_field={t_field:.2f} t_poly={t_poly:.2f}")


if __name__ == "__main__":
    main()
