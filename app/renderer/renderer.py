"""Diagram rendering pipeline using the diagrams library and Graphviz.

This module implements the core rendering logic that constructs a
diagrams.Diagram from the parsed Mermaid IR and mapped service classes,
producing PNG and SVG output files.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict

from diagrams import Diagram, Cluster, Edge

from app.api.models import WarningEntry
from app.mapper.mapper import MappingResult
from app.parser.models import MermaidGraph, MermaidCluster
from app.renderer.exceptions import RenderError
from app.renderer.svg_embed import embed_svg_images


@dataclass
class RenderResult:
    """Result of rendering a diagram.

    Attributes:
        png_path: Path to the generated PNG file.
        svg_path: Path to the generated SVG file.
        warnings: List of warnings from the mapping phase.
    """

    png_path: Path
    svg_path: Path
    warnings: List[WarningEntry] = field(default_factory=list)


# Matches HTML line-break tags: <br>, <br/>, <br />, case-insensitive.
_LINE_BREAK_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)


# AWS/Amazon official brand typeface is "Amazon Ember". Graphviz picks the
# first available font from a comma-separated list, so we fall back to common
# sans-serif faces (and finally the generic "sans-serif") when Amazon Ember is
# not installed on the host system.
_FONT_FAMILY = "Amazon Ember, Helvetica, Arial, sans-serif"

# Font sizes (points) chosen to establish a visual hierarchy consistent with
# AWS architecture diagrams: cluster/group titles larger than node labels,
# edge labels slightly smaller.
_CLUSTER_FONT_SIZE = "16"
_NODE_FONT_SIZE = "14"
_EDGE_FONT_SIZE = "13"

# Edge (step/action) labels use a bold italic style to match the look of
# official AWS reference architecture diagrams, where numbered steps such as
# "Assume Role" or "Deploy Serverless Stack" are emphasized in bold italics.
_EDGE_FONT_FAMILY = "Amazon Ember Bold Italic, Helvetica-BoldOblique, Arial, sans-serif"

# Output resolution. Higher DPI produces crisper text and icons in the PNG.
_OUTPUT_DPI = "300"


# Edge visual styles per Mermaid arrow type, mirroring official AWS reference
# architecture diagrams: the main flow (thick "==>") is drawn as a bold
# colored arrow, normal flow ("-->") as a solid dark arrow, and dependencies
# ("-.->") as a thin dashed grey arrow.
#
# Each entry maps an IR edge style to Graphviz edge attributes.
_EDGE_STYLES = {
    "thick": {
        "color": "#D45B07",       # AWS-style orange/red for the primary flow
        "penwidth": "3.0",
        "style": "solid",
        "fontcolor": "#D45B07",
    },
    "solid": {
        "color": "#232F3E",       # AWS "squid ink" dark for normal flow
        "penwidth": "1.8",
        "style": "solid",
        "fontcolor": "#232F3E",
    },
    "dotted": {
        "color": "#879196",       # muted grey for secondary dependencies
        "penwidth": "1.3",
        "style": "dashed",
        "fontcolor": "#5A6570",
    },
}


def _build_edge(edge) -> Edge:
    """Build a styled diagrams.Edge for a parsed Mermaid edge.

    Applies color, thickness, and line style based on the edge's Mermaid
    arrow type, and attaches the bold-italic label styling when the edge
    has a label.

    Args:
        edge: A MermaidEdge from the parsed IR.

    Returns:
        A configured diagrams.Edge instance.
    """
    style = _EDGE_STYLES.get(edge.style, _EDGE_STYLES["solid"])

    attrs = {
        "color": style["color"],
        "penwidth": style["penwidth"],
        "style": style["style"],
    }

    if edge.label:
        attrs["label"] = edge.label
        attrs["fontname"] = _EDGE_FONT_FAMILY
        attrs["fontsize"] = _EDGE_FONT_SIZE
        attrs["fontcolor"] = style["fontcolor"]

    return Edge(**attrs)


def _format_display_label(label: str) -> str:
    """Convert HTML line-break tags in a label to real newlines.

    Mermaid labels commonly use <br/> (or <br>) to indicate a line break,
    e.g. "GitHub<br/>Repository". Graphviz renders a literal "\n" in a node
    label as a line break, so we translate the tags accordingly for display.

    Args:
        label: The raw node label, possibly containing <br/> tags.

    Returns:
        The label with line-break tags replaced by newline characters and
        surrounding whitespace on each line trimmed.
    """
    parts = _LINE_BREAK_PATTERN.split(label)
    return "\n".join(part.strip() for part in parts)


def _get_node_cluster_map(graph: MermaidGraph) -> Dict[str, str]:
    """Build a mapping of node_id to cluster name for all clustered nodes.

    Traverses the cluster hierarchy recursively to identify which
    cluster each node belongs to.

    Args:
        graph: The parsed MermaidGraph intermediate representation.

    Returns:
        Dictionary mapping node IDs to their containing cluster name.
    """
    node_to_cluster: Dict[str, str] = {}
    _collect_node_clusters(graph.clusters, node_to_cluster)
    return node_to_cluster


def _collect_node_clusters(
    clusters: List[MermaidCluster], node_to_cluster: Dict[str, str]
) -> None:
    """Recursively collect node-to-cluster assignments.

    Args:
        clusters: List of clusters to traverse.
        node_to_cluster: Dictionary to populate with node_id -> cluster_name.
    """
    for cluster in clusters:
        for node_id in cluster.node_ids:
            node_to_cluster[node_id] = cluster.name
        _collect_node_clusters(cluster.children, node_to_cluster)


def _build_cluster_target_map(
    clusters: List[MermaidCluster],
    result: Dict[str, str],
) -> None:
    """Map each subgraph id to a representative inner node id.

    Graphviz cannot terminate an edge on a cluster directly, so an edge that
    targets a subgraph is redirected to a node inside it. This builds a
    mapping from a cluster's id to the first node found within that cluster
    (searching nested children if the cluster has no direct nodes).

    Args:
        clusters: The cluster hierarchy to traverse.
        result: Dictionary populated with cluster_id -> representative node id.
    """
    for cluster in clusters:
        if cluster.cluster_id:
            rep = _first_node_in_cluster(cluster)
            if rep is not None:
                result[cluster.cluster_id] = rep
        _build_cluster_target_map(cluster.children, result)


def _first_node_in_cluster(cluster: MermaidCluster):
    """Return the first node id inside a cluster, searching children.

    Args:
        cluster: The cluster to inspect.

    Returns:
        A node id, or None if the cluster (and its children) contain none.
    """
    if cluster.node_ids:
        return cluster.node_ids[0]
    for child in cluster.children:
        found = _first_node_in_cluster(child)
        if found is not None:
            return found
    return None


def _create_nodes_in_cluster(
    cluster: MermaidCluster,
    mappings_by_id: Dict[str, MappingResult],
    node_objects: Dict[str, object],
) -> None:
    """Create diagram nodes within a Cluster context, handling nesting.

    Recursively processes child clusters so nodes are instantiated
    inside the correct Cluster context manager for proper rendering.

    Args:
        cluster: The MermaidCluster to render.
        mappings_by_id: Mapping of node_id to MappingResult for class lookup.
        node_objects: Dictionary to populate with node_id -> diagrams node instance.
    """
    with Cluster(
        cluster.name,
        graph_attr={
            "fontname": _FONT_FAMILY,
            "fontsize": _CLUSTER_FONT_SIZE,
        },
    ):
        # Instantiate nodes that belong directly to this cluster
        for node_id in cluster.node_ids:
            if node_id in mappings_by_id:
                mapping = mappings_by_id[node_id]
                node_objects[node_id] = mapping.diagrams_class(
                    _format_display_label(mapping.node_label)
                )

        # Recursively process child clusters
        for child in cluster.children:
            _create_nodes_in_cluster(child, mappings_by_id, node_objects)


def render_diagram(
    graph: MermaidGraph,
    output_dir: Path,
    output_name: str,
    mappings: List[MappingResult],
) -> RenderResult:
    """Render the parsed graph into PNG and SVG files.

    Constructs a diagrams.Diagram from the intermediate representation
    and mapped service classes. Nodes are created within their respective
    Cluster context managers for correct grouping. Edges are connected
    using the >> operator with optional labels.

    Args:
        graph: The parsed MermaidGraph intermediate representation.
        output_dir: Directory where output files will be saved.
        output_name: Base name for output files (without extension).
        mappings: List of node-to-class mappings from the service mapper.

    Returns:
        RenderResult with paths to generated files and any warnings.

    Raises:
        RenderError: If Graphviz fails to produce output.
    """
    # Build lookup from node_id -> MappingResult
    mappings_by_id: Dict[str, MappingResult] = {
        m.node_id: m for m in mappings
    }

    # Determine which nodes belong to clusters
    node_cluster_map = _get_node_cluster_map(graph)

    # Map subgraph ids to a representative inner node, so edges that target a
    # whole subgraph can be redirected there instead of creating a phantom node.
    cluster_target_map: Dict[str, str] = {}
    _build_cluster_target_map(graph.clusters, cluster_target_map)

    # Collect warnings from mappings
    warnings: List[WarningEntry] = [
        m.warning for m in mappings if m.warning is not None
    ]

    # Node instances will be stored here
    node_objects: Dict[str, object] = {}

    try:
        with Diagram(
            name=output_name,
            filename=str(output_dir / output_name),
            show=False,
            direction=graph.direction,
            outformat=["png", "svg"],
            graph_attr={
                "dpi": _OUTPUT_DPI,
                # Applies to the diagram title and is inherited by clusters.
                "fontname": _FONT_FAMILY,
                "fontsize": _CLUSTER_FONT_SIZE,
                # Layout tuning for a compact, tidy look closer to official
                # AWS reference diagrams.
                "nodesep": "0.6",      # spacing between sibling nodes
                "ranksep": "0.8",      # spacing between ranks (levels)
                "splines": "ortho",    # right-angle connectors like AWS
                "pad": "0.5",          # padding around the whole drawing
                "compound": "true",    # allow edges to/from clusters
            },
            node_attr={
                "fontname": _FONT_FAMILY,
                "fontsize": _NODE_FONT_SIZE,
            },
            edge_attr={
                "fontname": _FONT_FAMILY,
                "fontsize": _EDGE_FONT_SIZE,
            },
        ):
            # Create nodes that are NOT in any cluster first. Skip ids that
            # are actually subgraph ids (edges to them are redirected below),
            # so we do not render a phantom node for a subgraph reference.
            for mapping in mappings:
                if mapping.node_id in cluster_target_map:
                    continue
                if mapping.node_id not in node_cluster_map:
                    node_objects[mapping.node_id] = mapping.diagrams_class(
                        _format_display_label(mapping.node_label)
                    )

            # Create clusters with their contained nodes
            for cluster in graph.clusters:
                _create_nodes_in_cluster(
                    cluster, mappings_by_id, node_objects
                )

            # Connect edges. If an endpoint references a subgraph id, redirect
            # it to a representative node inside that subgraph.
            for edge in graph.edges:
                source_id = cluster_target_map.get(edge.source_id, edge.source_id)
                target_id = cluster_target_map.get(edge.target_id, edge.target_id)
                source = node_objects.get(source_id)
                target = node_objects.get(target_id)
                if source is None or target is None:
                    continue

                source >> _build_edge(edge) >> target

    except Exception as exc:
        raise RenderError(str(exc)) from exc

    png_path = output_dir / f"{output_name}.png"
    svg_path = output_dir / f"{output_name}.svg"

    # Verify output files were created
    if not png_path.exists() or not svg_path.exists():
        raise RenderError(
            "Graphviz did not produce expected output files"
        )

    # Make the SVG self-contained by embedding icon images as data URIs.
    # Graphviz references icons by absolute path, which breaks portability
    # and prevents browsers from displaying them.
    try:
        embed_svg_images(svg_path)
    except OSError:
        # Embedding is best-effort; a non-embedded SVG is still returned.
        pass

    return RenderResult(
        png_path=png_path,
        svg_path=svg_path,
        warnings=warnings,
    )
