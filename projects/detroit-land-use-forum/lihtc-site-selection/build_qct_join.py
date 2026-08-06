"""Join Detroit parcel centroids to HUD 2026 Qualified Census Tracts.

Expensive step (reads a 653 MB GeoPackage), so the result is cached to parquet
and every downstream funnel script reads the cache instead.
"""
import geopandas as gpd, pandas as pd, pathlib

OUT = pathlib.Path("projects/detroit-land-use-forum/lihtc-site-selection/output")
CACHE = OUT / "parcels_qct.parquet"

COLS = ["parcel_id", "address", "taxpayer_1", "property_class_description",
        "zoning_district", "total_acreage", "total_square_footage", "frontage",
        "is_improved", "amt_assessed_value", "neighborhood", "zip_code"]

print("reading parcels…")
g = gpd.read_file("pipelines/parcel-data/parcels_with_compliance.gpkg",
                  columns=COLS, engine="pyogrio")
print(f"  {len(g):,} parcels, crs={g.crs}")

# Centroids in a projected CRS, then to WGS84 for the tract join.
cen = g.geometry.centroid.to_crs(4326)
df = pd.DataFrame(g.drop(columns="geometry"))
pts = gpd.GeoDataFrame(df, geometry=cen, crs=4326)

qct = gpd.read_file("data/lihtc/qct_2026_wayne.geojson")[["GEOID", "geometry"]]
print(f"  {len(qct)} QCT tracts")

j = gpd.sjoin(pts, qct, how="left", predicate="within")
j["in_qct"] = j["GEOID"].notna()
j["lon"] = j.geometry.x
j["lat"] = j.geometry.y

out = pd.DataFrame(j.drop(columns=["geometry", "index_right"]))
out = out.rename(columns={"GEOID": "qct_geoid"})
out.to_parquet(CACHE, index=False)
print(f"wrote {CACHE}  ({len(out):,} rows)")
print(f"  parcels in a QCT: {out['in_qct'].sum():,} ({100*out['in_qct'].mean():.1f}%)")
