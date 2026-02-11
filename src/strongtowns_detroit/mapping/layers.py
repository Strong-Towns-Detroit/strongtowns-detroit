"""Detroit map layer rendering for matplotlib.

Provides reusable functions for drawing geographic context (water, streets,
boundary) onto matplotlib axes, plus a legend helper.
"""

import geopandas as gpd
from shapely.geometry import box

from strongtowns_detroit.mapping.colors import (
    WATER_FILL, WATER_EDGE, STREET, BOUNDARY,
    Z_WATER, Z_STREETS, Z_BOUNDARY,
)


def add_geography_layers(
    ax, boundary, water, edges, ref_gdf, *,
    water_color=WATER_FILL,
    water_edge_color=WATER_EDGE,
    water_alpha=0.7,
    street_color=STREET,
    street_lw=0.2,
    street_alpha=0.4,
    boundary_color=BOUNDARY,
    boundary_lw=2,
    boundary_style='--',
    boundary_alpha=0.8,
    clip_to_bounds=True,
):
    """Render Detroit geographic context layers onto a matplotlib axis.

    Draws water, streets, and the municipal boundary behind (or around)
    whatever analysis layer you're plotting.  All layers are CRS-synced
    to *ref_gdf* and optionally clipped to its bounding box.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axis.
    boundary : GeoDataFrame or None
        Municipal boundary polygon.
    water : GeoDataFrame or None
        Water feature polygons.
    edges : GeoDataFrame or None
        Street network line segments.
    ref_gdf : GeoDataFrame
        Reference layer whose CRS and bounds are used for alignment.
    clip_to_bounds : bool
        If True (default), clip all layers to ref_gdf's bounding box.
    """
    target_crs = ref_gdf.crs
    clip_gdf = None
    if clip_to_bounds:
        clip_gdf = gpd.GeoDataFrame(
            {'geometry': [box(*ref_gdf.total_bounds)]}, crs=target_crs,
        )

    # Water (background)
    if water is not None and len(water) > 0:
        w = water.to_crs(target_crs) if water.crs != target_crs else water
        if clip_gdf is not None:
            w = w.clip(clip_gdf)
        if len(w) > 0:
            w.plot(
                ax=ax, facecolor=water_color, edgecolor=water_edge_color,
                linewidth=0.3, alpha=water_alpha, zorder=Z_WATER,
            )

    # Street network
    if edges is not None and len(edges) > 0:
        e = edges.to_crs(target_crs) if edges.crs != target_crs else edges
        if clip_gdf is not None:
            e = e.clip(clip_gdf)
        if len(e) > 0:
            e.plot(
                ax=ax, color=street_color, linewidth=street_lw,
                alpha=street_alpha, zorder=Z_STREETS,
            )

    # Municipal boundary (top)
    if boundary is not None:
        b = boundary.to_crs(target_crs) if boundary.crs != target_crs else boundary
        if clip_gdf is not None:
            b = b.clip(clip_gdf)
        if len(b) > 0:
            b.boundary.plot(
                ax=ax, edgecolor=boundary_color, linewidth=boundary_lw,
                linestyle=boundary_style, alpha=boundary_alpha,
                zorder=Z_BOUNDARY,
            )


def make_patch_legend(ax, color_label_pairs, *, loc='lower right', alpha=1.0, **kwargs):
    """Build a matplotlib Patch legend from (color, label) pairs.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axis.
    color_label_pairs : list of (str, str)
        Each entry is ``(hex_color, label_text)``.
    loc : str
        Legend location (matplotlib location string).
    alpha : float
        Patch alpha.
    **kwargs
        Forwarded to ``ax.legend()``.

    Returns
    -------
    matplotlib.legend.Legend
    """
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=color, label=label, alpha=alpha)
        for color, label in color_label_pairs
    ]
    return ax.legend(handles=handles, loc=loc, **kwargs)
