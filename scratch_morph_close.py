"""Prototype: morphological-closing isochrone polygon.

Dilate reachable edges by B metres, dissolve, then erode by B (a morphological
"closing") to fill inter-street gaps into a solid rounded blob; fill small holes;
light final round. Compare AREA to the honest 'buffer' baseline and to convex hull.
Renders a PNG for visual judging.
"""
from __future__ import annotations
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point, MultiPolygon, Polygon
from shapely.ops import unary_union

sys.path.insert(0, "/Users/johnbolt/strongtowns-detroit/src")
from strongtowns_detroit.geo.isochrones import (
    load_or_build_network, travel_times_from,
)

CACHE = "/Users/johnbolt/strongtowns-detroit/cache"
OUT = "/Users/johnbolt/strongtowns-detroit/output/proto_morphological-close.png"
POINT = (42.479124, -83.0847521)
DIST = 25000
CUTOFF_S = 600  # 10 minutes


def fill_holes(poly, max_hole_area):
    """Drop interior rings smaller than max_hole_area (keep genuine big voids)."""
    if poly.geom_type == "Polygon":
        polys = [poly]
    else:
        polys = list(poly.geoms)
    out = []
    for p in polys:
        keep = [r for r in p.interiors if Polygon(r).area >= max_hole_area]
        out.append(Polygon(p.exterior, keep))
    return out[0] if len(out) == 1 else MultiPolygon(out)


def morph_close_polygon(G, center_node, max_s, *, B=200.0,
                        hole_area_m2=None, drop_frac=0.02,
                        final_round_m=None, open_m=None, edge_buffer_m=25):
    """Morphological-closing isochrone.

    B          : closing radius (dilate +B then erode -B).
    hole_area_m2: interior rings smaller than this are filled (default = pi*B^2 * 4).
    drop_frac  : drop disconnected output pieces < drop_frac of the largest.
    final_round: optional +/- buffer for a last smoothing pass (default B*0.15).
    """
    reachable = travel_times_from(G, [center_node], cutoff_s=max_s)
    reachable_nodes = set(reachable)
    if not reachable_nodes:
        return None, None, None

    # local UTM in metres
    node_gdf = gpd.GeoDataFrame(
        {"node": list(reachable_nodes)},
        geometry=[Point(G.nodes[n]["x"], G.nodes[n]["y"]) for n in reachable_nodes],
        crs="EPSG:4326",
    )
    utm = node_gdf.estimate_utm_crs()
    node_gdf = node_gdf.to_crs(utm)

    # reachable EDGE geometries in UTM
    sub = G.subgraph(reachable_nodes)
    edges = ox.graph_to_gdfs(sub, nodes=False, edges=True)
    if edges.crs is None:
        edges = edges.set_crs("EPSG:4326")
    edges = edges.to_crs(utm)

    # --- honest buffer baseline (same as toolkit 'buffer') ---
    baseline = edges.geometry.buffer(edge_buffer_m).union_all()
    if baseline.is_empty:
        baseline = node_gdf.geometry.buffer(edge_buffer_m).union_all()

    # --- convex hull (overstatement reference) ---
    convex = node_gdf.geometry.union_all().convex_hull

    # --- morphological closing ---
    # dilate: buffer edges by B (round joins fill the street gaps)
    dilated = edges.geometry.buffer(B, join_style="round", cap_style="round").union_all()
    if dilated.is_empty:
        dilated = node_gdf.geometry.buffer(B).union_all()
    # erode: negative buffer by B -> back to true extent, gaps stay filled
    closed = dilated.buffer(-B, join_style="round", cap_style="round")

    # fill small holes (keep only genuinely large voids)
    if hole_area_m2 is None:
        hole_area_m2 = np.pi * B * B * 4.0
    if not closed.is_empty:
        closed = fill_holes(closed, hole_area_m2)

    # OPENING (erode O then dilate O): shaves thin tendrils/spikes and stair-step
    # nubs that the closing left. Unlike a closing this REMOVES area, pulling the
    # blob back toward the honest reach while smoothing convex detail.
    if open_m is None:
        open_m = B * 0.6
    if open_m > 0 and not closed.is_empty:
        opened = closed.buffer(-open_m, join_style="round").buffer(
            open_m, join_style="round")
        if not opened.is_empty:
            closed = opened
        # opening can re-open small holes; refill them
        if not closed.is_empty and closed.geom_type in ("Polygon", "MultiPolygon"):
            closed = fill_holes(closed, hole_area_m2)

    # final light rounding pass to shave any residual kinks
    if final_round_m is None:
        final_round_m = B * 0.15
    if final_round_m > 0 and not closed.is_empty:
        closed = closed.buffer(final_round_m, join_style="round").buffer(
            -final_round_m, join_style="round")

    # drop tiny disconnected islands
    if closed.geom_type == "MultiPolygon":
        parts = sorted(closed.geoms, key=lambda p: p.area, reverse=True)
        biggest = parts[0].area
        parts = [p for p in parts if p.area >= drop_frac * biggest]
        closed = parts[0] if len(parts) == 1 else MultiPolygon(parts)

    def to_wgs(g):
        return gpd.GeoSeries([g], crs=utm).to_crs("EPSG:4326").iloc[0]

    areas_km2 = {
        "morph": closed.area / 1e6,
        "buffer": baseline.area / 1e6,
        "convex": convex.area / 1e6,
    }
    geoms_wgs = {
        "morph": to_wgs(closed),
        "buffer": to_wgs(baseline),
        "convex": to_wgs(convex),
    }
    return geoms_wgs, areas_km2, (node_gdf.to_crs("EPSG:4326"), len(reachable_nodes))


def main():
    G = load_or_build_network(
        point=POINT, dist=DIST, mode="drive", cache_dir=CACHE,
        reuse_graphml=f"{CACHE}/pt_42_47912__83_08475_d25000_a3b03b6a_drive.graphml",
    )
    print("graph nodes", G.number_of_nodes(), "edges", G.number_of_edges())
    center = ox.distance.nearest_nodes(G, X=POINT[1], Y=POINT[0])

    B = float(os.environ.get("MORPH_B", 200.0))
    hole = os.environ.get("MORPH_HOLE")
    hole = float(hole) if hole else None
    fr = os.environ.get("MORPH_ROUND")
    fr = float(fr) if fr else None
    op = os.environ.get("MORPH_OPEN")
    op = float(op) if op else None
    import time
    t0 = time.time()
    geoms, areas, (nodes_wgs, nreach) = morph_close_polygon(
        G, center, CUTOFF_S, B=B, hole_area_m2=hole, final_round_m=fr, open_m=op)
    print(f"elapsed {time.time()-t0:.1f}s")

    m = geoms["morph"]
    parts = 1 if m.geom_type == "Polygon" else len(m.geoms)
    holes = sum(len(p.interiors) for p in ([m] if m.geom_type == "Polygon" else m.geoms))
    print(f"B={B} hole={hole} round={fr}  parts={parts} holes={holes}")
    print(f"B={B}  reachable_nodes={nreach}")
    for k, v in areas.items():
        print(f"  {k:8s} area = {v:8.3f} km^2")
    ratio = areas["morph"] / areas["buffer"]
    print(f"  morph/buffer = {ratio:.3f}   morph/convex = {areas['morph']/areas['convex']:.3f}")

    # --- render ---
    fig, ax = plt.subplots(figsize=(11, 11))
    # honest buffer reach as a LIGHT FILLED underlay (the street network footprint)
    gpd.GeoSeries([geoms["buffer"]], crs="EPSG:4326").plot(
        ax=ax, facecolor="#c62828", edgecolor="none", alpha=0.85, zorder=1)
    # reachable nodes (faint)
    nodes_wgs.plot(ax=ax, color="#333", markersize=0.6, alpha=0.35, zorder=2)

    # morph polygon: prominent translucent fill + bold outline (the deliverable)
    gpd.GeoSeries([geoms["morph"]], crs="EPSG:4326").plot(
        ax=ax, facecolor="#1f77b4", edgecolor="#0b3d63", alpha=0.32,
        linewidth=2.5, zorder=3)
    gpd.GeoSeries([geoms["morph"]], crs="EPSG:4326").boundary.plot(
        ax=ax, color="#0b3d63", linewidth=2.5, zorder=4)
    # convex hull outline
    gpd.GeoSeries([geoms["convex"]], crs="EPSG:4326").boundary.plot(
        ax=ax, color="#2ca02c", linewidth=1.2, linestyle="--", alpha=0.8, zorder=4)
    # center
    ax.plot(POINT[1], POINT[0], marker="*", color="black", markersize=18, zorder=5)

    ax.set_title(
        f"Morphological-closing isochrone (10 min drive, B={B:.0f} m)\n"
        f"morph={areas['morph']:.2f} km²  |  buffer baseline={areas['buffer']:.2f} km² "
        f"(ratio {ratio:.2f})  |  convex={areas['convex']:.2f} km²\n"
        f"blue = morph blob  ·  red fill = honest buffer reach  ·  green dashed = convex hull",
        fontsize=11)
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(OUT, dpi=130, bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
