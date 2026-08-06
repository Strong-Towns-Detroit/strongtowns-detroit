"""Generate travel-time isochrone (reachability) polygons from origin point(s).

Place- and mode-parameterized. Supply the network region as EITHER a --place string
OR a --point lat lon with --dist metres. Origins are one or more lat,lon points.

Outputs:
    <output>.gpkg     one polygon per (origin, minute) with columns origin, minutes, area_km2
    <output>.png      map of the isochrones over geographic context (if --map given)

Examples:
    # 5/10/15-min walk isochrones from Campus Martius, Detroit
    python pipelines/isochrones/generate_isochrones.py \
        --point 42.3400 -83.0550 --dist 3500 --mode walk \
        --origins 42.3314,-83.0458 --minutes 5 10 15 \
        --output output/isochrones_campus_martius.gpkg \
        --map output/isochrones_campus_martius.png

    # drive isochrones anywhere by place name
    python pipelines/isochrones/generate_isochrones.py \
        --place "Columbus, Ohio, USA" --mode drive \
        --origins 39.9612,-82.9988 --minutes 10 20 30 \
        --output output/columbus_iso.gpkg
"""

import argparse
from pathlib import Path

import geopandas as gpd

from strongtowns_detroit.geo.isochrones import (
    load_or_build_network, snap_points, isochrone_polygon, fetch_water,
)

DEFAULT_GRAPHML = (
    'pipelines/housingDataAnalysis/street_simplification/detroit_street_network.graphml'
)


def parse_coord(s):
    lat, lon = s.split(',')
    return float(lat), float(lon)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--place', nargs='+', help='Place name(s) for the network region')
    g.add_argument('--point', nargs=2, type=float, metavar=('LAT', 'LON'),
                   help='Center point for a point+dist network')
    p.add_argument('--dist', type=int, help='Radius in metres (required with --point)')
    p.add_argument('--mode', choices=('drive', 'walk', 'bike'), default='walk')
    p.add_argument('--origins', nargs='+', type=parse_coord, required=True,
                   metavar='LAT,LON', help='Origin coordinate(s), e.g. 42.33,-83.04')
    p.add_argument('--minutes', nargs='+', type=float, default=[5, 10, 15])
    p.add_argument(
        '--method', choices=('buffer', 'smooth', 'alpha', 'convex'), default='buffer',
        help="Polygon style: 'smooth' is recommended for a clean, network-faithful map; "
             "'buffer' is the honest street footprint (default); 'convex' overstates reach",
    )
    p.add_argument('--cache-dir', default='./cache')
    p.add_argument('--output', required=True)
    p.add_argument('--map', dest='map_path', default=None)
    p.add_argument('--reuse-graphml', default=None,
                   help='OPT-IN Detroit-only speed shortcut: path to a pre-downloaded drive '
                        'graph to reuse. Only honored for --mode drive AND only when the '
                        'requested location falls inside that graph; otherwise ignored and '
                        f'the correct network is built. Detroit graph: {DEFAULT_GRAPHML}')
    args = p.parse_args()

    place = ' '.join(args.place) if args.place and len(args.place) == 1 else args.place
    G = load_or_build_network(
        place=place,
        point=tuple(args.point) if args.point else None,
        dist=args.dist, mode=args.mode, cache_dir=args.cache_dir,
        reuse_graphml=args.reuse_graphml,
    )
    print(f"Network: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    origin_nodes = snap_points(G, args.origins)
    records, geoms = [], []
    for (lat, lon), node in zip(args.origins, origin_nodes):
        for minutes in sorted(args.minutes):
            poly = isochrone_polygon(G, node, minutes * 60, method=args.method)
            if poly is None:
                continue
            area = gpd.GeoSeries([poly], crs='EPSG:4326')
            area_km2 = area.to_crs(area.estimate_utm_crs()).area.iloc[0] / 1e6
            records.append({'origin': f"{lat},{lon}", 'minutes': minutes,
                            'area_km2': round(area_km2, 3)})
            geoms.append(poly)
            print(f"  origin {lat},{lon}  {minutes:g}-min  {area_km2:.3f} km2")

    iso = gpd.GeoDataFrame(records, geometry=geoms, crs='EPSG:4326')
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    iso.to_file(out, driver='GPKG')
    print(f"Wrote {out}")

    if args.map_path:
        print("Fetching OSM water for map context…")
        water = fetch_water(place=place,
                            point=tuple(args.point) if args.point else None,
                            dist=args.dist)
        _plot(iso, args.origins, args.map_path, G=G, water=water)
        print(f"Wrote {args.map_path}")


def _plot(iso, origins, map_path, *, G=None, water=None):
    """Layered map: faint OSM street underlay + water, then travel-time
    isochrones painted on top, then the origin marker."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 9))

    # clip context to the isochrone extent (with a small margin) so the map
    # frames the reachable area rather than the whole downloaded network
    minx, miny, maxx, maxy = iso.total_bounds
    mx, my = (maxx - minx) * 0.06, (maxy - miny) * 0.06

    # 1. faint street underlay (whole OSM network in-frame = the "land")
    if G is not None:
        import osmnx as ox
        edges = ox.graph_to_gdfs(G, nodes=False)
        edges.plot(ax=ax, color='#e2e2e2', linewidth=0.25, zorder=1)

    # 2. water features (define the land)
    if water is not None and len(water):
        polys = water[water.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        lines = water[water.geometry.type.isin(['LineString', 'MultiLineString'])]
        if len(polys):
            polys.plot(ax=ax, color='#a9cce3', edgecolor='#7fb3d5',
                       linewidth=0.3, zorder=2)
        if len(lines):
            lines.plot(ax=ax, color='#7fb3d5', linewidth=0.6, zorder=2)

    # 3. travel-time isochrones, largest first (drawn underneath the smaller)
    iso = iso.sort_values('minutes', ascending=False)
    mins = sorted(iso['minutes'].unique())
    cmap = plt.get_cmap('viridis', len(mins))
    color_by_min = {m: cmap(i) for i, m in enumerate(mins)}
    for _, row in iso.iterrows():
        gpd.GeoSeries([row.geometry], crs='EPSG:4326').plot(
            ax=ax, color=color_by_min[row['minutes']], alpha=0.55,
            edgecolor='#333333', linewidth=0.4, zorder=3,
        )

    # 4. origin marker
    for lat, lon in origins:
        ax.plot(lon, lat, marker='*', color='#FA4616', markersize=20,
                markeredgecolor='white', zorder=10)

    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=color_by_min[m], alpha=0.7, label=f'{m:g} min')
                       for m in mins], loc='upper right', title='drive time')
    ax.set_xlim(minx - mx, maxx + mx)
    ax.set_ylim(miny - my, maxy + my)
    ax.set_title('Travel-time reachability over OSM context')
    ax.set_axis_off()
    fig.savefig(map_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
