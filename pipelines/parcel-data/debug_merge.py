import geopandas as gpd
import pandas as pd

def debug_ids():
    print("Loading Parcels.geojson...")
    gdf = gpd.read_file("Parcels.geojson")
    
    print("Loading parcel-data-cleaned.csv...")
    csv = pd.read_csv("parcel-data-cleaned.csv", low_memory=False)
    
    gdf_ids = set(gdf['object_id'].astype(int))
    csv_ids = set(csv['object_id'].astype(int))
    
    print(f"GeoJSON Objects: {len(gdf_ids)}")
    print(f"CSV Objects: {len(csv_ids)}")
    
    overlap = gdf_ids.intersection(csv_ids)
    print(f"Overlap Count: {len(overlap)}")
    
    print("Sample GeoJSON IDs:", list(gdf_ids)[:5])
    print("Sample CSV IDs:", list(csv_ids)[:5])

if __name__ == "__main__":
    debug_ids()
