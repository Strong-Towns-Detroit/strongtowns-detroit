#!/usr/bin/env python3
"""Export one script-free, self-contained HTML and SVG asset per travel mode."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import transform, unary_union

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from exhibit_components import (
    forum_css,
)
from strongtowns_detroit.graphics import (
    CONFERENCE_LANDSCAPE,
    Graphic,
    GraphicTheme,
    SvgComponent,
    render_graphic_svg,
    write_graphic_bundle,
)
REPO_ROOT = HERE.parents[2]
DEFAULT_DATA = HERE / "output/display_isochrones.geojson"
DEFAULT_ROADS = HERE / "output/road_context.geojson"
DEFAULT_BOUNDARY = (
    REPO_ROOT
    / "pipelines/housingDataAnalysis/resources/data"
    / "Detroit_City_Council_Districts_2026.geojson"
)

MODE_LABELS = {
    "walking": "A 30-minute walk stays downtown",
    "public_transport": "Transit is barely viable along the inner spokes",
    "driving": "A 15-minute city—by car",
}
MODE_FILENAMES = {
    "walking": "walking",
    "public_transport": "public-transit",
    "driving": "driving",
}
COLORS = {30: "#a7c6ed", 20: "#5790db", 15: "#ffb549", 10: "#e8783d", 5: "#c83a3a"}
WIDTH, HEIGHT = 1400, 1000
MAP_X, MAP_Y, MAP_W, MAP_H = 45, 185, 1310, 720


def _project(geometry):
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    return transform(transformer.transform, geometry)


def _mapper(bounds):
    minx, miny, maxx, maxy = bounds
    scale = min(MAP_W / (maxx - minx), MAP_H / (maxy - miny))
    used_w, used_h = (maxx - minx) * scale, (maxy - miny) * scale
    x0, y0 = MAP_X + (MAP_W - used_w) / 2, MAP_Y + (MAP_H - used_h) / 2

    def point(x, y):
        return x0 + (x - minx) * scale, y0 + used_h - (y - miny) * scale

    return point


def _line(coords, map_point, close=False):
    values = []
    for index, (x, y, *_) in enumerate(coords):
        px, py = map_point(x, y)
        values.append(f"{'M' if index == 0 else 'L'}{px:.1f},{py:.1f}")
    if close:
        values.append("Z")
    return "".join(values)


def geometry_path(geometry, map_point):
    kind = geometry.geom_type
    if kind == "Polygon":
        paths = [_line(geometry.exterior.coords, map_point, True)]
        paths.extend(_line(ring.coords, map_point, True) for ring in geometry.interiors)
        return "".join(paths)
    if kind == "MultiPolygon":
        return "".join(geometry_path(part, map_point) for part in geometry.geoms)
    if kind in {"LineString", "LinearRing"}:
        return _line(geometry.coords, map_point)
    if kind == "MultiLineString":
        return "".join(_line(part.coords, map_point) for part in geometry.geoms)
    if kind == "GeometryCollection":
        return "".join(geometry_path(part, map_point) for part in geometry.geoms)
    return ""


def build_graphic(
    mode,
    data,
    roads,
    city,
    spec,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    sources: tuple[str, ...] | None = None,
    description: str | None = None,
):
    map_point = _mapper(city.bounds)
    city_path = geometry_path(city, map_point)
    layers = [
        f'<path class="city" fill-rule="evenodd" d="{city_path}"/>'
    ]
    rows = data[data["mode"] == mode].sort_values("minutes", ascending=False)
    for row in rows.itertuples():
        minutes = int(row.minutes)
        layers.append(
            f'<path class="band" fill="{COLORS[minutes]}" fill-rule="evenodd" '
            f'd="{geometry_path(row.geometry, map_point)}"/>'
        )
    for row in roads.itertuples():
        layers.append(
            f'<path class="road road-{html.escape(row.road_class)}" '
            f'd="{geometry_path(row.geometry, map_point)}"/>'
        )
    origin = _project(
        Point(spec["origin"]["longitude"], spec["origin"]["latitude"])
    )
    ox, oy = map_point(origin.x, origin.y)
    layers.append(f'<circle class="origin" cx="{ox:.1f}" cy="{oy:.1f}" r="7"/>')

    legend = []
    for minutes in spec["threshold_minutes"]:
        x = 50 + (minutes == 5 and 0 or spec["threshold_minutes"].index(minutes)) * 145
        legend.append(
            f'<rect x="{x}" y="935" width="24" height="24" fill="{COLORS[minutes]}"/>'
            f'<text class="legend" x="{x + 34}" y="954">{minutes} min</text>'
        )
    title = title or MODE_LABELS[mode]
    subtitle = subtitle or {
        "walking": "Five- to 30-minute walking times from Campus Martius",
        "public_transport": (
            "Median five- to 30-minute transit reach from Campus Martius · "
            "Wednesday noon–1 p.m."
        ),
        "driving": "Five- to 30-minute driving times from Campus Martius",
    }[mode]
    source = (
        "TravelTime API · Transit is the median of 13 departures, noon–1 p.m."
        if mode == "public_transport"
        else "TravelTime API · Wednesday midday travel-time model"
    )
    visual = f"""
<style>
  {forum_css(dek_size=23, legend_size=17,
  extra_rules=".legend{font-weight:700}.subtitle{font-family:Georgia,'Times New Roman',serif;font-size:23px;fill:#526276}",
  cream="#fffdf8")}
  .city{{fill:#f4efe6;stroke:#0c2340;stroke-width:1.5}}
  .band{{stroke:#0c2340;stroke-width:.35}}
  .road{{fill:none;stroke-linecap:round}} .road-local{{stroke:#fff;stroke-width:.55;opacity:.76}}
  .road-arterial{{stroke:#0c2340;stroke-width:.75;opacity:.52}}
  .road-major{{stroke:#0c2340;stroke-width:1.6;opacity:.74}}
  .origin{{fill:#c83a3a;stroke:#fff;stroke-width:2.5}}
</style>
<g>{''.join(layers)}</g>
<g>{''.join(legend)}</g>
"""
    return Graphic(
        title=title,
        subtitle=subtitle,
        visual=SvgComponent(visual, WIDTH, 800, min_y=170),
        sources=sources if sources is not None else (source,),
        description=description if description is not None else (
            f"{subtitle}. Five through thirty minute travel bands."
        ),
    )


def build_svg(mode, data, roads, city, spec):
    return render_graphic_svg(
        build_graphic(mode, data, roads, city, spec),
        theme=GraphicTheme(background="#fffdf8"),
    )


def run(data_path, roads_path, boundary_path, spec_path, output_dir, png_width=2800):
    spec = json.loads(spec_path.read_text())
    data = gpd.read_file(data_path).to_crs("EPSG:4326")
    roads = gpd.read_file(roads_path).to_crs("EPSG:4326")
    boundary = gpd.read_file(boundary_path).to_crs("EPSG:4326")
    city = _project(unary_union(boundary.geometry))
    data.geometry = data.geometry.map(_project)
    roads.geometry = roads.geometry.map(_project)

    output_dir.mkdir(parents=True, exist_ok=True)
    for mode in spec["modes"]:
        expected = set(spec["threshold_minutes"])
        present = set(data.loc[data["mode"] == mode, "minutes"].astype(int))
        if present != expected:
            raise SystemExit(
                f"{mode}: expected thresholds {sorted(expected)}, found {sorted(present)}"
            )
        stem = MODE_FILENAMES[mode]
        write_graphic_bundle(
            output_dir, stem, build_graphic(mode, data, roads, city, spec),
            aspect_ratio=CONFERENCE_LANDSCAPE,
            png_width=png_width,
            theme=GraphicTheme(background="#fffdf8"),
        )
        print(f"Wrote {output_dir / f'{stem}.svg'}")
        print(f"Wrote {output_dir / f'{stem}.html'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--roads", type=Path, default=DEFAULT_ROADS)
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--spec", type=Path, default=HERE / "spec.json")
    parser.add_argument("--output-dir", type=Path, default=HERE / "output/share")
    parser.add_argument(
        "--png-width", type=int, default=2800,
        help="PNG width in pixels; height follows the SVG aspect ratio (default: 2800).",
    )
    args = parser.parse_args()
    run(
        args.data, args.roads, args.boundary, args.spec, args.output_dir,
        args.png_width,
    )


if __name__ == "__main__":
    main()
