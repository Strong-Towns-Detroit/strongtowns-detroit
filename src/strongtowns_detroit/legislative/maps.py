"""Multi-panel choropleth rendering for a state legislative district."""

from pathlib import Path
from typing import Optional, Sequence

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from strongtowns_data.geo.loader import load_geography, prepare_water
from strongtowns_data.legislative.osm import filter_arterials
from strongtowns_data.mapping.colors import BOUNDARY, Z_BOUNDARY
from strongtowns_data.mapping.layers import add_geography_layers


# Each panel: (column, title, colormap, format_str)
DEFAULT_PANELS: Sequence[tuple[str, str, str, str]] = (
    ('total_population',          'Total population',           'viridis',  '{:,.0f}'),
    ('pop_density_per_km2',       'Population density (per km²)', 'magma',  '{:,.0f}'),
    ('median_household_income',   'Median household income',    'YlGn',     '${:,.0f}'),
    ('pct_poverty',               'Poverty rate (%)',           'OrRd',     '{:.1f}%'),
    ('pct_nh_black',              '% non-Hispanic Black',       'Purples',  '{:.1f}%'),
    ('pct_nh_white',              '% non-Hispanic White',       'Blues',    '{:.1f}%'),
    ('pct_hispanic',              '% Hispanic / Latino',        'Oranges',  '{:.1f}%'),
    ('pct_bachelors_plus',        "% Bachelor's degree or higher", 'BuGn',  '{:.1f}%'),
    ('pct_18_34',                 '% age 18–34',                'GnBu',     '{:.1f}%'),
    ('pct_65_plus',               '% age 65+',                  'PuBu',     '{:.1f}%'),
    ('pct_renter',                '% renter-occupied',          'RdPu',     '{:.1f}%'),
    ('pct_unemployed',            'Unemployment rate (%)',      'OrRd',     '{:.1f}%'),
)


def render_district_panels(
    tracts: gpd.GeoDataFrame,
    district: gpd.GeoDataFrame,
    panels: Sequence[tuple[str, str, str, str]] = DEFAULT_PANELS,
    *,
    ncols: int = 3,
    figsize: Optional[tuple[float, float]] = None,
    title: Optional[str] = None,
    geography_dir: Optional[str | Path] = None,
    streets: Optional[gpd.GeoDataFrame] = None,
    water: Optional[gpd.GeoDataFrame] = None,
) -> Figure:
    """Render a grid of choropleth maps, one per panel definition.

    Parameters
    ----------
    geography_dir : str or Path, optional
        Fallback directory with detroit_water.gpkg / detroit_network_basic.gpkg.
    streets, water : GeoDataFrame, optional
        Pre-loaded street and water layers (override geography_dir if given).
    """
    n = len(panels)
    nrows = (n + ncols - 1) // ncols
    if figsize is None:
        figsize = (5 * ncols, 5 * nrows)

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    axes = axes.flatten() if n > 1 else [axes]

    # Sync CRS once.
    if tracts.crs != district.crs:
        tracts = tracts.to_crs(district.crs)

    # Optional geographic context layers (water, streets).
    edges = streets
    if edges is None and geography_dir is not None:
        _city_boundary, fallback_water, edges = load_geography(
            geography_dir, load_streets=True,
        )
        if water is None:
            water = fallback_water
    if edges is not None:
        edges = filter_arterials(edges)
    if water is not None:
        water = prepare_water(water, district)

    for ax, (col, panel_title, cmap, fmt) in zip(axes, panels):
        if col not in tracts.columns:
            ax.set_title(f"{panel_title}\n(missing column: {col})")
            ax.axis('off')
            continue

        data = tracts.copy()
        data[col] = pd.to_numeric(data[col], errors='coerce')
        data = data.dropna(subset=[col])
        if len(data) == 0:
            ax.set_title(f"{panel_title}\n(no data)")
            ax.axis('off')
            continue

        data.plot(
            column=col, cmap=cmap, ax=ax, legend=True,
            legend_kwds={'shrink': 0.6, 'format': _formatter(fmt)},
            edgecolor='white', linewidth=0.2, zorder=2,
        )
        if water is not None or edges is not None:
            add_geography_layers(
                ax, boundary=None, water=water, edges=edges,
                ref_gdf=district, clip_to_bounds=True,
                street_lw=0.35, street_alpha=0.55,
                water_alpha=0.85,
            )
        district.boundary.plot(
            ax=ax, edgecolor=BOUNDARY, linewidth=1.5,
            linestyle='--', zorder=Z_BOUNDARY,
        )
        ax.set_title(panel_title, fontsize=11)
        ax.set_axis_off()

    # Hide leftover axes.
    for ax in axes[n:]:
        ax.set_axis_off()

    if title:
        fig.suptitle(title, fontsize=15, y=0.995)

    fig.tight_layout()
    return fig


def render_locator_map(
    district: gpd.GeoDataFrame,
    *,
    cities: Optional[gpd.GeoDataFrame] = None,
    streets: Optional[gpd.GeoDataFrame] = None,
    water: Optional[gpd.GeoDataFrame] = None,
    title: str = 'Michigan State House District 9',
    subtitle: Optional[str] = None,
    district_color: str = '#0C2340',
    district_alpha: float = 0.85,
    background: str = '#f5f5f0',
    figsize: tuple[float, float] = (10, 11),
    pad_frac: float = 0.08,
    label_cities: bool = True,
) -> Figure:
    """Render a clean, campaign-style locator map for a single district.

    Layout: district polygon filled in district_color, surrounding city
    boundaries as light reference, arterial streets thin gray, water soft
    blue. Sized for embedding on a website.
    """
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_facecolor(background)
    fig.patch.set_facecolor(background)

    target_crs = district.crs

    # Frame: pad the district bounds.
    minx, miny, maxx, maxy = district.total_bounds
    dx, dy = maxx - minx, maxy - miny
    ax.set_xlim(minx - dx * pad_frac, maxx + dx * pad_frac)
    ax.set_ylim(miny - dy * pad_frac, maxy + dy * pad_frac)

    # 1) Cities (background reference, very light).
    if cities is not None and len(cities) > 0:
        c = cities.to_crs(target_crs) if cities.crs != target_crs else cities
        c.plot(
            ax=ax, facecolor='#e8e8e2', edgecolor='#bdbdb5',
            linewidth=0.8, zorder=1,
        )

    # 2) Water.
    if water is not None and len(water) > 0:
        w = water.to_crs(target_crs) if water.crs != target_crs else water
        w.plot(
            ax=ax, facecolor='#bcd8ea', edgecolor='#7fb3d5',
            linewidth=0.4, alpha=0.95, zorder=2,
        )

    # 3) Streets — emphasise arterials, fade residential.
    if streets is not None and len(streets) > 0:
        s = streets.to_crs(target_crs) if streets.crs != target_crs else streets
        residential = s[~s['highway'].isin(filter_arterials(s)['highway'].unique())] \
            if 'highway' in s.columns else None
        arterials = filter_arterials(s)
        if residential is not None and len(residential) > 0:
            residential.plot(
                ax=ax, color='#bdbdbd', linewidth=0.25, alpha=0.5, zorder=3,
            )
        if len(arterials) > 0:
            arterials.plot(
                ax=ax, color='#7a7a7a', linewidth=0.85, alpha=0.9, zorder=4,
            )

    # 4) District fill (the headline).
    district.plot(
        ax=ax, facecolor=district_color, edgecolor=district_color,
        linewidth=0, alpha=district_alpha, zorder=5,
    )
    district.boundary.plot(
        ax=ax, edgecolor=district_color, linewidth=2.5, zorder=6,
    )

    # 5) City labels.
    if label_cities and cities is not None and 'display_name' in cities.columns:
        for _, row in cities.iterrows():
            name = (row.get('name') or row.get('display_name') or '').split(',')[0]
            if not name:
                continue
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            point = geom.representative_point()
            ax.annotate(
                name.upper(),
                xy=(point.x, point.y),
                ha='center', va='center',
                fontsize=10, fontweight='bold',
                color='#2c3e50',
                path_effects=[],
                zorder=7,
            )

    ax.set_aspect('equal')
    ax.set_axis_off()

    # Title block.
    fig.suptitle(title, fontsize=22, fontweight='bold', y=0.96, color='#1a1a1a')
    if subtitle:
        ax.set_title(subtitle, fontsize=13, color='#555555', pad=12)

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return fig


def _formatter(fmt: str):
    def f(x, _pos=None):
        try:
            return fmt.format(x)
        except (ValueError, TypeError):
            return ''
    return f


def save_figure(fig: Figure, output_path: str | Path, *, dpi: int = 150) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
    return output_path
