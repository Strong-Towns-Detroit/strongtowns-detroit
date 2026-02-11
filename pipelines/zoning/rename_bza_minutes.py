import os

from strongtowns_detroit.bza.renamer import parse_date

def main():
    directory = "/Users/johnbolt/workplace/web-scraping/scripts/city-of-detroit/bza_dataset/bza_minutes"
    files = sorted(os.listdir(directory))
    
    print(f"Found {len(files)} files.")
    
    renames = []
    failed = []
    target_map = {}
    
    for f in files:
        if not f.lower().endswith('.pdf'):
            continue
            
        date_obj = parse_date(f)
        if date_obj:
            new_name = f"{date_obj.strftime('%Y-%m-%d')}_bza_minutes.pdf"
            if new_name != f:
                renames.append((f, new_name))
                if new_name in target_map:
                    target_map[new_name].append(f)
                else:
                    target_map[new_name] = [f]
        else:
            failed.append(f)

    final_renames = []
    
    # Process non-colliding files
    for new_name, sources in target_map.items():
        if len(sources) == 1:
            final_renames.append((sources[0], new_name))
        else:
            # Handle collisions
            print(f"Resolving collision for {new_name}: {sources}")
            # Sort sources to be deterministic
            sources.sort()
            for i, source in enumerate(sources):
                if i == 0:
                    final_renames.append((source, new_name))
                else:
                    base, ext = os.path.splitext(new_name)
                    suffixed_name = f"{base}_{i}{ext}"
                    final_renames.append((source, suffixed_name))

    if failed:
        print(f"\nFailed to parse ({len(failed)}):")
        for f in failed:
            print(f)

    print(f"\nApplying {len(final_renames)} renames...")
    for old, new in final_renames:
        print(f"Renaming {old} -> {new}")
        os.rename(os.path.join(directory, old), os.path.join(directory, new))
    print("Done.")

if __name__ == "__main__":
    main()
