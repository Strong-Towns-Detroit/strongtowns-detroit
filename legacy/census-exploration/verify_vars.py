import pytidycensus as tc
import pandas as pd

from strongtowns_detroit.config import get_census_api_key

tc.set_census_api_key(get_census_api_key())

def inspect_table(table_id):
    print(f"\nInspecting Table: {table_id}")
    try:
        df = tc.get_acs(
            geography='place',
            variables=table_id, # pytidycensus allows passing table ID to get all vars
            year=2023,
            survey='acs5',
            state='MI',
            geometry=False
        )
        print(f"Columns found: {len(df.columns)}")
        print(df.columns.tolist())
        
    except Exception as e:
        print(f"Error fetching {table_id}: {e}")

inspect_table("group(B09019)")
inspect_table("group(B26001)")
