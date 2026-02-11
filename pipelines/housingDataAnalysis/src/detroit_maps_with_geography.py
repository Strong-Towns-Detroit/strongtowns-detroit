#!/usr/bin/env python3
"""
Enhanced Detroit Housing Maps with Geographic Context

This script adds street networks, water features, and municipal boundaries
to the housing burden visualizations.
"""

import geopandas as gpd
import matplotlib.pyplot as plt

from pathlib import Path
import pandas as pd

from strongtowns_detroit.geo.loader import load_geography, sync_crs
from strongtowns_detroit.mapping.layers import add_geography_layers, make_patch_legend
from strongtowns_detroit.mapping.colors import (
    ALPHA_BLOCKGROUPS, BURDEN_BINS as BINS, BURDEN_CMAP,
    SHORTAGE_COLORS, ACCESSIBILITY_COLORS, HOUSING_CATEGORY_COLORS,
    NEUTRAL, Z_DATA,
)

# Configuration
GEOGRAPHY_DIR = 'output'  # Directory with geography files from osmnx script


def load_geography_data(geography_dir='output'):
    """Load the geography data created by the OSMnx script."""
    print("Loading geography data...")
    boundary, water, edges = load_geography(geography_dir, load_streets=True)

    print(f"  Boundary: {'✓' if boundary is not None else '✗'}")
    print(f"  Water: {'✓' if water is not None else '✗'} ({len(water) if water is not None else 0} features)")
    print(f"  Streets: {'✓' if edges is not None else '✗'} ({len(edges) if edges is not None else 0} segments)")

    return boundary, water, edges


def create_four_panel_map_with_geography(gdf_analysis, boundary, water, edges, output_file='detroit_housing_burden_with_geography.png', geographic_unit_name='Zip Code'):
    """
    Create the four-panel housing burden map with geographic context.
    """
    print(f"\nCreating four-panel map with geographic context ({geographic_unit_name})...")

    fig, axes = plt.subplots(2, 2, figsize=(20, 18))
    fig.suptitle(f'Housing Cost Burden in Detroit by {geographic_unit_name}\nAmerican Community Survey 2019-2023', 
                 fontsize=18, fontweight='bold', y=0.995)

    # Color scheme
    cmap = BURDEN_CMAP

    # Map 1: Renters 30%+
    ax1 = axes[0, 0]
    add_geography_layers(ax1, boundary, water, edges, gdf_analysis)
    gdf_analysis.plot(column='pct_renters_30plus', ax=ax1,
                      cmap=cmap, edgecolor='black', linewidth=0.1,
                      legend=True, scheme='UserDefined', classification_kwds={'bins': BINS}, alpha=ALPHA_BLOCKGROUPS,
                      legend_kwds={'loc': 'lower right', 'fmt': '{:.0f}%', 'title': '% of Renter Households'},
                      zorder=2)
    ax1.set_title('Renter Households: Cost Burden 30%+', fontsize=14, fontweight='bold', pad=10)
    ax1.axis('off')
    
    # Map 2: Owners 30%+
    ax2 = axes[0, 1]
    add_geography_layers(ax2, boundary, water, edges, gdf_analysis)
    gdf_analysis.plot(column='pct_owners_30plus', ax=ax2,
                      cmap=cmap, edgecolor='black', linewidth=0.1,
                      legend=True, scheme='UserDefined', classification_kwds={'bins': BINS}, alpha=ALPHA_BLOCKGROUPS,
                      legend_kwds={'loc': 'lower right', 'fmt': '{:.0f}%', 'title': '% of Owner Households'},
                      zorder=2)
    ax2.set_title('Owner Households: Cost Burden 30%+', fontsize=14, fontweight='bold', pad=10)
    ax2.axis('off')
    
    # Map 3: All households 30%+
    ax3 = axes[1, 0]
    add_geography_layers(ax3, boundary, water, edges, gdf_analysis)
    gdf_analysis.plot(column='pct_burden_30plus_all', ax=ax3, 
                      cmap=cmap, edgecolor='black', linewidth=0.1,
                      legend=True, scheme='UserDefined', classification_kwds={'bins': BINS}, alpha=ALPHA_BLOCKGROUPS,
                      legend_kwds={'loc': 'lower right', 'fmt': '{:.0f}%', 'title': '% of Households'},
                      zorder=2)
    ax3.set_title('All Households: Cost Burden 30%+', fontsize=14, fontweight='bold', pad=10)
    ax3.axis('off')
    
    # Map 4: All households 50%+ (severe)
    ax4 = axes[1, 1]
    add_geography_layers(ax4, boundary, water, edges, gdf_analysis)
    gdf_analysis.plot(column='pct_burden_50plus_all', ax=ax4,
                      cmap=cmap, edgecolor='black', linewidth=0.1,
                      legend=True, scheme='UserDefined', classification_kwds={'bins': BINS}, alpha=ALPHA_BLOCKGROUPS,
                      legend_kwds={'loc': 'lower right', 'fmt': '{:.0f}%', 'title': '% of Households'},
                      zorder=2)
    ax4.set_title('All Households: Severe Cost Burden 50%+', fontsize=14, fontweight='bold', pad=10)
    ax4.axis('off')
    
    plt.tight_layout()
    
    # Save
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved to: {output_file}")
    



def create_three_panel_map_with_geography(gdf_extended, boundary, water, edges, output_file='detroit_housing_market_health_with_geography.png', geographic_unit_name='Zip Code'):
    """
    Create the three-panel housing market health map with geographic context.
    """
    print(f"\nCreating three-panel market health map with geographic context ({geographic_unit_name})...")
    
    fig, axes = plt.subplots(1, 3, figsize=(26, 9))

    # 1. Housing Shortage Map (RED)
    ax1 = axes[0]
    add_geography_layers(ax1, boundary, water, edges, gdf_extended)

    # Create color column for housing shortage
    shortage_color_map = gdf_extended['housing_shortage'].map(SHORTAGE_COLORS)
    shortage_color_map = shortage_color_map.fillna(NEUTRAL)  # No data color
    
    gdf_extended.plot(
        color=shortage_color_map,
        ax=ax1,
        edgecolor='black',
        linewidth=0.3,
        alpha=ALPHA_BLOCKGROUPS,
        zorder=Z_DATA,
    )

    make_patch_legend(ax1, [
        (SHORTAGE_COLORS[True], 'Housing Shortage'),
        (SHORTAGE_COLORS[False], 'No Shortage'),
        (NEUTRAL, 'No Data'),
    ], loc='upper left', alpha=ALPHA_BLOCKGROUPS, frameon=True)
    ax1.set_title('Housing Shortage\n(Price/Income Ratio > 3)', fontsize=14, fontweight='bold')
    ax1.axis('off')
    
    # 2. Renter Accessibility Crisis Map (BLUE)
    ax2 = axes[1]
    add_geography_layers(ax2, boundary, water, edges, gdf_extended)
    
    # Create color column for accessibility crisis
    accessibility_color_map = gdf_extended['renter_accessibility_crisis'].map(ACCESSIBILITY_COLORS)
    accessibility_color_map = accessibility_color_map.fillna(NEUTRAL)  # No data color
    
    gdf_extended.plot(
        color=accessibility_color_map,
        ax=ax2,
        edgecolor='black',
        linewidth=0.3,
        alpha=ALPHA_BLOCKGROUPS,
        zorder=Z_DATA,
    )

    make_patch_legend(ax2, [
        (ACCESSIBILITY_COLORS[True], 'Accessibility Crisis'),
        (ACCESSIBILITY_COLORS[False], 'No Crisis'),
        (NEUTRAL, 'No Data'),
    ], loc='upper left', alpha=ALPHA_BLOCKGROUPS, frameon=True)
    ax2.set_title('Renter Accessibility Crisis\n(>50% pay 33%+ AND >25% pay 50%+)', 
                  fontsize=14, fontweight='bold')
    ax2.axis('off')
    
    # 3. Combined Map
    ax3 = axes[2]
    add_geography_layers(ax3, boundary, water, edges, gdf_extended)
    
    # Create color mapping
    if 'color' not in gdf_extended.columns:
        gdf_extended['color'] = gdf_extended['housing_category'].map(HOUSING_CATEGORY_COLORS)

    gdf_extended.plot(
        color=gdf_extended['color'],
        ax=ax3,
        edgecolor='black',
        linewidth=0.3,
        alpha=ALPHA_BLOCKGROUPS,
        zorder=Z_DATA,
    )

    make_patch_legend(ax3, [
        (HOUSING_CATEGORY_COLORS['Shortage Only'], 'Housing Shortage Only'),
        (HOUSING_CATEGORY_COLORS['Accessibility Only'], 'Accessibility Crisis Only'),
        (HOUSING_CATEGORY_COLORS['Both Issues'], 'Both Issues'),
        (HOUSING_CATEGORY_COLORS['Neither'], 'Neither Issue'),
        (HOUSING_CATEGORY_COLORS['No Data'], 'No Data'),
    ], loc='upper left', alpha=ALPHA_BLOCKGROUPS, frameon=True)
    
    ax3.set_title('Combined Housing Issues', fontsize=14, fontweight='bold')
    ax3.axis('off')
    
    plt.suptitle(f'Detroit Housing Market Health by {geographic_unit_name}\nACS 2019-2023', 
                 fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    # Save
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved to: {output_file}")
    


def main():
    """Main execution function."""
    print("="*70)
    print("Detroit Housing Maps with Geographic Context")
    print("="*70)
    
    # Load geography data
    boundary, water, edges = load_geography_data(GEOGRAPHY_DIR)
    
    # Load census analysis data
    print("\nLoading census analysis data...")
    
    # Try to load the GeoJSON files from the notebook output
    gdf_analysis_path = Path('../detroit_blockgroups_housing_burden.geojson')
    gdf_extended_path = Path('../detroit_housing_market_health.geojson')
    
    if not gdf_analysis_path.exists():
        print("ERROR: Could not find 'detroit_blockgroups_housing_burden.geojson'")
        print("Please run the Jupyter notebook first to generate the data files.")
        return
    
    gdf_analysis = gpd.read_file(gdf_analysis_path)
    print(f"  Loaded {len(gdf_analysis)} block groups (basic analysis)")
    
    # Create four-panel map
    create_four_panel_map_with_geography(
        gdf_analysis, boundary, water, edges,
        output_file='detroit_housing_burden_with_geography.png'
    )
    
    # Create three-panel map if extended data exists
    if gdf_extended_path.exists():
        gdf_extended = gpd.read_file(gdf_extended_path)
        print(f"  Loaded {len(gdf_extended)} block groups (extended analysis)")
        
        create_three_panel_map_with_geography(
            gdf_extended, boundary, water, edges,
            output_file='detroit_housing_market_health_with_geography.png'
        )
    else:
        print("\nNote: Extended analysis data not found. Skipping three-panel map.")
        print("Run the full notebook to generate 'detroit_housing_market_health.geojson'")
    
    print("\n" + "="*70)
    print("Complete! Your enhanced maps have been saved.")
    print("="*70)


if __name__ == "__main__":
    main()
