import sys
import os
from pathlib import Path

# Add src to path to import the modules
# Script is in src/scripts, so we need to go up one level
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from strongtowns_detroit.census.fetcher import DetroitCensusFetcher
import detroit_maps_with_geography as dmaps

def main():
    print("="*70)
    print("Detroit Housing Analysis Pipeline")
    print("="*70)

    fetcher = DetroitCensusFetcher()  # loads API key from .env
    
    # Paths relative to src/scripts/run_detroit_analysis.py
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    
    resources_data_dir = project_root / 'resources' / 'data'
    resources_images_dir = project_root / 'resources' / 'images'
    
    # Ensure output dirs exist
    resources_data_dir.mkdir(parents=True, exist_ok=True)
    resources_images_dir.mkdir(parents=True, exist_ok=True)

    # Geography directory is in street_simplification/output
    geo_dir = project_root / 'street_simplification' / 'output'
    if not geo_dir.exists():
        print(f"Warning: Geography directory {geo_dir} not found. Maps might lack context.")
    
    # Load geography once
    boundary, water, edges = dmaps.load_geography_data(geo_dir)

    # Configurations
    configs = [
        {
            'name': 'Zip Code',
            'filename_suffix': 'zcta',
            'input_file': 'City_of_Detroit_Zip_Code_Tabulation_Areas_-3837086369644795658.geojson',
            'merge_col': 'zipcode'
        },
        {
            'name': 'Council District',
            'filename_suffix': 'district',
            'input_file': 'Detroit_City_Council_Districts_2026.geojson',
            'merge_col': 'district_number'
        }
    ]

    for config in configs:
        print(f"\n\nProcessing {config['name']}...")
        print("-" * 40)
        
        input_path = resources_data_dir / config['input_file']
        
        # 1. Fetch and Aggregate
        try:
            detroit_data = fetcher.fetch_and_aggregate(str(input_path), merge_col=config['merge_col'])
            
            # Save aggregated data
            output_data_path = resources_data_dir / f"detroit_{config['filename_suffix']}_aggregated.geojson"
            detroit_data.to_file(output_data_path, driver='GeoJSON')
            print(f"✓ Saved aggregated data to {output_data_path}")
            
            print(f"Data ready for {len(detroit_data)} {config['name']}s")
            
            # 2. Generate Maps
            dmaps.create_four_panel_map_with_geography(
                detroit_data, 
                boundary, 
                water, 
                edges,
                output_file=str(resources_images_dir / f"detroit_{config['filename_suffix']}_housing_burden_map.png"),
                geographic_unit_name=config['name']
            )
            
            dmaps.create_three_panel_map_with_geography(
                detroit_data,
                boundary,
                water,
                edges,
                output_file=str(resources_images_dir / f"detroit_{config['filename_suffix']}_market_health_map.png"),
                geographic_unit_name=config['name']
            )
            
        except Exception as e:
            print(f"ERROR processing {config['name']}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
