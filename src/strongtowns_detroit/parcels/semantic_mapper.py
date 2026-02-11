"""Semantic mapping of parcel use codes to zoning-specific uses via SBERT."""

import json
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Tuple
import pandas as pd


class ZoningMapper:
    """Maps use categories to zoning specific uses using SBERT semantic similarity."""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        print(f"Loading model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print("Model loaded successfully!")

    def extract_specific_uses(self, zoning_data: Dict) -> List[Tuple[str, str]]:
        """Extract all specific uses from zoning data with their use categories."""
        specific_uses = []
        for use_category, uses in zoning_data.items():
            for specific_use in uses.keys():
                specific_uses.append((use_category, specific_use))
        return specific_uses

    def compute_similarities(
        self,
        use_list: List[str],
        specific_uses: List[Tuple[str, str]],
        batch_size: int = 32,
    ) -> pd.DataFrame:
        """Compute similarity scores between use list items and specific uses."""
        print(f"Encoding {len(use_list)} use list items...")
        use_list_embeddings = self.model.encode(use_list, batch_size=batch_size, show_progress_bar=True)

        print(f"Encoding {len(specific_uses)} specific uses...")
        specific_use_texts = [su[1] for su in specific_uses]
        specific_use_embeddings = self.model.encode(specific_use_texts, batch_size=batch_size, show_progress_bar=True)

        print("Computing similarity matrix...")
        similarity_matrix = np.dot(use_list_embeddings, specific_use_embeddings.T)

        results = []
        for i, use_item in enumerate(use_list):
            similarities = similarity_matrix[i]
            for j, (use_cat, spec_use) in enumerate(specific_uses):
                results.append({
                    'use_item': use_item,
                    'use_category': use_cat,
                    'specific_use': spec_use,
                    'similarity': similarities[j],
                })

        return pd.DataFrame(results)

    def get_top_matches(
        self,
        df: pd.DataFrame,
        high_threshold: float = 0.75,
        medium_threshold: float = 0.60,
        top_k: int = 5,
    ) -> Dict:
        """Get top matches for each use item, categorized by confidence."""
        results = {
            'high_confidence': {},
            'medium_confidence': {},
            'low_confidence': {},
        }

        for use_item in df['use_item'].unique():
            item_matches = df[df['use_item'] == use_item].nlargest(top_k, 'similarity')

            high = []
            medium = []
            low = []

            for _, row in item_matches.iterrows():
                match_info = {
                    'specific_use': row['specific_use'],
                    'use_category': row['use_category'],
                    'similarity': float(row['similarity']),
                }

                if row['similarity'] >= high_threshold:
                    high.append(match_info)
                elif row['similarity'] >= medium_threshold:
                    medium.append(match_info)
                else:
                    low.append(match_info)

            if high:
                results['high_confidence'][use_item] = high
            if medium:
                results['medium_confidence'][use_item] = medium
            if low:
                results['low_confidence'][use_item] = low

        return results

    def generate_mapping(self, matches: Dict, auto_accept_high: bool = True) -> Dict:
        """Generate the final mapping from high confidence matches."""
        mapping = {}

        for use_item, match_list in matches['high_confidence'].items():
            categories = {}
            for match in match_list:
                cat = match['use_category']
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(match['specific_use'])

            mapping[use_item] = {
                'use_category': list(categories.keys()),
                'specific_use': match_list[0]['specific_use'] if len(match_list) == 1 else [m['specific_use'] for m in match_list],
                'confidence': 'high',
                'top_similarity': match_list[0]['similarity'],
            }

        return mapping

    def print_summary(self, matches: Dict):
        """Print a summary of the matching results."""
        print("\n" + "=" * 80)
        print("MATCHING SUMMARY")
        print("=" * 80)
        print(f"High confidence matches: {len(matches['high_confidence'])}")
        print(f"Medium confidence matches: {len(matches['medium_confidence'])}")
        print(f"Low confidence matches: {len(matches['low_confidence'])}")
        total = len(matches['high_confidence']) + len(matches['medium_confidence']) + len(matches['low_confidence'])
        print(f"Total items processed: {total}")
        print("=" * 80 + "\n")

    def export_results(
        self,
        matches: Dict,
        output_file: str,
        include_medium: bool = True,
        include_low: bool = False,
    ):
        """Export results to JSON file for review."""
        export_data = {'high_confidence': matches['high_confidence']}

        if include_medium:
            export_data['medium_confidence'] = matches['medium_confidence']

        if include_low:
            export_data['low_confidence'] = matches['low_confidence']

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"Results exported to: {output_file}")
