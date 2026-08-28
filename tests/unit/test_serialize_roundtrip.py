"""Unit tests for MermaidGraph.serialize() and the round-trip property.

Tests that parse(serialize(parse(input))) == parse(input) for various
valid Mermaid graph inputs — ensuring no information is lost through
the serialize/re-parse cycle.

Validates: Requirements 8.1, 8.2, 8.3
"""

from typing import List

import pytest

from app.parser.models import (
    MermaidCluster,
    MermaidEdge,
    MermaidGraph,
    MermaidNode,
)
from app.parser.parser import parse_mermaid


def _graphs_equivalent(g1: MermaidGraph, g2: MermaidGraph) -> bool:
    """Check structural equivalence of two MermaidGraph objects.

    Compares direction, nodes (by id+label), edges (by all fields),
    and clusters (recursively by name, node_ids, and children).

    Args:
        g1: First graph to compare.
        g2: Second graph to compare.

    Returns:
        True if both graphs are structurally equivalent.
    """
    if g1.direction != g2.direction:
        return False

    # Compare nodes as sets of (id, label)
    nodes1 = {(n.id, n.label) for n in g1.nodes}
    nodes2 = {(n.id, n.label) for n in g2.nodes}
    if nodes1 != nodes2:
        return False

    # Compare edges as sets of (source, target, label, style)
    edges1 = {(e.source_id, e.target_id, e.label, e.style) for e in g1.edges}
    edges2 = {(e.source_id, e.target_id, e.label, e.style) for e in g2.edges}
    if edges1 != edges2:
        return False

    # Compare clusters recursively
    return _clusters_equivalent(g1.clusters, g2.clusters)


def _clusters_equivalent(
    c1_list: List[MermaidCluster], c2_list: List[MermaidCluster]
) -> bool:
    """Recursively compare two lists of clusters for structural equivalence.

    Args:
        c1_list: First cluster list.
        c2_list: Second cluster list.

    Returns:
        True if both cluster lists are structurally equivalent.
    """
    if len(c1_list) != len(c2_list):
        return False

    sorted1 = sorted(c1_list, key=lambda c: c.name)
    sorted2 = sorted(c2_list, key=lambda c: c.name)

    for c1, c2 in zip(sorted1, sorted2):
        if c1.name != c2.name:
            return False
        if sorted(c1.node_ids) != sorted(c2.node_ids):
            return False
        if not _clusters_equivalent(c1.children, c2.children):
            return False

    return True


def _assert_roundtrip(mermaid_text: str) -> None:
    """Assert the round-trip property holds for the given input.

    Parses the input, serializes, re-parses, and verifies equivalence.

    Args:
        mermaid_text: Valid Mermaid graph syntax.
    """
    graph1 = parse_mermaid(mermaid_text)
    serialized = graph1.serialize()
    graph2 = parse_mermaid(serialized)

    assert _graphs_equivalent(graph1, graph2), (
        f"Round-trip failed.\n"
        f"Original nodes: {[(n.id, n.label) for n in graph1.nodes]}\n"
        f"Re-parsed nodes: {[(n.id, n.label) for n in graph2.nodes]}\n"
        f"Original edges: {[(e.source_id, e.target_id, e.label, e.style) for e in graph1.edges]}\n"
        f"Re-parsed edges: {[(e.source_id, e.target_id, e.label, e.style) for e in graph2.edges]}\n"
        f"Serialized text:\n{serialized}"
    )


class TestSerializeOutput:
    """Tests that serialize() produces valid Mermaid syntax."""

    def test_serialize_includes_direction(self) -> None:
        """Serialize output starts with the direction declaration."""
        graph = MermaidGraph(
            direction="TD",
            nodes=[MermaidNode(id="A", label="NodeA")],
        )
        result = graph.serialize()
        assert result.startswith("graph TD")

    def test_serialize_includes_all_directions(self) -> None:
        """Serialize correctly outputs each supported direction."""
        for direction in ("TD", "LR", "TB", "RL"):
            graph = MermaidGraph(
                direction=direction,
                nodes=[MermaidNode(id="X", label="X")],
            )
            result = graph.serialize()
            assert result.startswith(f"graph {direction}")

    def test_serialize_emits_node_with_bracket_label(self) -> None:
        """Nodes are emitted as id[label] format."""
        graph = MermaidGraph(
            direction="TD",
            nodes=[MermaidNode(id="Svc", label="My Service")],
        )
        result = graph.serialize()
        assert "Svc[My Service]" in result

    def test_serialize_emits_solid_edge(self) -> None:
        """Solid edges use --> arrow syntax."""
        graph = MermaidGraph(
            direction="TD",
            nodes=[
                MermaidNode(id="A", label="A"),
                MermaidNode(id="B", label="B"),
            ],
            edges=[MermaidEdge(source_id="A", target_id="B", style="solid")],
        )
        result = graph.serialize()
        assert "A --> B" in result

    def test_serialize_emits_dotted_edge(self) -> None:
        """Dotted edges use -.-> arrow syntax."""
        graph = MermaidGraph(
            direction="TD",
            nodes=[
                MermaidNode(id="A", label="A"),
                MermaidNode(id="B", label="B"),
            ],
            edges=[MermaidEdge(source_id="A", target_id="B", style="dotted")],
        )
        result = graph.serialize()
        assert "A -.-> B" in result

    def test_serialize_emits_thick_edge(self) -> None:
        """Thick edges use ==> arrow syntax."""
        graph = MermaidGraph(
            direction="TD",
            nodes=[
                MermaidNode(id="A", label="A"),
                MermaidNode(id="B", label="B"),
            ],
            edges=[MermaidEdge(source_id="A", target_id="B", style="thick")],
        )
        result = graph.serialize()
        assert "A ==> B" in result

    def test_serialize_emits_edge_label(self) -> None:
        """Labeled edges include |label| syntax."""
        graph = MermaidGraph(
            direction="TD",
            nodes=[
                MermaidNode(id="A", label="A"),
                MermaidNode(id="B", label="B"),
            ],
            edges=[
                MermaidEdge(
                    source_id="A", target_id="B", label="data flow", style="solid"
                )
            ],
        )
        result = graph.serialize()
        assert "A -->|data flow| B" in result

    def test_serialize_emits_subgraph(self) -> None:
        """Clusters are wrapped in subgraph/end blocks."""
        graph = MermaidGraph(
            direction="TD",
            nodes=[MermaidNode(id="N1", label="Node 1")],
            clusters=[MermaidCluster(name="MyCluster", node_ids=["N1"])],
        )
        result = graph.serialize()
        assert "subgraph MyCluster" in result
        assert "N1[Node 1]" in result
        assert "end" in result

    def test_serialize_emits_nested_subgraphs(self) -> None:
        """Nested clusters produce nested subgraph/end blocks."""
        graph = MermaidGraph(
            direction="TD",
            nodes=[
                MermaidNode(id="Inner", label="Inner Node"),
                MermaidNode(id="Outer", label="Outer Node"),
            ],
            clusters=[
                MermaidCluster(
                    name="OuterCluster",
                    node_ids=["Outer"],
                    children=[
                        MermaidCluster(name="InnerCluster", node_ids=["Inner"])
                    ],
                )
            ],
        )
        result = graph.serialize()
        assert "subgraph OuterCluster" in result
        assert "subgraph InnerCluster" in result
        # Nested structure
        lines = result.split("\n")
        outer_idx = next(i for i, l in enumerate(lines) if "OuterCluster" in l)
        inner_idx = next(i for i, l in enumerate(lines) if "InnerCluster" in l)
        assert inner_idx > outer_idx


class TestRoundTripSimple:
    """Tests the round-trip property with simple graphs."""

    def test_roundtrip_single_node(self) -> None:
        """Round-trip preserves a single node."""
        _assert_roundtrip("graph TD\n    A[Hello World]")

    def test_roundtrip_two_nodes_one_edge(self) -> None:
        """Round-trip preserves a basic graph with one edge."""
        _assert_roundtrip("graph TD\n    A[Source] --> B[Target]")

    def test_roundtrip_bare_nodes(self) -> None:
        """Round-trip preserves bare nodes referenced in edges."""
        _assert_roundtrip("graph LR\n    Alpha --> Beta")

    def test_roundtrip_direction_lr(self) -> None:
        """Round-trip preserves LR direction."""
        _assert_roundtrip("graph LR\n    A[Node A] --> B[Node B]")

    def test_roundtrip_direction_tb(self) -> None:
        """Round-trip preserves TB direction."""
        _assert_roundtrip("graph TB\n    X[Top] --> Y[Bottom]")

    def test_roundtrip_direction_rl(self) -> None:
        """Round-trip preserves RL direction."""
        _assert_roundtrip("graph RL\n    End[End] --> Start[Start]")


class TestRoundTripEdges:
    """Tests the round-trip property with various edge types."""

    def test_roundtrip_labeled_edge(self) -> None:
        """Round-trip preserves edge labels."""
        _assert_roundtrip(
            "graph TD\n    A[API] -->|REST| B[Lambda]"
        )

    def test_roundtrip_dotted_edge(self) -> None:
        """Round-trip preserves dotted edge style."""
        _assert_roundtrip(
            "graph TD\n    A[Service] -.-> B[Database]"
        )

    def test_roundtrip_thick_edge(self) -> None:
        """Round-trip preserves thick edge style."""
        _assert_roundtrip(
            "graph TD\n    A[Queue] ==> B[Worker]"
        )

    def test_roundtrip_mixed_edges(self) -> None:
        """Round-trip preserves a mix of edge styles and labels."""
        _assert_roundtrip(
            "graph TD\n"
            "    A[Client] --> B[API]\n"
            "    B -->|invoke| C[Lambda]\n"
            "    C -.-> D[DynamoDB]\n"
            "    D ==> E[Stream]"
        )

    def test_roundtrip_multiple_edges_same_source(self) -> None:
        """Round-trip preserves fan-out from one node."""
        _assert_roundtrip(
            "graph TD\n"
            "    Hub[Hub] --> A[Service A]\n"
            "    Hub --> B[Service B]\n"
            "    Hub --> C[Service C]"
        )


class TestRoundTripClusters:
    """Tests the round-trip property with subgraphs."""

    def test_roundtrip_single_cluster(self) -> None:
        """Round-trip preserves a single cluster with nodes."""
        _assert_roundtrip(
            "graph TD\n"
            "    subgraph VPC\n"
            "        Lambda[Lambda]\n"
            "        RDS[RDS]\n"
            "    end\n"
            "    Client[Client] --> Lambda"
        )

    def test_roundtrip_multiple_clusters(self) -> None:
        """Round-trip preserves multiple sibling clusters."""
        _assert_roundtrip(
            "graph TD\n"
            "    subgraph Frontend\n"
            "        Web[Web App]\n"
            "    end\n"
            "    subgraph Backend\n"
            "        API[API Server]\n"
            "    end\n"
            "    Web --> API"
        )

    def test_roundtrip_nested_clusters(self) -> None:
        """Round-trip preserves nested cluster hierarchy."""
        _assert_roundtrip(
            "graph TD\n"
            "    subgraph Cloud\n"
            "        subgraph VPC\n"
            "            Lambda[Lambda]\n"
            "        end\n"
            "        S3[S3 Bucket]\n"
            "    end\n"
            "    Client[Client] --> Lambda"
        )

    def test_roundtrip_edges_across_clusters(self) -> None:
        """Round-trip preserves edges between nodes in different clusters."""
        _assert_roundtrip(
            "graph TD\n"
            "    subgraph Region1\n"
            "        SvcA[Service A]\n"
            "    end\n"
            "    subgraph Region2\n"
            "        SvcB[Service B]\n"
            "    end\n"
            "    SvcA --> SvcB"
        )


class TestRoundTripComplex:
    """Tests the round-trip property with realistic AWS architectures."""

    def test_roundtrip_typical_aws_architecture(self) -> None:
        """Round-trip preserves a typical AWS serverless architecture."""
        _assert_roundtrip(
            "graph TD\n"
            "    Client[Web Client] -->|HTTPS| APIGW[API Gateway]\n"
            "    APIGW --> Lambda[Lambda]\n"
            "    Lambda --> DDB[DynamoDB]\n"
            "    Lambda -.-> SQS[SQS]\n"
            "    SQS ==> Worker[ECS Worker]"
        )

    def test_roundtrip_full_example_with_clusters(self) -> None:
        """Round-trip preserves a full architecture with clusters and mixed edges."""
        _assert_roundtrip(
            "graph TD\n"
            "    subgraph Public\n"
            "        Client[Client]\n"
            "        CDN[CloudFront]\n"
            "    end\n"
            "    subgraph Private\n"
            "        subgraph Compute\n"
            "            Lambda[Lambda]\n"
            "            ECS[ECS]\n"
            "        end\n"
            "        DDB[DynamoDB]\n"
            "    end\n"
            "    Client --> CDN\n"
            "    CDN -->|forward| Lambda\n"
            "    Lambda -.-> DDB\n"
            "    Lambda ==>|async| ECS"
        )

    def test_roundtrip_idempotent(self) -> None:
        """Applying round-trip twice produces the same result."""
        input_text = (
            "graph LR\n"
            "    A[Auth] -->|token| B[API]\n"
            "    B --> C[Database]"
        )
        g1 = parse_mermaid(input_text)
        s1 = g1.serialize()
        g2 = parse_mermaid(s1)
        s2 = g2.serialize()
        g3 = parse_mermaid(s2)

        assert _graphs_equivalent(g1, g2)
        assert _graphs_equivalent(g2, g3)
        # Serialized forms should stabilize after first round-trip
        assert s1 == s2
