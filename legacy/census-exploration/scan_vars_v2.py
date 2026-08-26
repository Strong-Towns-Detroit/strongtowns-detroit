import requests
import json

def scan_tables(prefix, start, end):
    print(f"Scanning {prefix} {start}-{end}...")
    for i in range(start, end + 1):
        table_id = f"{prefix}{i:03d}"
        url = f"https://api.census.gov/data/2023/acs/acs5/groups/{table_id}.json"
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                vars_dict = data.get('variables', {})
                for key, val in vars_dict.items():
                    label = val.get('label', '')
                    if "Roomer" in label or "Boarder" in label:
                        print(f"FOUND in {table_id}: {key} - {label}")
                    if "Non-institutional" in label or "Group Quarters" in label:
                         if "Group quarters" in label or "Noninstitutional" in label or "Non-institutional" in label:
                             print(f"FOUND GQ in {table_id}: {key} - {label}")
        except Exception:
            pass

scan_tables("B11", 0, 20)
scan_tables("B25", 0, 20)
scan_tables("B26", 0, 20)
