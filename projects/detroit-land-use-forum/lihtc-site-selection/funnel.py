"""LIHTC site-selection attrition funnel for Detroit.

Answers: how many Detroit parcels could actually host a LIHTC development?
Each gate is a real constraint on site selection, applied in sequence.
"""
import pandas as pd, pathlib, json
OUT = pathlib.Path("projects/detroit-land-use-forum/lihtc-site-selection/output")
df = pd.read_parquet(OUT / "parcels_qct.parquet")

tp = df["taxpayer_1"].astype(str).str.upper().fillna("")
df["acres"] = pd.to_numeric(df["total_acreage"], errors="coerce")
df["vacant"] = df["property_class_description"].astype(str).str.contains("VACANT", na=False)

# "Vacant" in the assessor file means no assessed structure -- it includes active
# parkland, rail corridor, and utility right-of-way. None of that is developable.
PROTECTED = ("DETROIT PARKS|PARKS AND RECREATION|PARKS & RECREATION|WATER DEPT|"
             "WATER DEPARTMENT|CONSOLIDATED RAIL|CONRAIL|MICHIGAN DEPT OF TRANSPORTATION|"
             r"\bMDOT\b|BRIDGE AUTHORITY|DTE |DTE ELECTRIC|CEMETERY|GRAND TRUNK|RAILROAD|RAILWAY")
DISPOSABLE = ("DETROIT LAND BANK|LAND BANK|CITY OF DETROIT|DETROIT, CITY|DETROIT HOUSING|"
              "DETROIT BUILDING AUTHORITY|ECONOMIC DEVELOPMENT CORP")

df["protected"]  = tp.str.contains(PROTECTED, na=False, regex=True)
df["public_disp"] = tp.str.contains(DISPOSABLE, na=False, regex=True) & ~df["protected"]

MIN_AC = 1.5   # ~40 units at a realistic Detroit density; sensitivity reported below

gates = [
    ("Every parcel in Detroit",                      lambda d: d),
    ("In a 2026 Qualified Census Tract",             lambda d: d[d.in_qct]),
    ("Vacant / no assessed structure",               lambda d: d[d.vacant]),
    ("Not parkland, rail, or utility corridor",      lambda d: d[~d.protected]),
    (f"At least {MIN_AC} acres (a ~40-unit site)",   lambda d: d[d.acres >= MIN_AC]),
    ("Publicly owned and disposable",                lambda d: d[d.public_disp]),
]
rows, s, prev = [], df, len(df)
print(f"{'GATE':<44}{'REMAIN':>10}{'% OF ALL':>10}{'CUT':>10}")
for label, fn in gates:
    s = fn(s); cut = prev - len(s); prev = len(s)
    rows.append({"gate": label, "remaining": len(s), "pct_of_all": 100*len(s)/len(df), "cut": cut})
    print(f"{label:<44}{len(s):>10,}{100*len(s)/len(df):>9.2f}%{cut:>10,}")

print(f"\n--- Sensitivity to the site-size threshold ---")
b = df[df.in_qct & df.vacant & ~df.protected]
for a in [1.0, 1.5, 2.0, 3.0, 5.0]:
    x = b[b.acres >= a]
    print(f"  >= {a:>4.1f} ac : {len(x):>5,} sites   publicly disposable: {int(x.public_disp.sum()):>4,}")

final = df[df.in_qct & df.vacant & ~df.protected & (df.acres >= MIN_AC) & df.public_disp]
final = final.sort_values("acres", ascending=False)
final.to_csv(OUT / "candidate_sites.csv", index=False)
json.dump(rows, open(OUT / "funnel.json", "w"), indent=1)

bz = final[final.address.astype(str).str.contains("7737 KERCHEVAL", na=False)]
print(f"\nFinal candidate set: {len(final)} sites, {final.acres.sum():.0f} acres")
print(f"Butzel present: {len(bz)>0}   size rank {final.acres.rank(ascending=False)[bz.index].iloc[0]:.0f} of {len(final)}")
print("\nTop 12 genuinely disposable public sites:")
print(final.head(12)[["address","taxpayer_1","acres","neighborhood"]].to_string(index=False))
