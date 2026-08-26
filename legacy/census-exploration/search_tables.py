import requests
import json

def search_groups(query):
    url = "https://api.census.gov/data/2023/acs/acs5/groups.json"
    print(f"Fetching groups from {url}...")
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            groups = resp.json().get('groups', [])
            print(f"Found {len(groups)} groups. Searching for '{query}'...")
            found = []
            for g in groups:
                title = g.get('description', '') or g.get('title', '')
                if query.lower() in title.lower():
                    found.append(g)
            
            for f in found[:10]:
                print(f"{f['name']}: {f.get('description') or f.get('title')}")
        else:
            print(f"Error {resp.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

def get_table_vars(table_id):
    url = f"https://api.census.gov/data/2023/acs/acs5/groups/{table_id}.json"
    print(f"\nFetching vars for {table_id}...")
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            vars_dict = data.get('variables', {})
            sorted_keys = sorted(vars_dict.keys())
            for key in sorted_keys:
                if key.endswith("E"):
                    label = vars_dict[key].get('label', 'No Label')
                    print(f"{key}: {label}")
    except Exception as e:
        print(f"Exception: {e}")

search_groups("Nonrelatives")
search_groups("Group Quarters")
