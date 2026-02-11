"""Visualize the zoning ordinance citation graph.

Provides four complementary views of the citation structure:

1. **Article-level flow** — 18 articles collapsed into a ring diagram
   showing inter-article citation flows.
2. **Top-cited sections** — Force-directed network of the N most-cited
   sections, sized by in-degree.
3. **Single-article deep dive** — All sections within one article with
   cross-references colored by direction.
4. **Degree distribution** — Histograms of in-degree and out-degree
   revealing whether citation structure follows a power law.

All functions accept a :class:`CitationGraph` and optionally a
matplotlib ``Axes`` for embedding in custom layouts.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.figure import Figure

from strongtowns_detroit.mapping.colors import BUILDABLE
from strongtowns_detroit.zoning.models import CitationGraph

# ──────────────────────────────────────────────
# Roman numeral mapping (mirrors citations.py)
# ──────────────────────────────────────────────

_INT_TO_ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
    6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X",
    11: "XI", 12: "XII", 13: "XIII", 14: "XIV", 15: "XV",
    16: "XVI", 17: "XVII", 18: "XVIII", 19: "XIX", 20: "XX",
}

_INTERNAL_RE = re.compile(r"^\d{2}-\d{1,2}-\d{1,4}$")


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _to_nx(graph: CitationGraph) -> nx.DiGraph:
    """Convert a CitationGraph to a networkx DiGraph.

    Nodes carry a ``label`` attribute; edges carry ``citation_type``.
    Multi-edges between the same pair are collapsed into a single edge
    with a ``weight`` attribute counting occurrences.
    """
    G = nx.DiGraph()
    for node_id, label in graph.nodes.items():
        G.add_node(node_id, label=label)
    edge_counts: Counter[tuple[str, str]] = Counter()
    for cit in graph.edges:
        edge_counts[(cit.source_section, cit.target)] += 1
    for (src, tgt), weight in edge_counts.items():
        G.add_edge(src, tgt, weight=weight)
    return G


def _article_of(section_id: str) -> int | None:
    """Extract the article number from an internal section ID like '50-12-101'."""
    parts = section_id.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return None


def _is_internal(node_id: str) -> bool:
    return bool(_INTERNAL_RE.match(node_id))


def _article_colormap(n: int = 20) -> dict[int, str]:
    """Return a mapping of article number → hex color using tab20."""
    cmap = plt.colormaps.get_cmap("tab20").resampled(n)
    return {
        i: "#{:02x}{:02x}{:02x}".format(
            int(cmap(i % n)[0] * 255),
            int(cmap(i % n)[1] * 255),
            int(cmap(i % n)[2] * 255),
        )
        for i in range(1, n + 1)
    }


# ──────────────────────────────────────────────
# Figure 1: Article-Level Flow Diagram
# ──────────────────────────────────────────────

def plot_article_flow(graph: CitationGraph, ax: plt.Axes | None = None) -> Figure:
    """Collapse sections into articles and draw inter-article citation flow.

    Each article becomes a node sized by its section count.  Directed
    edges between articles are weighted by citation count.  External
    references are grouped into a single "External" node.

    Returns the matplotlib ``Figure``.
    """
    # Build article-level aggregation
    article_sections: Counter[str] = Counter()  # "Art. XII" → count
    for node_id in graph.nodes:
        art = _article_of(node_id) if _is_internal(node_id) else None
        if art is not None:
            label = f"Art. {_INT_TO_ROMAN.get(art, str(art))}"
            article_sections[label] += 1

    # Count inter-article edges
    edge_weights: Counter[tuple[str, str]] = Counter()
    for cit in graph.edges:
        src_art = _article_of(cit.source_section) if _is_internal(cit.source_section) else None
        tgt_art = _article_of(cit.target) if _is_internal(cit.target) else None
        src_label = f"Art. {_INT_TO_ROMAN.get(src_art, str(src_art))}" if src_art else None
        tgt_label = f"Art. {_INT_TO_ROMAN.get(tgt_art, str(tgt_art))}" if tgt_art else "External"

        if src_label is None:
            continue
        if src_label == tgt_label:
            continue  # skip intra-article edges
        edge_weights[(src_label, tgt_label)] += 1

    # Build the article-level graph
    AG = nx.DiGraph()
    for label, count in article_sections.items():
        AG.add_node(label, section_count=count)

    # Add External node if there are external edges
    ext_total = sum(w for (_, t), w in edge_weights.items() if t == "External")
    if ext_total > 0:
        AG.add_node("External", section_count=0)

    for (src, tgt), weight in edge_weights.items():
        if src in AG.nodes and tgt in AG.nodes:
            AG.add_edge(src, tgt, weight=weight)

    # Layout + draw
    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(14, 14))
    else:
        fig = ax.figure

    if len(AG.nodes) == 0:
        ax.text(0.5, 0.5, "No article-level data", ha="center", va="center",
                transform=ax.transAxes, fontsize=14)
        ax.axis("off")
        return fig

    pos = nx.circular_layout(AG)

    # Node sizes proportional to section count
    sizes = [max(AG.nodes[n].get("section_count", 1) * 15, 200) for n in AG.nodes]

    # Node colors
    art_colors = _article_colormap()
    node_colors = []
    for n in AG.nodes:
        if n == "External":
            node_colors.append("#999999")
        else:
            # Extract article number from "Art. XII"
            roman = n.replace("Art. ", "")
            art_num = next((k for k, v in _INT_TO_ROMAN.items() if v == roman), None)
            node_colors.append(art_colors.get(art_num, "#cccccc") if art_num else "#cccccc")

    nx.draw_networkx_nodes(AG, pos, ax=ax, node_size=sizes, node_color=node_colors,
                           edgecolors="white", linewidths=1.5)
    nx.draw_networkx_labels(AG, pos, ax=ax, font_size=9, font_weight="bold")

    # Edges with width proportional to weight
    if AG.edges:
        weights = [AG[u][v]["weight"] for u, v in AG.edges]
        max_w = max(weights) if weights else 1
        widths = [0.5 + (w / max_w) * 4 for w in weights]
        nx.draw_networkx_edges(AG, pos, ax=ax, width=widths, alpha=0.35,
                               edge_color="#555555", arrows=True,
                               arrowsize=15, connectionstyle="arc3,rad=0.1")

    ax.set_title("Inter-Article Citation Flow — Detroit Zoning Ordinance",
                 fontsize=18, fontweight="bold", pad=20)
    ax.axis("off")
    return fig


# ──────────────────────────────────────────────
# Figure 2: Top-Cited Sections Network
# ──────────────────────────────────────────────

def plot_top_cited(
    graph: CitationGraph, top_n: int = 30, ax: plt.Axes | None = None,
) -> Figure:
    """Draw a force-directed network of the *top_n* most-cited sections.

    Node size is proportional to in-degree; color indicates article
    membership.

    Returns the matplotlib ``Figure``.
    """
    G = _to_nx(graph)

    # Rank internal nodes by in-degree
    internal = [n for n in G.nodes if _is_internal(n)]
    in_deg = {n: G.in_degree(n) for n in internal}
    top_nodes = sorted(in_deg, key=in_deg.get, reverse=True)[:top_n]

    if not top_nodes:
        own_fig = ax is None
        if own_fig:
            fig, ax = plt.subplots(figsize=(16, 12))
        else:
            fig = ax.figure
        ax.text(0.5, 0.5, "No internal nodes", ha="center", va="center",
                transform=ax.transAxes, fontsize=14)
        ax.axis("off")
        return fig

    subG = G.subgraph(top_nodes).copy()

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(16, 12))
    else:
        fig = ax.figure

    pos = nx.spring_layout(subG, k=2.0, seed=42, iterations=50)

    # Sizes based on in-degree in the full graph
    sizes = [max(in_deg.get(n, 0) * 40, 100) for n in subG.nodes]

    art_colors = _article_colormap()
    node_colors = []
    for n in subG.nodes:
        art = _article_of(n)
        node_colors.append(art_colors.get(art, "#cccccc") if art else "#cccccc")

    nx.draw_networkx_nodes(subG, pos, ax=ax, node_size=sizes,
                           node_color=node_colors, edgecolors="white", linewidths=1.0)
    nx.draw_networkx_labels(subG, pos, ax=ax, font_size=7)
    nx.draw_networkx_edges(subG, pos, ax=ax, alpha=0.2, arrows=True,
                           edge_color="#555555", arrowsize=10)

    ax.set_title("Most-Cited Sections — Detroit Zoning Ordinance",
                 fontsize=18, fontweight="bold", pad=20)
    ax.axis("off")
    return fig


# ──────────────────────────────────────────────
# Figure 3: Single-Article Deep Dive
# ──────────────────────────────────────────────

def plot_article_detail(
    graph: CitationGraph,
    article_num: int = 12,
    max_focal: int = 40,
    max_external: int = 10,
    ax: plt.Axes | None = None,
) -> Figure:
    """Show the most-connected sections within one article.

    Keeps only the *max_focal* highest-degree focal sections and the
    *max_external* most-connected external references, producing a
    readable "skeleton" of the article's citation structure.

    Edge colors: dark blue = intra-article, orange = outgoing to
    other articles, green = incoming from other articles.

    Returns the matplotlib ``Figure``.
    """
    art_prefix = f"50-{article_num}"
    all_focal = {n for n in graph.nodes if _is_internal(n) and n.startswith(art_prefix + "-")}

    # Collect all edges involving focal nodes and count degree
    focal_degree: Counter[str] = Counter()
    external_degree: Counter[str] = Counter()
    all_intra: list[tuple[str, str]] = []
    all_outgoing: list[tuple[str, str]] = []
    all_incoming: list[tuple[str, str]] = []

    for cit in graph.edges:
        src_focal = cit.source_section in all_focal
        tgt_focal = cit.target in all_focal
        if src_focal and tgt_focal:
            all_intra.append((cit.source_section, cit.target))
            focal_degree[cit.source_section] += 1
            focal_degree[cit.target] += 1
        elif src_focal and not tgt_focal:
            all_outgoing.append((cit.source_section, cit.target))
            focal_degree[cit.source_section] += 1
            external_degree[cit.target] += 1
        elif not src_focal and tgt_focal:
            all_incoming.append((cit.source_section, cit.target))
            focal_degree[cit.target] += 1
            external_degree[cit.source_section] += 1

    # Keep the top focal and external nodes
    top_focal = {n for n, _ in focal_degree.most_common(max_focal)}
    top_external = {n for n, _ in external_degree.most_common(max_external)}

    # Filter edges to only involve kept nodes
    intra = [(s, t) for s, t in all_intra if s in top_focal and t in top_focal]
    outgoing = [(s, t) for s, t in all_outgoing if s in top_focal and t in top_external]
    incoming = [(s, t) for s, t in all_incoming if s in top_external and t in top_focal]

    # Build subgraph
    shown_focal = set()
    for s, t in intra:
        shown_focal.update((s, t))
    for s, _ in outgoing:
        shown_focal.add(s)
    for _, t in incoming:
        shown_focal.add(t)
    shown_external = {t for _, t in outgoing} | {s for s, _ in incoming}

    all_nodes = shown_focal | shown_external
    SG = nx.DiGraph()
    for n in all_nodes:
        SG.add_node(n)
    for src, tgt in intra + outgoing + incoming:
        if src in all_nodes and tgt in all_nodes:
            SG.add_edge(src, tgt)

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(16, 12))
    else:
        fig = ax.figure

    roman = _INT_TO_ROMAN.get(article_num, str(article_num))

    if len(SG.nodes) == 0:
        ax.text(0.5, 0.5, f"No cross-references in Article {roman}",
                ha="center", va="center", transform=ax.transAxes, fontsize=14)
        ax.axis("off")
        return fig

    pos = nx.spring_layout(SG, k=3.0, seed=42, iterations=100)

    # Node sizing: scale by degree in the full graph
    focal_list = [n for n in SG.nodes if n in shown_focal]
    ext_list = [n for n in SG.nodes if n in shown_external]
    focal_sizes = [max(focal_degree.get(n, 0) * 50, 200) for n in focal_list]
    ext_sizes = [max(external_degree.get(n, 0) * 40, 150) for n in ext_list]

    if focal_list:
        nx.draw_networkx_nodes(SG, pos, nodelist=focal_list, ax=ax,
                               node_size=focal_sizes, node_color="#2171b5",
                               edgecolors="white", linewidths=1.0)
    if ext_list:
        nx.draw_networkx_nodes(SG, pos, nodelist=ext_list, ax=ax,
                               node_size=ext_sizes, node_color="#bbbbbb",
                               edgecolors="white", linewidths=1.0)

    # Labels — short section suffixes for focal, full ID for external
    focal_labels = {n: n.replace(art_prefix + "-", "") for n in focal_list}
    ext_labels = {n: n for n in ext_list}
    nx.draw_networkx_labels(SG, pos, labels=focal_labels, ax=ax, font_size=8)
    nx.draw_networkx_labels(SG, pos, labels=ext_labels, ax=ax, font_size=7,
                            font_color="#555555")

    # Draw edge groups
    def _draw_edges(edge_list: list[tuple[str, str]], color: str) -> None:
        valid = [(u, v) for u, v in edge_list if u in SG.nodes and v in SG.nodes]
        if valid:
            nx.draw_networkx_edges(SG, pos, edgelist=valid, ax=ax, alpha=0.35,
                                   edge_color=color, arrows=True, arrowsize=12,
                                   connectionstyle="arc3,rad=0.1")

    _draw_edges(intra, "#08519c")      # dark blue
    _draw_edges(outgoing, "#e6550d")   # orange
    _draw_edges(incoming, "#31a354")   # green

    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color="#08519c", lw=2, label="Intra-article"),
        Line2D([0], [0], color="#e6550d", lw=2, label="Outgoing"),
        Line2D([0], [0], color="#31a354", lw=2, label="Incoming"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2171b5",
               markersize=10, label=f"Art. {roman} sections ({len(shown_focal)})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#bbbbbb",
               markersize=10, label=f"External refs ({len(shown_external)})"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=10,
              framealpha=0.9)

    ax.set_title(
        f"Article {roman} Citation Network"
        f"  (top {len(shown_focal)} of {len(all_focal)} sections by connectivity)",
        fontsize=16, fontweight="bold", pad=20,
    )
    ax.axis("off")
    return fig


# ──────────────────────────────────────────────
# Figure 4: Degree Distribution
# ──────────────────────────────────────────────

def plot_degree_distribution(
    graph: CitationGraph, ax: plt.Axes | None = None,
) -> Figure:
    """Plot in-degree and out-degree histograms for internal sections.

    Uses log-scale y-axis to highlight the power-law tail.

    When *ax* is provided it must be a pair of axes (left, right).
    If *ax* is ``None`` a new 1×2 figure is created.

    Returns the matplotlib ``Figure``.
    """
    G = _to_nx(graph)
    internal = [n for n in G.nodes if _is_internal(n)]

    in_degs = [G.in_degree(n) for n in internal]
    out_degs = [G.out_degree(n) for n in internal]

    own_fig = ax is None
    if own_fig:
        fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(14, 6))
    else:
        ax_left, ax_right = ax
        fig = ax_left.figure

    color = BUILDABLE

    # In-degree histogram
    if in_degs:
        max_in = max(in_degs)
        bins_in = range(0, max_in + 2)
        ax_left.hist(in_degs, bins=bins_in, color=color, edgecolor="white", linewidth=0.5)
        mean_in = sum(in_degs) / len(in_degs)
        median_in = sorted(in_degs)[len(in_degs) // 2]
        ax_left.axvline(mean_in, color="#e6550d", linestyle="--", linewidth=1.5,
                        label=f"Mean: {mean_in:.1f}")
        ax_left.axvline(median_in, color="#31a354", linestyle="--", linewidth=1.5,
                        label=f"Median: {median_in}")
        ax_left.legend(fontsize=9)
    ax_left.set_xlabel("In-degree (times cited)", fontsize=12)
    ax_left.set_ylabel("Number of sections", fontsize=12)
    ax_left.set_title("In-Degree Distribution", fontsize=14, fontweight="bold")
    ax_left.set_yscale("log")

    # Out-degree histogram
    if out_degs:
        max_out = max(out_degs)
        bins_out = range(0, max_out + 2)
        ax_right.hist(out_degs, bins=bins_out, color=color, edgecolor="white", linewidth=0.5)
        mean_out = sum(out_degs) / len(out_degs)
        median_out = sorted(out_degs)[len(out_degs) // 2]
        ax_right.axvline(mean_out, color="#e6550d", linestyle="--", linewidth=1.5,
                         label=f"Mean: {mean_out:.1f}")
        ax_right.axvline(median_out, color="#31a354", linestyle="--", linewidth=1.5,
                         label=f"Median: {median_out}")
        ax_right.legend(fontsize=9)
    ax_right.set_xlabel("Out-degree (citations made)", fontsize=12)
    ax_right.set_ylabel("Number of sections", fontsize=12)
    ax_right.set_title("Out-Degree Distribution", fontsize=14, fontweight="bold")
    ax_right.set_yscale("log")

    fig.suptitle("Citation Degree Distribution", fontsize=18, fontweight="bold", y=1.02)
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────

def visualize_citation_graph(
    graph: CitationGraph,
    output_dir: Path,
    article_number: int = 12,
    top_n: int = 30,
) -> None:
    """Generate all 4 visualization figures and save to *output_dir*.

    Creates the output directory if it doesn't exist.  Saves each figure
    as a 300-DPI PNG with tight bounding boxes.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    figures = {
        "article_flow.png": plot_article_flow(graph),
        "top_cited.png": plot_top_cited(graph, top_n=top_n),
        "article_detail.png": plot_article_detail(graph, article_num=article_number),
        "degree_distribution.png": plot_degree_distribution(graph),
    }

    for filename, fig in figures.items():
        fig.savefig(output_dir / filename, dpi=300, bbox_inches="tight",
                    facecolor="white")
        plt.close(fig)
