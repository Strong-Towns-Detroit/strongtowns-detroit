import requests
import json

def get_table_vars(table_id):
    url = f"https://api.census.gov/data/2023/acs/acs5/groups/{table_id}.json"
    print(f"Fetching {url}...")
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            # The variables are in 'variables' dict
            vars_dict = data.get('variables', {})
            print(f"Found {len(vars_dict)} variables for {table_id}")
            
            # Sort by key to see order
            sorted_keys = sorted(vars_dict.keys())
            for key in sorted_keys:
                # Filter for Estimate variables (usually end in E)
                if key.endswith("E"):
                    label = vars_dict[key].get('label', 'No Label')
                    print(f"{key}: {label}")
        else:
            print(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

get_table_vars("B09019")
get_table_vars("B26001")
