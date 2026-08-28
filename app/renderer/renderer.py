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
    with Cluster(cluster.name):
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
            graph_attr={"dpi": "150", "size": "10.24,7.68!"},
        ):
            # Create nodes that are NOT in any cluster first
            for mapping in mappings:
                if mapping.node_id not in node_cluster_map:
                    node_objects[mapping.node_id] = mapping.diagrams_class(
                        _format_display_label(mapping.node_label)
                    )

            # Create clusters with their contained nodes
            for cluster in graph.clusters:
                _create_nodes_in_cluster(
                    cluster, mappings_by_id, node_objects
                )

            # Connect edges
            for edge in graph.edges:
                source = node_objects.get(edge.source_id)
                target = node_objects.get(edge.target_id)
                if source is None or target is None:
                    continue

                if edge.label:
                    source >> Edge(label=edge.label) >> target
                else:
                    source >> target

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
