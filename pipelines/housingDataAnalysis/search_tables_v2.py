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

search_groups("Roomer")
search_groups("Institutional")
