# Hand-off: implement a "classic" smooth isochrone method

**For:** Codex (or any coding agent) picking up where a prior workflow left off.
**Status:** design + 3 prototypes DONE and judged; **implementation + verification NOT done**
(the prior run hit an account usage limit before the implement step).
**Goal:** add a new `method='smooth'` to `isochrone_polygon()` that produces a clean,
filled, *classic-looking* isochrone (à la OpenRouteService / Mapbox) that still **hugs the
true road-network reachable extent** — without the visual "street-hair" of the current
`buffer` method and without the area **overstatement** of the convex hull.

---

## 1. Context — what exists

Toolkit module: `src/strongtowns_detroit/geo/isochrones.py`
- `isochrone_polygon(G, center_node, max_s, *, method='buffer'|'alpha'|'convex', edge_buffer_m=25, alpha=None)`
  returns a shapely (Multi)Polygon in EPSG:4326. See lines ~319–373.
  - `buffer` (default): union of reachable **edge** geometries buffered ~25 m. **Honest reach**
    (follows streets) but looks like a filled street network — "hairy". This is the **area baseline**.
  - `alpha`: `shapely.concave_hull(ratio=…)` of reachable **node** points. Smoother, middle ground.
  - `convex`: convex hull. **Overstates** (bridges gaps the network never crosses). Never default.
- `travel_times_from(G, [center_node], cutoff_s=max_s) -> {node: seconds}` — the reachable set.
  Node coords: `G.nodes[n]['x']` = lon, `G.nodes[n]['y']` = lat.
- `build_network` / `load_or_build_network(place|point, dist, mode, cache_dir)` → travel-time-weighted MultiDiGraph.
- Helper `_to_wgs84(geom, utm_crs)` converts a UTM geometry back to EPSG:4326 (used by the existing methods).

CLI: `pipelines/isochrones/generate_isochrones.py` — has `--method {buffer,alpha,convex}` (add `smooth`).
Map rendering (`_plot`) already layers OSM street underlay + water + isochrones; no change needed there.

### Environment / how to run (IMPORTANT)
The repo-root venv lacks osmnx. Use the osmnx venv and set PYTHONPATH, running from the repo root:
```
cd /Users/johnbolt/strongtowns-detroit
PYTHONPATH=src pipelines/housingDataAnalysis/.venv/bin/python <script_or_-c>
```
Installed there: osmnx 2.0.6, shapely 2.1.2 (`shapely.concave_hull`, `.buffer`, `.simplify`),
geopandas, networkx, numpy, matplotlib. **`scipy` MAY be present — test `import scipy` before relying on it.**
`skimage` is likely absent — do not depend on it.

A **Madison Heights drive network is already cached** (fast to reload, no re-download):
point `42.479124, -83.0847521`, dist `25000`, mode `drive`, under `./cache/`. Use it for all dev/testing:
```python
from strongtowns_detroit.geo.isochrones import load_or_build_network, isochrone_polygon
import osmnx as ox
G = load_or_build_network(point=(42.479124, -83.0847521), dist=25000, mode='drive', cache_dir='./cache')
c = ox.distance.nearest_nodes(G, X=-83.0847521, Y=42.479124)
poly = isochrone_polygon(G, c, 600, method='smooth')   # 10-min
```

---

## 2. What was tried — 3 prototypes, judged (renders in `output/proto_*.png`)

All on the **same real 10-min drive reachable set** (13,699 nodes) from the Madison Heights site.
**Honest buffer baseline = 126.3 km². Convex hull = 399.8 km² (the overstatement ceiling).**
The target polygon should be **close to ~126 km²**, NOT near 400.

| Prototype | Area | vs baseline | Verdict |
|---|---|---|---|
| `proto_concave-hull.png` | 280 km² | **2.22× — overstates** | Smooth, but at ratio 0.05 it bridges the gaps between highway fingers. Rejected on fidelity. |
| `proto_morphological-close.png` | **156 km²** | **1.23× — faithful ✅** | Buffer-out(80 m)→erode-in the reachable edges. Closest to honest reach; correctly keeps holes (unreachable pockets) and the isolated west spur as an island. BUT blocky/jagged — not yet "classic smooth". |
| `proto_grid-contour.png` | 254 km² | 2.01× — overstates *at these params* | Distance-field on a 25 m grid → gaussian blur (σ=45) → iso-contour. **Best classic ORS look** (rounded outline, clean holes). Overstatement is from too-generous `road_r=40 m` + `close=130 m`, i.e. tunable, not fundamental. |

### Judgment (already made — implement this, don't re-litigate)
**Winner = morphological-close for the SHAPE (best fidelity + honest holes), plus a smoothing pass for the LOOK.**
The grid-contour's smoothness is desirable but its default params inflate area 2×; morph-close is faithful but
blocky. The right final algorithm combines them:

> **Morphological close on the reachable edges → then smooth the boundary.**

Two acceptable smoothing routes — pick whichever renders cleaner (try both, keep the better default):
- **(preferred) Chaikin corner-cutting (2–3 iters) + `simplify(tolerance)`** — pure-shapely, no scipy, cheap,
  applied to every ring (exterior + interior holes). Rounds corners without moving the boundary outward.
- **(alt) round-trip buffer** `poly.buffer(+r).buffer(-2r).buffer(+r)` at small `r` (~40–60 m) to round corners.
  Note: a naive close-then-open shifts area slightly; verify it doesn't push area up.

Keep morph-close's honest behavior: **preserve interior holes** (genuine unreachable pockets) and **drop
tiny sliver islands** (< ~1% of total area) but keep legitimate disconnected reachable pieces (e.g. the west spur).

### Salvageable code (from the completed concave-hull prototype — reuse the smoothing helpers)
The one prototype that returned full code gave working **Chaikin + sliver-drop + simplify** helpers:
```python
def smooth_isochrone(pts_utm, *, ratio=0.05, round_m=60, min_area_frac=0.01, chaikin_iters=2, simplify_m=12):
    hull = concave_hull(pts_utm, ratio=ratio)
    if hull.geom_type not in ('Polygon','MultiPolygon'):
        hull = pts_utm.convex_hull
    rounded = hull.buffer(round_m).buffer(-2*round_m).buffer(round_m)   # close-then-open
    if rounded.is_empty: rounded = hull
    rounded = drop_slivers(rounded, min_area_frac)                       # keep pieces >= 1% of total area
    return smooth_rings(rounded, chaikin_iters).simplify(simplify_m)     # Chaikin + simplify
# chaikin(): each ring edge -> two points at 0.75/0.25 and 0.25/0.75 blends; 2 iters.
# smooth_rings applies chaikin to exterior + interior rings of each polygon.
```
**Reuse `drop_slivers`, `smooth_rings`/`chaikin`, and the `simplify` tail verbatim.** Just **replace the
`concave_hull(...)` line with the morphological close on reachable EDGES** (that's the fidelity fix), i.e.
build `blob = edges_buffer(B).union_all().buffer(-B*0.6)` style close from the reachable subgraph edges the
way `method='buffer'` already collects them (lines ~364–372), then round + Chaikin + simplify.

---

## 3. The task (do this)

1. **Implement `method='smooth'`** in `isochrone_polygon()` (`src/strongtowns_detroit/geo/isochrones.py`),
   leaving `buffer`/`alpha`/`convex` untouched. Algorithm:
   - reachable set → reachable subgraph edges → buffer each edge by `B` m in local UTM → `union_all()` →
     negative-buffer (erode) by ~`B` (morphological **close**) to fill inter-street gaps into a solid blob;
   - fill/keep holes per honesty rule; drop sliver islands < `min_area_frac`;
   - **smooth** the boundary (Chaikin `chaikin_iters` + `simplify(simplify_m)`), and/or the round-trip buffer;
   - return via `_to_wgs84(...)`.
   - **Expose params** with sensible defaults, e.g. `close_m=120, chaikin_iters=2, simplify_m=15, min_area_frac=0.01`
     (thread through `isochrone_polygon`'s signature; keep existing `edge_buffer_m`/`alpha` for other methods).
   - **Guard optional deps**: pure-shapely path must work with **no scipy**. If you also add a grid-contour
     variant, gate it behind `try: import scipy` with a documented fallback to the morph path.

2. **Tune to fidelity.** Target: 10-min smooth-method area within roughly **1.1–1.4× the buffer baseline
   (~140–175 km²)** on the Madison Heights set — decisively below the convex hull. If it lands near 2× you've
   over-filled; reduce `close_m`. Print `smooth / buffer / convex` areas when tuning.

3. **Wire into the CLI**: add `smooth` to `--method` choices in `generate_isochrones.py` (and anywhere else
   isochrones are drawn). Make it the recommended method in `--help` / README, but do **not** change the
   existing default silently unless it verifies clean — note the change if you do.

4. **Verify** (this is the acceptance gate):
   - Generate 5/10/15-min isochrones with `method='smooth'` on the cached Madison Heights graph.
   - **Area monotonic** with time (5 < 10 < 15).
   - **Faithful**: each ~close to the `buffer` baseline for the same minutes, NOT convex-inflated.
   - **Render a SIDE-BY-SIDE `buffer` vs `smooth` PNG** to `output/` and eyeball it: the smooth one should read
     as a clean classic isochrone while still showing the highway fingers (no bridging across true gaps).
   - **Degrades gracefully** on a tiny/sparse reachable set (few nodes) and with scipy absent.

5. **Do NOT `git commit`.** Leave changes in the working tree; the repo owner commits atomically. Current branch
   is `assessment-and-bza-datasets`; there is other uncommitted work in the tree — **touch only** `isochrones.py`,
   `generate_isochrones.py`, and (optionally) the isochrones README/tests. A test module already exists at
   `pipelines/isochrones/tests/test_isochrones.py` (run with the osmnx venv, `PYTHONPATH=src`) — add a
   monotonicity + fidelity test for `smooth` there.

---

## 4. Guardrails / gotchas

- **Honesty over prettiness.** The whole point is a smooth look that does **not** lie about reach. If smoothing
  pushes area toward the convex hull, it's wrong — dial it back. Keep the highway fingers and genuine holes.
- All metric ops (buffer/erode/area) must be in a **local UTM CRS** (`node_gdf.estimate_utm_crs()`), then
  `_to_wgs84` back — mirror the existing methods; never buffer in degrees.
- Reuse `method='buffer'`'s reachable-edge collection (subgraph → `ox.graph_to_gdfs(sub, nodes=False)` → UTM)
  rather than re-deriving the reachable set.
- Speed: polygon step is trivial vs the Dijkstra; morph close + Chaikin ran < 0.05 s on 13.7k nodes. Fine for 100k.
- The prior workflow's structured-output journal for the completed prototype is at
  `.claude/.../wf_fa7030ea-f92/journal.jsonl` (concave-hull result, full code sketch) if you want the exact helpers.
```
```
