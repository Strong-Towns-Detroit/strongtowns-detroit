"""Can small vacant lots be assembled into LIHTC-scale sites?

Dissolves touching vacant parcels into contiguous blocks and measures the
resulting developable footprints -- the honest test of "just assemble lots".

Areas are computed in UTM 17N (EPSG:32617). Web Mercator (the source CRS)
inflates area by ~1/cos(lat)^2 ~ 1.83x at Detroit's latitude.
"""
import geopandas as gpd, pandas as pd, pathlib
OUT = pathlib.Path("projects/detroit-land-use-forum/lihtc-site-selection/output")
UTM = 32617
ACRE = 4046.856

print("reading vacant parcels…")
g = gpd.read_file(
    "pipelines/parcel-data/parcels_with_compliance.gpkg",
    columns=["parcel_id", "address", "taxpayer_1", "property_class_description", "total_acreage"],
    where="property_class_description LIKE '%VACANT%'", engine="pyogrio").to_crs(UTM)
print(f"  {len(g):,} vacant parcels, reprojected to UTM 17N")

# Validate geometry area against the assessor's acreage field.
g["geom_acres"] = g.geometry.area / ACRE
rec = pd.to_numeric(g["total_acreage"], errors="coerce")
ok = rec.notna() & (rec > 0)
ratio = (g.loc[ok, "geom_acres"] / rec[ok]).median()
print(f"  median(geometry acres / recorded acres) = {ratio:.3f}   (1.0 == agreement)")

tp = g["taxpayer_1"].astype(str).str.upper()
g["public"] = tp.str.contains("DETROIT LAND BANK|LAND BANK|CITY OF DETROIT|DETROIT, CITY|DETROIT PARKS|DETROIT HOUSING", na=False)

qct = gpd.read_file("data/lihtc/qct_2026_wayne.geojson")[["GEOID","geometry"]].to_crs(UTM)

for label, sub, tag in [("ALL vacant", g, "all"), ("PUBLICLY-OWNED vacant", g[g["public"]], "public")]:
    print(f"\n--- {label}: {len(sub):,} parcels ---")
    merged = sub.geometry.buffer(0.75).union_all()   # true metres now
    blocks = gpd.GeoDataFrame(geometry=list(merged.geoms), crs=UTM)
    blocks["acres"] = blocks.geometry.area / ACRE
    # count constituent parcels per block (transaction cost of assembly)
    j = gpd.sjoin(sub[["parcel_id","geometry"]], blocks.reset_index()[["index","geometry"]],
                  how="left", predicate="intersects")
    cnt = j.groupby("index").size()
    blocks["n_parcels"] = blocks.index.map(cnt).fillna(0).astype(int)
    # QCT membership by block centroid
    cent = gpd.GeoDataFrame(blocks.drop(columns="geometry"), geometry=blocks.geometry.centroid, crs=UTM)
    blocks["in_qct"] = gpd.sjoin(cent, qct, how="left", predicate="within")["GEOID"].notna().values

    print(f"  contiguous blocks: {len(blocks):,}")
    print(f"  {'thresh':>7} {'blocks':>8} {'in QCT':>8} {'med parcels/block':>18}")
    for a in [1.0, 1.5, 2.0, 3.0, 4.0]:
        b = blocks[blocks["acres"] >= a]
        bq = b[b["in_qct"]]
        med = int(bq["n_parcels"].median()) if len(bq) else 0
        print(f"  >={a:>4.1f} ac {len(b):>8,} {len(bq):>8,} {med:>18,}")
    blocks[(blocks["acres"] >= 1.5)].to_file(OUT / f"assembled_{tag}.gpkg", driver="GPKG")
    blocks.to_parquet(OUT / f"blocks_{tag}.parquet")
