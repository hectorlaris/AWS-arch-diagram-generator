"""Intermediate representation (IR) dataclasses for parsed Mermaid graphs.

This module defines the core data structures that bridge the Mermaid parser
and the diagram renderer. The IR supports serialization back to Mermaid syntax
for round-trip testing.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MermaidNode:
    """Represents a node in the Mermaid graph.

    Attributes:
        id: The Mermaid identifier (used in edge definitions).
        label: The display label (used for service mapping).
    """

    id: str
    label: str

    def __eq__(self, other: object) -> bool:
        """Equality based on id and label.

        Args:
            other: The object to compare against.

        Returns:
            True if both id and label match, NotImplemented for non-MermaidNode.
        """
        if not isinstance(other, MermaidNode):
            return NotImplemented
        return self.id == other.id and self.label == other.label

    def __hash__(self) -> int:
        """Hash based on id.

        Returns:
            Hash value derived from the node's id.
        """
        return hash(self.id)


@dataclass
class MermaidEdge:
    """Represents a directed edge between two nodes.

    Attributes:
        source_id: ID of the source node.
        target_id: ID of the target node.
        label: Optional text label displayed on the edge.
        style: Arrow style - "solid", "dotted", or "thick".
    """

    source_id: str
    target_id: str
    label: Optional[str] = None
    style: str = "solid"


@dataclass
class MermaidCluster:
    """Represents a subgraph grouping.

    Attributes:
        name: Display name of the cluster.
        node_ids: IDs of nodes directly contained in this cluster.
        children: Nested sub-clusters within this cluster.
        cluster_id: Optional Mermaid identifier of the subgraph (the token
            before the bracketed title, e.g. "OBJETIVO" in
            `subgraph OBJETIVO["..."]`). Used to resolve edges that target a
            subgraph rather than a plain node.
    """

    name: str
    node_ids: List[str] = field(default_factory=list)
    children: List["MermaidCluster"] = field(default_factory=list)
    cluster_id: Optional[str] = None


@dataclass
class MermaidGraph:
    """Complete intermediate representation of a parsed Mermaid graph.

    This is the core data model that bridges parsing and rendering.
    It supports serialization back to Mermaid syntax for round-trip
    testing.

    Attributes:
        direction: Graph layout direction (TD, LR, TB, RL).
        nodes: All nodes declared in the graph.
        edges: All directed edges between nodes.
        clusters: Top-level cluster hierarchy (may be nested).
    """

    direction: str
    nodes: List[MermaidNode] = field(default_factory=list)
    edges: List[MermaidEdge] = field(default_factory=list)
    clusters: List[MermaidCluster] = field(default_factory=list)

    def serialize(self) -> str:
        """Serialize the IR back to valid Mermaid syntax.

        Outputs valid Mermaid graph syntax representing this IR,
        including direction declaration, node definitions, edges,
        and subgraph blocks.

        Returns:
            A string of valid Mermaid graph syntax representing this IR.
        """
        lines: List[str] = []
        lines.append(f"graph {self.direction}")

        # Collect node IDs that belong to clusters
        clustered_node_ids = self._get_all_clustered_node_ids()

        # Emit node declarations for nodes not in clusters
        for node in self.nodes:
            if node.id not in clustered_node_ids:
                lines.append(f"    {node.id}[{node.label}]")

        # Emit clusters with their contained nodes
        for cluster in self.clusters:
            self._serialize_cluster(cluster, lines, indent=4)

        # Emit edges
        for edge in self.edges:
            lines.append(f"    {self._serialize_edge(edge)}")

        return "\n".join(lines)

    def get_node_by_id(self, node_id: str) -> Optional[MermaidNode]:
        """Look up a node by its ID.

        Args:
            node_id: The identifier of the node to find.

        Returns:
            The MermaidNode with the given ID, or None if not found.
        """
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_cluster_for_node(self, node_id: str) -> Optional[MermaidCluster]:
        """Find which cluster (if any) contains the given node.

        Searches the cluster hierarchy recursively to find the
        innermost cluster containing the specified node.

        Args:
            node_id: The identifier of the node to locate.

        Returns:
            The MermaidCluster containing the node, or None if the
            node is not in any cluster.
        """
        return self._find_cluster_for_node(node_id, self.clusters)

    def _find_cluster_for_node(
        self, node_id: str, clusters: List[MermaidCluster]
    ) -> Optional[MermaidCluster]:
        """Recursively search clusters for a node.

        Args:
            node_id: The identifier of the node to locate.
            clusters: List of clusters to search through.

        Returns:
            The innermost MermaidCluster containing the node, or None.
        """
        for cluster in clusters:
            # Check children first (innermost match)
            child_result = self._find_cluster_for_node(
                node_id, cluster.children
            )
            if child_result is not None:
                return child_result
            if node_id in cluster.node_ids:
                return cluster
        return None

    def _get_all_clustered_node_ids(self) -> set:
        """Collect all node IDs that belong to any cluster.

        Returns:
            A set of node IDs that are contained in clusters.
        """
        ids: set = set()
        self._collect_clustered_ids(self.clusters, ids)
        return ids

    def _collect_clustered_ids(
        self, clusters: List[MermaidCluster], ids: set
    ) -> None:
        """Recursively collect node IDs from clusters.

        Args:
            clusters: List of clusters to traverse.
            ids: Set to accumulate node IDs into.
        """
        for cluster in clusters:
            ids.update(cluster.node_ids)
            self._collect_clustered_ids(cluster.children, ids)

    def _serialize_cluster(
        self, cluster: MermaidCluster, lines: List[str], indent: int
    ) -> None:
        """Serialize a cluster and its children to Mermaid syntax.

        Args:
            cluster: The cluster to serialize.
            lines: List of output lines to append to.
            indent: Current indentation level in spaces.
        """
        prefix = " " * indent
        lines.append(f"{prefix}subgraph {cluster.name}")

        # Emit nodes within this cluster
        for node_id in cluster.node_ids:
            node = self.get_node_by_id(node_id)
            if node is not None:
                lines.append(f"{prefix}    {node.id}[{node.label}]")

        # Emit nested clusters
        for child in cluster.children:
            self._serialize_cluster(child, lines, indent + 4)

        lines.append(f"{prefix}end")

    def _serialize_edge(self, edge: MermaidEdge) -> str:
        """Serialize a single edge to Mermaid syntax.

        Args:
            edge: The edge to serialize.

        Returns:
            A string representing the edge in Mermaid syntax.
        """
        if edge.style == "dotted":
            arrow = "-.->"
        elif edge.style == "thick":
            arrow = "==>"
        else:
            arrow = "-->"

        if edge.label:
            return f"{edge.source_id} {arrow}|{edge.label}| {edge.target_id}"
        return f"{edge.source_id} {arrow} {edge.target_id}"
