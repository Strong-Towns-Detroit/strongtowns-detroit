import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path

from strongtowns_detroit.geo.loader import load_geography, prepare_water, sync_crs
from strongtowns_detroit.mapping.layers import make_patch_legend
from strongtowns_detroit.mapping.colors import (
    WATER_PARCEL, BUILDABLE, NOT_BUILDABLE, Z_WATER, Z_DATA, Z_BOUNDARY,
)

def map_parcels():
    print("Loading data...")

    # Paths
    geography_dir = Path('../housingDataAnalysis/street_simplification/output')
    parcels_path = Path('parcels_with_buildability.gpkg')
    output_file = 'detroit_buildable_parcels_map.png'

    # Load Geography
    print("Loading geography layers...")
    boundary, water, _ = load_geography(geography_dir)

    # Load Parcels
    print("Loading parcels...")
    parcels = gpd.read_file(parcels_path)

    # Ensure CRS match
    parcels = sync_crs(parcels, target_crs=boundary.crs)

    unknown_color = NOT_BUILDABLE

    # Prepare water: CRS sync, filter Lake St. Clair, clip to boundary
    print("Preparing water features...")
    water = prepare_water(water, boundary)

    # Plotting
    print("Creating map...")
    fig, ax = plt.subplots(figsize=(20, 20))

    # 1. Water (Background)
    water.plot(ax=ax, color=WATER_PARCEL, edgecolor='none', alpha=0.5, zorder=Z_WATER)

    # 2. Parcels
    parcels['color'] = parcels['isBuildable'].map({True: BUILDABLE, False: NOT_BUILDABLE})
    parcels['color'] = parcels['color'].fillna(unknown_color)
    # Grey out parcels owned by Detroit Parks & Recreation
    parcels.loc[parcels['taxpayer_1'] == 'DETROIT PARKS & RECREATION', 'color'] = unknown_color

    parcels.plot(
        ax=ax,
        color=parcels['color'],
        edgecolor='none',
        alpha=0.9,
        zorder=Z_DATA,
    )

    # 3. Boundary (Top)
    boundary.boundary.plot(ax=ax, color='black', linewidth=0.5, zorder=Z_BOUNDARY)

    # Formatting
    ax.set_title('Detroit Parcel Buildability\n(Green: Buildable, Red: Not Buildable)', fontsize=24)
    ax.axis('off')

    make_patch_legend(ax, [
        (BUILDABLE, 'Buildable'),
        (NOT_BUILDABLE, 'Not Buildable'),
        (unknown_color, 'Unknown'),
    ], loc='lower right', fontsize=16)

    plt.tight_layout()

    # Save
    print(f"Saving map to {output_file}...")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print("Done!")

if __name__ == "__main__":
    map_parcels()
