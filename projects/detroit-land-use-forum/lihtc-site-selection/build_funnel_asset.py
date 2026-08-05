"""Board: the LIHTC site-selection attrition funnel."""
from __future__ import annotations
import json, math, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from exhibit_brand import masthead_svg
from exhibit_components import (CREAM, NAVY, RED, MUTED, PALE, forum_css,
                                title_block, source_lines, write_svg_bundle)

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "output"
W, H = 1450, 1100

rows = json.load(open(OUT / "funnel.json"))

# Chart column stops well short of the rail so nothing can collide with it.
X0, X1 = 78, 880
RAIL = 1010
LO, HI = 10.0, 1_000_000.0
def sx(v): return X0 + (X1 - X0) * (math.log10(max(v, LO)) - math.log10(LO)) / (math.log10(HI) - math.log10(LO))

Y0, DY, BAR = 300, 112, 42
parts = [masthead_svg(),
         title_block("There is no “somewhere else”",
                     "Detroit parcels that could host a LIHTC affordable-housing development")]

for t in (100, 1_000, 10_000, 100_000):
    x = sx(t)
    parts.append(f'<line x1="{x:.1f}" y1="{Y0-36}" x2="{x:.1f}" y2="{Y0+(len(rows)-1)*DY+BAR+10}" '
                 f'stroke="{PALE}" stroke-width="1"/>')
    parts.append(f'<text class="legend" x="{x:.1f}" y="{Y0-46}" text-anchor="middle" '
                 f'fill="{MUTED}">{t:,}</text>')

for i, r in enumerate(rows):
    y = Y0 + i * DY
    last = i == len(rows) - 1
    color = RED if last else NAVY
    x_end = sx(r["remaining"])
    parts.append(f'<text class="note" x="{X0}" y="{y-13}" font-weight="700">{r["gate"]}</text>')
    parts.append(f'<rect x="{X0}" y="{y}" width="{max(x_end-X0,2):.1f}" height="{BAR}" '
                 f'fill="{color}" fill-opacity="{1.0 if last else 0.88}" rx="2"/>')
    parts.append(f'<text class="section-title" x="{x_end+14:.1f}" y="{y+BAR-10}" '
                 f'fill="{color}">{r["remaining"]:,}</text>')
    if i:
        parts.append(f'<text class="legend" x="{x_end+16:.1f}" y="{y+BAR+22}" '
                     f'fill="{MUTED}">−{r["cut"]:,} removed</text>')

# Call out the gate that actually does the work, inline beside its bar.
gy = Y0 + 4 * DY
ax = sx(433) + 120
parts.append(f'<line x1="{ax-16}" y1="{gy+6}" x2="{ax-16}" y2="{gy+BAR-4}" '
             f'stroke="{RED}" stroke-width="2.5"/>')
for j, line in enumerate(["The collapse happens here.",
                          "99.6% of Detroit’s vacant land sits in",
                          "lots too small to build anything on."]):
    parts.append(f'<text class="note" x="{ax}" y="{gy+4+j*23}" fill="{RED}" '
                 f'font-weight="{"700" if j == 0 else "400"}">{line}</text>')

# ---- right rail ----
parts.append(f'<text class="metric" x="{RAIL}" y="290" fill="{RED}">94</text>')
for j, line in enumerate(["SITES CITYWIDE WHERE A", "LIHTC DEAL COULD PLAUSIBLY GO"]):
    parts.append(f'<text class="metric-label" x="{RAIL+3}" y="{322+j*20}">{line}</text>')
for j, line in enumerate(["0.02% of Detroit’s 378,366 parcels.", "404 acres in total."]):
    parts.append(f'<text class="note" x="{RAIL+3}" y="{382+j*26}">{line}</text>')

parts.append(f'<rect x="{RAIL}" y="452" width="370" height="1" fill="{PALE}"/>')
parts.append(f'<text class="section-title" x="{RAIL}" y="500">The Butzel site</text>')
for j, line in enumerate([
        "7737 Kercheval — 4.08 acres, city-owned,",
        "vacant, inside a Qualified Census Tract.",
        "It clears every gate, and ranks 37th of",
        "94 by size."]):
    parts.append(f'<text class="note" x="{RAIL}" y="{534+j*27}">{line}</text>')
parts.append(f'<rect x="{RAIL}" y="664" width="370" height="1" fill="{PALE}"/>')
for j, line in enumerate([
        "“Build it somewhere else” is a request to",
        "choose from the other 93 — most of them",
        "further from transit, jobs, and existing",
        "neighborhood fabric than this one."]):
    parts.append(f'<text class="note" x="{RAIL}" y="{702+j*27}" font-style="italic">{line}</text>')

parts.append(source_lines([
    "Gates applied in sequence to the City of Detroit assessor parcel file (378,366 parcels); each bar counts parcels surviving all gates above it.",
    "Qualified Census Tracts: HUD 2026 designations, effective Jan. 1 2026, joined by parcel centroid. Only ZCTA 48226 in Detroit is a Difficult Development Area.",
    "“Vacant” is the assessor’s no-assessed-structure class; parkland, rail corridor, and utility right-of-way are removed separately because that class includes them.",
    "1.5 acres approximates a 40-unit site at Detroit densities. At 1.0 acre 131 sites qualify; at 3.0 acres, 54. Horizontal axis is logarithmic.",
], first_y=996, line_height=24))

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
       'aria-labelledby="title desc">'
       '<title id="title">There is no somewhere else</title>'
       '<desc id="desc">Attrition funnel reducing 378,366 Detroit parcels to 94 sites that '
       'could host a LIHTC affordable-housing development.</desc>'
       f'<style>{forum_css()}</style>'
       f'<rect class="paper" width="{W}" height="{H}"/>' + "".join(parts) + "</svg>")

write_svg_bundle(OUT, "01-lihtc-site-funnel", "There is no somewhere else", svg, width=W, height=H)
print("wrote 01-lihtc-site-funnel")
