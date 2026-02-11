import json

from strongtowns_detroit.parcels.semantic_mapper import ZoningMapper


def main():
    """Example usage"""
    
    # Load your data
    with open('zoning_data.json', 'r') as f:
        zoning_data = json.load(f)
    
    with open('use_list.json', 'r') as f:
        use_list = json.load(f)
    
    # Initialize mapper
    mapper = ZoningMapper(model_name='all-MiniLM-L6-v2')
    
    # Extract specific uses
    specific_uses = mapper.extract_specific_uses(zoning_data)
    print(f"Found {len(specific_uses)} specific uses across {len(zoning_data)} use categories")
    
    # Compute similarities
    df = mapper.compute_similarities(use_list, specific_uses)
    
    # Get top matches with configurable thresholds
    matches = mapper.get_top_matches(
        df,
        high_threshold=0.75,    # Adjust these thresholds based on your needs
        medium_threshold=0.60,
        top_k=5                 # Top 5 matches per item
    )
    
    # Print summary
    mapper.print_summary(matches)
    
    # Export for review
    mapper.export_results(matches, 'zoning_matches.json', include_medium=True, include_low=False)
    
    # Generate final mapping (high confidence only)
    final_mapping = mapper.generate_mapping(matches, auto_accept_high=True)
    
    with open('final_mapping.json', 'w') as f:
        json.dump(final_mapping, f, indent=2)
    
    print("Final mapping saved to: final_mapping.json")
    
    # Print some examples
    print("\n" + "="*80)
    print("EXAMPLE HIGH CONFIDENCE MATCHES (first 5):")
    print("="*80)
    for i, (use_item, match_list) in enumerate(list(matches['high_confidence'].items())[:5]):
        print(f"\n{use_item}:")
        for match in match_list[:3]:  # Show top 3
            print(f"  → {match['specific_use']} ({match['use_category']})")
            print(f"    Similarity: {match['similarity']:.3f}")


if __name__ == "__main__":
    main()