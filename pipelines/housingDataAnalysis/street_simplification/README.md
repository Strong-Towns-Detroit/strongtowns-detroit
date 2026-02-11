# OSMnx Graph Simplification for Detroit Streets

This script demonstrates various graph simplification techniques using OSMnx for the street network of Detroit, Michigan.

## Overview

OSMnx graph simplification reduces network complexity by removing unnecessary nodes while preserving the essential topology of the street network. This is useful for:

- Network analysis and routing algorithms
- Visualization and mapping
- Reducing computational complexity
- Creating cleaner network representations

## Features

The script implements three different simplification methods:

1. **Basic Simplification** (`strict=False`)
   - Removes interstitial nodes between intersections
   - Most aggressive simplification
   - Replaces long street segments with single edges

2. **Strict Simplification** (`strict=True`)
   - Only removes nodes with exactly 2 neighbors
   - Preserves nodes at street name or highway type changes
   - More conservative approach

3. **Consolidation + Simplification**
   - First consolidates nearby nodes (within 15m tolerance)
   - Merges nodes that represent the same intersection
   - Then applies basic simplification
   - Useful for cleaning up complex intersections

## Installation

### Requirements

- Python 3.8 or higher
- pip package manager

### Setup

1. Install the required packages:

```bash
pip install -r requirements.txt
```

Or install packages individually:

```bash
pip install osmnx networkx matplotlib pandas geopandas
```

## Usage

### Basic Usage

Simply run the script:

```bash
python detroit_street_simplification.py
```

The script will:
1. Download the Detroit street network from OpenStreetMap
2. Apply all three simplification methods
3. Generate visualizations comparing original vs simplified networks
4. Save network data in multiple formats
5. Calculate and display network statistics
6. Create a summary comparison CSV

### Output Files

All output files are saved in the `output/` directory:

- **Visualizations**: PNG files showing side-by-side comparisons
  - `detroit_network_basic.png`
  - `detroit_network_strict.png`
  - `detroit_network_consolidate.png`

- **Network Data**:
  - GraphML format (`.graphml`) - preserves all attributes
  - GeoPackage format (`.gpkg`) - for QGIS and other GIS software
  - Shapefile format (folder) - for legacy GIS applications

- **Statistics**:
  - `simplification_comparison.csv` - summary table comparing all methods

### Customization

You can modify the script to:

#### Change the network type:

```python
G_original = download_detroit_network(network_type='walk')  # or 'bike', 'all'
```

#### Adjust consolidation tolerance:

```python
# In the simplify_network function, modify:
G_simplified = ox.consolidate_intersections(
    G,
    tolerance=10,  # Change from 15 to 10 meters
    rebuild_graph=True,
    dead_ends=False
)
```

#### Change the location:

```python
# In the download_detroit_network function:
G = ox.graph_from_place(
    "Ann Arbor, Michigan, USA",  # Different city
    network_type=network_type,
    simplify=False
)
```

## Understanding the Results

### Key Statistics

- **Node Reduction**: Percentage of nodes removed during simplification
- **Edge Reduction**: Percentage of edges removed/consolidated
- **Average Street Length**: Mean length of street segments
- **Average Node Degree**: Average number of connections per node
- **Circuity**: Ratio of network distances to straight-line distances

### Interpretation

- Higher reduction percentages indicate more aggressive simplification
- Basic simplification typically removes 40-60% of nodes
- Strict simplification is more conservative (20-40% reduction)
- Consolidation helps clean up complex intersections and roundabouts

## Examples

### Example Output

```
Processing: Basic Simplification
=============================================================
Original network: 45,234 nodes, 98,765 edges
Simplified network: 18,456 nodes, 42,123 edges
Reduction: 59.2% nodes, 57.3% edges

Average street length: 127.45 m
Average node degree: 2.85
Circuity average: 1.042
```

## Technical Details

### OSMnx Simplification Algorithm

The simplification process:

1. Identifies nodes that are strictly between intersections
2. Removes these interstitial nodes
3. Combines the edges on either side into a single edge
4. Preserves edge attributes (street names, types, etc.)
5. Updates edge geometry to maintain accurate geographic representation

### Data Source

Street network data is downloaded from OpenStreetMap via the Overpass API. The data includes:

- All drivable roads (when using `network_type='drive'`)
- Street names and classifications
- Geographic coordinates
- One-way information
- Speed limits (where available)

## Troubleshooting

### Common Issues

**Issue**: Script fails to download network
- **Solution**: Check internet connection; OSM servers may be temporarily unavailable

**Issue**: Memory error with large networks
- **Solution**: Reduce area size or download smaller sections of the city

**Issue**: Visualizations look cluttered
- **Solution**: Adjust node_size and edge_linewidth parameters in `visualize_networks()`

## References

- [OSMnx Documentation](https://osmnx.readthedocs.io/)
- [OSMnx GitHub Repository](https://github.com/gboeing/osmnx)
- Boeing, G. (2017). "OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks." *Computers, Environment and Urban Systems*, 65, 126-139.

## License

This script is provided as-is for educational and research purposes.

## Author

Created using OSMnx library by Geoff Boeing
