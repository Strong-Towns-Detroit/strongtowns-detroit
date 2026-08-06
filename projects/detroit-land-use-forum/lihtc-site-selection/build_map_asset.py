"""Board: every Detroit site where a LIHTC deal could plausibly go."""
from __future__ import annotations
import base64, io, pathlib, sys
import geopandas as gpd, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from exhibit_brand import masthead_svg
from exhibit_components import (CREAM, NAVY, RED, MUTED, PALE, forum_css, title_block,
                                map_frame, source_lines, write_svg_bundle,
                                swatch_legend, LegendItem)

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "output"
W, H = 1450, 1100
UTM = 32617

sites = pd.read_csv(OUT / "candidate_sites.csv")
g = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs=4326).to_crs(UTM)
bound = gpd.read_file("pipelines/housingDataAnalysis/street_simplification/output/detroit_boundary.geojson").to_crs(UTM)
water = gpd.read_file("pipelines/housingDataAnalysis/street_simplification/output/detroit_water.geojson").to_crs(UTM)
water = water[water.geom_type.isin(["Polygon", "MultiPolygon"])]
# The raw water layer spans Lake St. Clair; clipped to a thin collar around the
# city so the map frames Detroit rather than the lake.
collar = gpd.GeoDataFrame(geometry=bound.buffer(1200), crs=UTM)
water = gpd.clip(water, collar)
qct = gpd.read_file("data/lihtc/qct_2026_wayne.geojson").to_crs(UTM)
qct = gpd.clip(qct, bound)

butzel = g[g.address.astype(str).str.contains("7737 KERCHEVAL", na=False)]

fig, ax = plt.subplots(figsize=(10.4, 7.4), dpi=210)
fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
qct.plot(ax=ax, facecolor="#c8cfd9", alpha=.55, edgecolor="#b3bdcb", linewidth=.3)
bound.plot(ax=ax, facecolor="none", edgecolor=NAVY, linewidth=1.5)
water.plot(ax=ax, facecolor="#dfe7ef", edgecolor="#c9d6e4", linewidth=.4)

# Marker area scales with site acreage so the eye reads capacity, not just count.
g.plot(ax=ax, color=RED, markersize=(g.acres.clip(1.5, 22) * 5.5), alpha=.82,
       edgecolor="white", linewidth=.7, zorder=5)
butzel.plot(ax=ax, color="none", edgecolor=NAVY, markersize=420, linewidth=2.6, zorder=6)

bx, by = butzel.geometry.x.iloc[0], butzel.geometry.y.iloc[0]
ax.annotate("Butzel — 7737 Kercheval\n4.08 acres, city-owned",
            xy=(bx, by), xytext=(bx + 900, by - 7600),
            fontsize=9.5, color=NAVY, fontweight="bold", ha="left",
            arrowprops=dict(arrowstyle="-", color=NAVY, linewidth=1.4))
x0, y0, x1, y1 = bound.total_bounds
mx, my = (x1 - x0) * .03, (y1 - y0) * .03
ax.set_xlim(x0 - mx, x1 + mx); ax.set_ylim(y0 - my, y1 + my)
ax.set_axis_off()
buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=CREAM, bbox_inches="tight", pad_inches=.05)
plt.close(fig)
uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

parts = [masthead_svg(),
         title_block("Every site, all at once",
                     "The 94 publicly owned Detroit parcels that could host a LIHTC development"),
         map_frame(uri, x=40, y=196, width=1000, height=700)]

RAIL = 1080
parts.append(f'<text class="metric" x="{RAIL}" y="286" fill="{RED}">94</text>')
for j, l in enumerate(["SITES", "404 ACRES CITYWIDE"]):
    parts.append(f'<text class="metric-label" x="{RAIL+3}" y="{318+j*20}">{l}</text>')
parts.append(f'<rect x="{RAIL}" y="372" width="310" height="1" fill="{PALE}"/>')
parts.append(f'<text class="section-title" x="{RAIL}" y="418">Where they are</text>')
nb = sites.neighborhood.fillna("Unrecorded").value_counts().head(7)
for j, (name, n) in enumerate(nb.items()):
    parts.append(f'<text class="note" x="{RAIL}" y="{452+j*27}">{name[:26]}</text>')
    parts.append(f'<text class="note" x="{RAIL+310}" y="{452+j*27}" text-anchor="end" '
                 f'font-weight="700">{n}</text>')
parts.append(f'<rect x="{RAIL}" y="{452+len(nb)*27+8}" width="310" height="1" fill="{PALE}"/>')
for j, l in enumerate(["Sites are spread thin across the city.",
                       "Most sit in weak-market tracts far from",
                       "the transit, retail, and jobs that make",
                       "an affordable deal work — which is why",
                       "the short list is shorter than 94."]):
    parts.append(f'<text class="note" x="{RAIL}" y="{452+len(nb)*27+48+j*27}" '
                 f'font-style="italic">{l}</text>')

parts.append(swatch_legend(
    [LegendItem("Candidate site (area ∝ acreage)", RED),
     LegendItem("Qualified Census Tract", "#c8cfd9")],
    positions=[52, 420], y=918))

parts.append(source_lines([
    "Sites: City of Detroit assessor parcel file — publicly owned, vacant, at least 1.5 acres, inside a HUD 2026 Qualified Census Tract, excluding parkland, rail, and utility corridor.",
    "Qualified Census Tracts: HUD 2026 designations clipped to the city boundary. Marker area is proportional to parcel acreage, capped at 22 acres so large outliers stay legible.",
    "Publicly owned means City of Detroit, its Planning & Development Department, the Detroit Land Bank Authority, or an affiliated authority — parcels the city can actually convey.",
], first_y=1000, line_height=25))

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
       'aria-labelledby="title desc"><title id="title">Every site, all at once</title>'
       '<desc id="desc">Map of the 94 publicly owned Detroit parcels that could host a LIHTC '
       'affordable-housing development, with the Butzel site marked.</desc>'
       f'<style>{forum_css()}</style><rect class="paper" width="{W}" height="{H}"/>'
       + "".join(parts) + "</svg>")
write_svg_bundle(OUT, "02-lihtc-candidate-sites", "Every site, all at once", svg, width=W, height=H)
print("wrote 02-lihtc-candidate-sites")
