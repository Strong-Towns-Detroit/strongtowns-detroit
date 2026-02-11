import osmnx as ox
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
from pathlib import Path

def render_detroit_strait():
    print("Downloading Detroit geography...")
    
    # Configure OSMnx
    ox.settings.use_cache = True
    ox.settings.log_console = True
    
    # Define tags for water features
    tags = {
        'natural': ['water', 'coastline', 'bay'],
        'waterway': ['river', 'riverbank', 'canal'],
        'place': ['sea', 'ocean']
    }
    
    # 1. Download Detroit Boundary (for view trimming)
    print("Downloading Detroit boundary...")
    detroit_boundary = ox.geocode_to_gdf("Detroit, Michigan, USA")
    
    # 2. Download Water Features (Detroit + Windsor to cover the river fully)
    print("Downloading water features for Detroit and Windsor...")
    places = ["Detroit, Michigan, USA", "Windsor, Ontario, Canada"]
    
    try:
        water = ox.features_from_place(places, tags=tags)
    except Exception as e:
        print(f"Error downloading features: {e}")
        return

    print(f"Downloaded {len(water)} water features")
    
    # Filter for the Detroit River
    # We look for "Detroit River" in the name, but since we have data from both sides,
    # we might get multiple features or a large combined set.
    # To be safe and ensure we get the main channel, we can filter by name or just plot everything
    # and let the view trimming handle the focus.
    
    # Let's try to filter for major water bodies to avoid small ponds if possible,
    # but "Detroit River" name check is a good start.
    
    detroit_river = water[water['name'].fillna('').str.contains('Detroit River', case=False)]
    
    if len(detroit_river) == 0:
        print("Could not find 'Detroit River' by name. Using all water features.")
        plot_data = water
    else:
        print(f"Found {len(detroit_river)} features matching 'Detroit River'")
        plot_data = detroit_river

    # Dissolve geometries to remove internal boundaries (e.g. international border)
    print("Dissolving geometries...")
    plot_data = plot_data.dissolve()

    # Setup the plot
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    
    # Plot
    # User wants: "outline of the strait in thick black, and then everything else in white"
    # We plot the polygon with white facecolor and black edgecolor
    
    plot_data.plot(
        ax=ax,
        facecolor='white',
        edgecolor='black',
        linewidth=2.0
    )
    
    # Trim the view to Detroit's bounding box
    # This effectively "crops" the map without cutting the geometries
    minx, miny, maxx, maxy = detroit_boundary.total_bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    
    # Remove axes
    ax.axis('off')
    
    # Save
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'detroit_strait_stylized.png'
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved stylized map to {output_file}")

if __name__ == "__main__":
    render_detroit_strait()
