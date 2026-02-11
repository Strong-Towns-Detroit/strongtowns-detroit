#!/usr/bin/env python3
"""
OSMnx Graph Simplification for Detroit Streets

This script demonstrates various graph simplification techniques using OSMnx
for the street network of Detroit, Michigan, with added coastline and municipal boundary.
"""

import osmnx as ox
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

from strongtowns_detroit.geo.streets import compare_networks

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = True


def download_detroit_geography():
    """
    Download the municipal boundary and coastline for Detroit, Michigan.
    
    Returns:
    --------
    boundary : GeoDataFrame
        Detroit municipal boundary
    water : GeoDataFrame
        Water bodies and coastline
    """
    print("Downloading Detroit geography (boundary and water features)...")
    
    # Get municipal boundary
    boundary = ox.geocode_to_gdf("Detroit, Michigan, USA")
    
    # Get water features (rivers, lakes, etc.)
    # Using OSM tags for natural water features
    tags = {
        'natural': ['water', 'coastline', 'bay'],
        'waterway': ['river', 'riverbank', 'canal']
    }
    
    try:
        water = ox.features_from_place(
            "Detroit, Michigan, USA",
            tags=tags
        )
        print(f"Downloaded {len(water)} water features")
    except Exception as e:
        print(f"Note: Could not download water features: {e}")
        water = None
    
    print(f"Downloaded municipal boundary")
    
    return boundary, water


def download_detroit_network(network_type='drive'):
    """
    Download the street network for Detroit, Michigan.
    
    Parameters:
    -----------
    network_type : str
        Type of street network ('drive', 'walk', 'bike', 'all')
    
    Returns:
    --------
    G : networkx.MultiDiGraph
        The unsimplified street network
    """
    print(f"Downloading {network_type} network for Detroit, Michigan...")
    
    # Download network for Detroit
    G = ox.graph_from_place(
        "Detroit, Michigan, USA",
        network_type=network_type,
        custom_filter='["highway"~"motorway|trunk|primary|secondary|tertiary"]',
        simplify=False  # Get unsimplified network first
    )
    
    print(f"Downloaded network with {len(G.nodes)} nodes and {len(G.edges)} edges")
    return G


def simplify_network(G, method='basic'):
    """
    Simplify the street network using OSMnx.
    
    Parameters:
    -----------
    G : networkx.MultiDiGraph
        The unsimplified street network
    method : str
        Simplification method: 'basic', 'strict', or 'consolidate'
    
    Returns:
    --------
    G_simplified : networkx.MultiDiGraph
        The simplified street network
    """
    print(f"\nApplying {method} simplification...")
    
    if method == 'basic':
        # Basic simplification: removes interstitial nodes between intersections
        # This is the default OSMnx simplification
        G_simplified = ox.simplify_graph(G)
        
    elif method == 'strict':
        # Strict simplification: only removes nodes if they have exactly 2 neighbors
        # and are not at a change in street name or highway type
        G_simplified = ox.simplify_graph(G)
        
    elif method == 'consolidate':
        # Consolidate intersections: merge nearby nodes that represent
        # the same intersection in reality
        G_simplified = ox.consolidate_intersections(
            G,
            tolerance=15,  # meters
            rebuild_graph=True,
            dead_ends=False
        )
        # Then apply basic simplification
        G_simplified = ox.simplify_graph(G_simplified)
    
    else:
        raise ValueError(f"Unknown method: {method}")
    
    print(f"Simplified network has {len(G_simplified.nodes)} nodes and {len(G_simplified.edges)} edges")
    
    return G_simplified


def visualize_networks(G_original, G_simplified, boundary, water, method_name, output_dir='output'):
    """
    Create side-by-side visualization of original and simplified networks with geography.
    
    Parameters:
    -----------
    G_original : networkx.MultiDiGraph
        Original street network
    G_simplified : networkx.MultiDiGraph
        Simplified street network
    boundary : GeoDataFrame
        Municipal boundary
    water : GeoDataFrame
        Water features
    method_name : str
        Name of simplification method for labeling
    output_dir : str
        Directory to save output files
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print(f"\nCreating visualization for {method_name} method...")
    
    fig, ax = plt.subplots(1, 1, figsize=(20, 20))
    
    # Set background color
    ax.set_facecolor('#e8f4f8')  # Light blue for water
    fig.patch.set_facecolor('white')
    
    # Plot water features first (background)
    if water is not None and len(water) > 0:
        # Ensure water is in the same CRS as the graph
        water_plot = water.to_crs(epsg=4326)
        water_plot.plot(
            ax=ax,
            facecolor='#c6e3f0',
            edgecolor='#7fb3d5',
            linewidth=0.5,
            alpha=0.7,
            zorder=1
        )
    
    # Plot municipal boundary
    if boundary is not None:
        boundary_plot = boundary.to_crs(epsg=4326)
        boundary_plot.boundary.plot(
            ax=ax,
            edgecolor='#2c3e50',
            linewidth=2.5,
            linestyle='--',
            alpha=0.8,
            zorder=3
        )
    
    # Plot simplified network on top
    ox.plot_graph(
        G_simplified,
        ax=ax,
        node_size=0,
        node_color='gray',
        edge_color='#34495e',
        edge_linewidth=1,
        bgcolor='white',
        show=False,
        close=False
    )
    
    ax.set_title(
        f'Detroit Street Network - Simplified ({method_name})\n'
        f'{len(G_simplified.nodes):,} nodes, {len(G_simplified.edges):,} edges',
        fontsize=16,
        fontweight='bold',
        pad=20
    )
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#34495e', label='Street Network'),
        Patch(facecolor='#c6e3f0', edgecolor='#7fb3d5', label='Water Bodies'),
        Patch(facecolor='none', edgecolor='#2c3e50', linestyle='--', linewidth=2, label='City Boundary')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=12, framealpha=0.9)
    
    plt.tight_layout()
    
    output_file = output_path / f'detroit_network_{method_name}_with_geography.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Saved visualization to {output_file}")


def save_geography(boundary, water, output_dir='output'):
    """
    Save geography data (boundary and water) to files.
    
    Parameters:
    -----------
    boundary : GeoDataFrame
        Municipal boundary
    water : GeoDataFrame
        Water features
    output_dir : str
        Directory to save output files
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print("\nSaving geography data to files...")
    
    # Save boundary
    if boundary is not None:
        boundary.to_file(
            output_path / 'detroit_boundary.geojson',
            driver='GeoJSON'
        )
        boundary.to_file(
            output_path / 'detroit_boundary.gpkg',
            driver='GPKG'
        )
        print(f"Saved boundary to detroit_boundary.geojson and detroit_boundary.gpkg")
    
    # Save water features
    if water is not None and len(water) > 0:
        # Clean up column names - replace problematic characters
        water_clean = water.copy()
        water_clean.columns = [col.replace(':', '_').replace(' ', '_') for col in water_clean.columns]
        
        # Remove the problematic NHD_FType column if it exists
        if 'NHD_FType' in water_clean.columns:
            water_clean = water_clean.drop(columns=['NHD_FType'])
        
        water_clean.to_file(
            output_path / 'detroit_water.geojson',
            driver='GeoJSON'
        )
        water_clean.to_file(
            output_path / 'detroit_water.gpkg',
            driver='GPKG'
        )
        print(f"Saved water features to detroit_water.geojson and detroit_water.gpkg")


def save_networks(G_original, G_simplified, method_name, output_dir='output'):
    """
    Save network data to files.
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print(f"\nSaving {method_name} networks to files...")
    
    # Save as GraphML (preserves attributes)
    ox.save_graphml(
        G_simplified,
        filepath=output_path / f'detroit_network_{method_name}.graphml'
    )
    
    # Save as GeoPackage (for GIS software)
    ox.save_graph_geopackage(
        G_simplified,
        filepath=output_path / f'detroit_network_{method_name}.gpkg'
    )
    
    print(f"Saved network files to {output_path}/")


def main():
    """
    Main execution function.
    """
    print("="*60)
    print("OSMnx Graph Simplification for Detroit Streets")
    print("with Geographic Context (Boundary & Coastline)")
    print("="*60)
    
    # Download geography first
    boundary, water = download_detroit_geography()
    save_geography(boundary, water)
    
    # Download street network
    G_original = download_detroit_network(network_type='drive')
    
    # Apply different simplification methods
    methods = {
        'basic': 'Basic Simplification',
        'strict': 'Strict Simplification'
    }
    
    results = []
    
    for method, description in methods.items():
        print(f"\n{'='*60}")
        print(f"Processing: {description}")
        print(f"{'='*60}")
        
        G_simplified = simplify_network(G_original.copy(), method=method)
        
        comparison = compare_networks(G_original, G_simplified, description)
        comparison['method'] = method
        results.append(comparison)
        
        visualize_networks(G_original, G_simplified, boundary, water, method)
        
        save_networks(G_original, G_simplified, method)
    
    print(f"\n{'='*60}")
    print("SUMMARY: Simplification Method Comparison")
    print(f"{'='*60}")
    
    df = pd.DataFrame(results)
    df = df[['method', 'original_nodes', 'simplified_nodes', 'node_reduction_pct',
             'original_edges', 'simplified_edges', 'edge_reduction_pct']]
    
    print("\n" + df.to_string(index=False))
    
    output_path = Path('output')
    output_path.mkdir(exist_ok=True)
    df.to_csv(output_path / 'simplification_comparison.csv', index=False)
    print(f"\nSaved comparison table to output/simplification_comparison.csv")
    
    print(f"\n{'='*60}")
    print("Processing complete!")
    print(f"{'='*60}")
    print("\nOutput files saved in 'output/' directory:")
    print("  - Network visualizations with geography (PNG)")
    print("  - Network files (GraphML, GeoPackage)")
    print("  - Geography files (GeoJSON, GeoPackage):")
    print("    * detroit_boundary.geojson/gpkg - Municipal boundary")
    print("    * detroit_water.geojson/gpkg - Water features/coastline")
    print("  - Comparison statistics (CSV)")


if __name__ == "__main__":
    main()
