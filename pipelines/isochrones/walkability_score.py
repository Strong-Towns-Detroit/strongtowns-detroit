"""Score points by travel-time access to amenities (walkability / land-value accessibility).

Place- and mode-parameterized. Reads points from a .gpkg / .geojson (point geometries) or a
.csv with lat/lon columns. Fetches OSM amenities per category, computes each point's
travel time to the nearest amenity, and produces a composite 0-100 accessibility score
plus a per-category breakdown and the weakest category.

Outputs:
    <output>.gpkg    input points + time_<cat>, score_<cat>, walkability_score, weakest_category
    <output>.csv     same, tabular
    <output>.png     map coloured by walkability_score (if --map given)

Example:
    python pipelines/isochrones/walkability_score.py \
        --place "Detroit, Michigan, USA" --mode walk \
        --points my_coords.csv --lat-col lat --lon-col lon \
        --categories grocery transit park school pharmacy restaurant \
        --output output/walkability.gpkg --map output/walkability.png
"""

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from strongtowns_detroit.geo.isochrones import load_or_build_network, score_accessibility

DEFAULT_GRAPHML = (
    'pipelines/housingDataAnalysis/street_simplification/detroit_street_network.graphml'
)


def load_points(path, lat_col, lon_col):
    path = Path(path)
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(path)
        geom = [Point(x, y) for x, y in zip(df[lon_col], df[lat_col])]
        return gpd.GeoDataFrame(df, geometry=geom, crs='EPSG:4326')
    gdf = gpd.read_file(path)
    return gdf.to_crs('EPSG:4326')


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--place', nargs='+')
    g.add_argument('--point', nargs=2, type=float, metavar=('LAT', 'LON'))
    p.add_argument('--dist', type=int)
    p.add_argument('--mode', choices=('drive', 'walk', 'bike'), default='walk')
    p.add_argument('--points', required=True, help='.gpkg/.geojson/.csv of points to score')
    p.add_argument('--lat-col', default='lat')
    p.add_argument('--lon-col', default='lon')
    p.add_argument('--categories', nargs='+',
                   default=['grocery', 'transit', 'park', 'school', 'pharmacy', 'restaurant'])
    p.add_argument('--cutoff-min', type=float, default=None,
                   help='Ignore amenities beyond this travel time (speeds up big runs)')
    p.add_argument('--decay', choices=('exp', 'linear'), default='exp')
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
        place=place, point=tuple(args.point) if args.point else None,
        dist=args.dist, mode=args.mode, cache_dir=args.cache_dir,
        reuse_graphml=args.reuse_graphml,
    )
    print(f"Network: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    points = load_points(args.points, args.lat_col, args.lon_col)
    print(f"Scoring {len(points)} points across {len(args.categories)} categories...")

    # Amenity search region: the place if given, else the points' buffered hull.
    place_or_poly = place if place else None
    scored = score_accessibility(
        points, G, mode=args.mode, categories=args.categories,
        place_or_poly=place_or_poly, cutoff_min=args.cutoff_min, decay=args.decay,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    from strongtowns_detroit.legislative.osm import save_layer
    save_layer(scored, out)
    csv_path = out.with_suffix('.csv')
    scored.drop(columns='geometry').to_csv(csv_path, index=False)
    print(f"Wrote {out}\nWrote {csv_path}")

    label = 'name' if 'name' in scored.columns else scored.columns[0]
    cols = [label, 'walkability_score', 'weakest_category']
    print("\n" + scored[cols].round(1).to_string(index=False))

    if args.map_path:
        _plot(scored, args.map_path)
        print(f"Wrote {args.map_path}")


def _plot(scored, map_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 9))
    scored.plot(ax=ax, column='walkability_score', cmap='RdYlGn', vmin=0, vmax=100,
                markersize=90, edgecolor='#222222', linewidth=0.5, legend=True,
                legend_kwds={'label': 'walkability score (0-100)', 'shrink': 0.6})
    if 'name' in scored.columns:
        for _, r in scored.iterrows():
            ax.annotate(str(r['name']), (r.geometry.x, r.geometry.y),
                        xytext=(4, 4), textcoords='offset points', fontsize=8)
    ax.set_title('Amenity accessibility (walkability score)')
    ax.set_axis_off()
    fig.savefig(map_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
