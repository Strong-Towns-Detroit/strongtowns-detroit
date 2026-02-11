"""Street network comparison utilities."""


def compare_networks(G_original, G_simplified, title="Network Comparison"):
    """Compare original vs simplified street networks and print statistics.

    Parameters
    ----------
    G_original : networkx.MultiDiGraph
        Original street network.
    G_simplified : networkx.MultiDiGraph
        Simplified street network.
    title : str
        Title for the comparison output.

    Returns
    -------
    dict
        Comparison statistics including node/edge counts and reduction percentages.
    """
    node_reduction = (1 - len(G_simplified.nodes) / len(G_original.nodes)) * 100
    edge_reduction = (1 - len(G_simplified.edges) / len(G_original.edges)) * 100

    print(f"\n{title}")
    print(f"{'='*60}")
    print(f"Original network: {len(G_original.nodes):,} nodes, {len(G_original.edges):,} edges")
    print(f"Simplified network: {len(G_simplified.nodes):,} nodes, {len(G_simplified.edges):,} edges")
    print(f"Reduction: {node_reduction:.1f}% nodes, {edge_reduction:.1f}% edges")

    return {
        'original_nodes': len(G_original.nodes),
        'original_edges': len(G_original.edges),
        'simplified_nodes': len(G_simplified.nodes),
        'simplified_edges': len(G_simplified.edges),
        'node_reduction_pct': node_reduction,
        'edge_reduction_pct': edge_reduction,
    }
