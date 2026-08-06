"""Rank candidate warehouse sites by drive time to a set of destinations.

Place- and mode-parameterized and Detroit-agnostic -- point the network at any metro.
Reads candidate sites and destinations from CSV (lat/lon columns; optional id and
weight/volume columns). Produces a ranked table with NON-collapsible tradeoff metrics
(worst-case max, volume-weighted mean, coverage within a threshold, p90, unreached count).

Outputs:
    <output>.csv    ranked sites with all metrics
    <output>.png    map of top-K sites + their isochrones + destinations (if --map given)

Example:
    python pipelines/isochrones/warehouse_siting.py \
        --place "Detroit, Michigan, USA" --mode drive \
        --sites sites.csv --destinations dests.csv \
        --id-col name --dest-weight-col volume \
        --threshold-min 30 --objective weighted_mean --top 3 \
        --output output/site_ranking.csv --map output/top_sites.png
"""

import argparse
from pathlib import Path

import pandas as pd

from strongtowns_detroit.geo.isochrones import (
    load_or_build_network, snap_points, isochrone_polygon, rank_sites,
)

DEFAULT_GRAPHML = (
    'pipelines/housingDataAnalysis/street_simplification/detroit_street_network.graphml'
)


def load_pts(path, lat_col, lon_col, id_col=None, weight_col=None):
    df = pd.read_csv(path)
    coords = list(zip(df[lat_col], df[lon_col]))
    ids = list(df[id_col]) if id_col and id_col in df.columns else list(range(len(df)))
    weights = list(df[weight_col]) if weight_col and weight_col in df.columns else None
    return coords, ids, weights


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--place', nargs='+')
    g.add_argument('--point', nargs=2, type=float, metavar=('LAT', 'LON'))
    p.add_argument('--dist', type=int)
    p.add_argument('--mode', choices=('drive', 'walk', 'bike'), default='drive')
    p.add_argument('--sites', required=True, help='CSV of candidate sites')
    p.add_argument('--destinations', required=True, help='CSV of destinations')
    p.add_argument('--lat-col', default='lat')
    p.add_argument('--lon-col', default='lon')
    p.add_argument('--id-col', default='name')
    p.add_argument('--dest-weight-col', default=None,
                   help='Column of destination volumes/weights')
    p.add_argument('--threshold-min', type=float, default=30)
    p.add_argument('--objective', choices=('max', 'weighted_mean', 'pct_within'),
                   default='weighted_mean')
    p.add_argument('--top', type=int, default=3)
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

    sites, site_ids, _ = load_pts(args.sites, args.lat_col, args.lon_col, args.id_col)
    dests, dest_ids, weights = load_pts(
        args.destinations, args.lat_col, args.lon_col, args.id_col, args.dest_weight_col)
    print(f"{len(sites)} candidate sites vs {len(dests)} destinations "
          f"(weights: {'yes' if weights else 'uniform'})")

    ranking = rank_sites(
        G, sites, dests, site_ids=site_ids, weights=weights,
        threshold_min=args.threshold_min, objective=args.objective,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    ranking.round(2).to_csv(out, index=False)
    print(f"Wrote {out}\n")
    print(f"Ranked by {args.objective} (threshold {args.threshold_min:g} min):")
    print(ranking.round(2).to_string(index=False))

    if args.map_path:
        _plot(G, ranking, sites, site_ids, dests, dest_ids, args.top, args.map_path)
        print(f"\nWrote {args.map_path}")


def _plot(G, ranking, sites, site_ids, dests, dest_ids, top, map_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import geopandas as gpd

    id_to_coord = dict(zip(site_ids, sites))
    top_ids = list(ranking['site_id'].head(top))
    top_coords = [id_to_coord[i] for i in top_ids]
    nodes = snap_points(G, top_coords)

    fig, ax = plt.subplots(figsize=(10, 10))
    cmap = plt.get_cmap('Set1', max(top, 3))
    for rank, (sid, (lat, lon), node) in enumerate(zip(top_ids, top_coords, nodes)):
        poly = isochrone_polygon(G, node, 30 * 60, method='buffer')
        if poly is not None:
            gpd.GeoSeries([poly], crs='EPSG:4326').plot(
                ax=ax, color=cmap(rank), alpha=0.20, edgecolor=cmap(rank), linewidth=1.2)
        ax.plot(lon, lat, marker='s', color=cmap(rank), markersize=13,
                markeredgecolor='white', zorder=10, label=f'#{rank+1} {sid}')
    for (lat, lon), did in zip(dests, dest_ids):
        ax.plot(lon, lat, marker='o', color='#0C2340', markersize=8,
                markeredgecolor='white', zorder=9)
        ax.annotate(str(did), (lon, lat), xytext=(3, 3),
                    textcoords='offset points', fontsize=7)
    ax.legend(loc='upper right', title='top sites (30-min drive)')
    ax.set_title('Warehouse siting: top candidates and 30-min drive reach')
    ax.set_axis_off()
    fig.savefig(map_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
