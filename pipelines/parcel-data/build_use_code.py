import csv
import json

from strongtowns_detroit.parcels.zoning_json import parse_zoning_csv

def main():
    input_file = "merged_tables.csv"
    output_file = "detroit_zoning.json"
    
    print(f"Parsing {input_file}...")
    zoning_data, use_categories, specific_uses = parse_zoning_csv(input_file)
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(zoning_data, f, indent=2, ensure_ascii=False)
        
    with open("use_codes_from_municode.json", 'w', encoding='utf-8') as f:
        json.dump(specific_uses, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Parsed data written to {output_file}")
    
    # Print some statistics
    total_categories = len(zoning_data)
    total_uses = sum(len(uses) for uses in zoning_data.values())
    print(f"\nStatistics:")
    print(f"  - Use categories: {total_categories}")
    print(f"  - Specific land uses: {total_uses}")
    
    # Show a sample
    print(f"\nSample categories:")
    for i, category in enumerate(list(zoning_data.keys())[:5]):
        print(f"  - {category}: {len(zoning_data[category])} uses")


if __name__ == "__main__":
    main()