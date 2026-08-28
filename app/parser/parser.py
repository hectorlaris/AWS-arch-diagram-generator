"""Structural phase of the Mermaid parser — builds the intermediate representation.

This module consumes tokens produced by the lexical phase (tokenizer) and
assembles them into a complete MermaidGraph IR, handling direction extraction,
node registration, edge construction, and subgraph nesting.
"""

from typing import Dict, List, Optional

from .exceptions import MermaidSyntaxError
from .models import MermaidCluster, MermaidEdge, MermaidGraph, MermaidNode
from .tokenizer import Token, TokenType, tokenize


def parse_mermaid(text: str) -> MermaidGraph:
    """Parse Mermaid graph syntax into a structured intermediate representation.

    Processes the input text through two phases:
    1. Lexical — regex tokenization via the tokenizer module
    2. Structural — sequential token processing to build the IR

    Args:
        text: Raw Mermaid graph syntax (without Markdown fencing).

    Returns:
        A MermaidGraph object containing all parsed nodes, edges, and clusters.

    Raises:
        MermaidSyntaxError: If the text contains invalid syntax such as
            a missing direction declaration, unclosed subgraph, or
            invalid edge references.
    """
    tokens = tokenize(text)

    direction = _extract_direction(tokens, text)
    nodes: Dict[str, MermaidNode] = {}
    edges: List[MermaidEdge] = []
    top_level_clusters: List[MermaidCluster] = []
    cluster_stack: List[MermaidCluster] = []

    for token in tokens:
        if token.type == TokenType.DIRECTION:
            # Already processed
            continue

        elif token.type == TokenType.SUBGRAPH_START:
            _handle_subgraph_start(token, cluster_stack)

        elif token.type == TokenType.SUBGRAPH_END:
            _handle_subgraph_end(
                token, cluster_stack, top_level_clusters
            )

        elif token.type in (
            TokenType.NODE_BRACKET,
            TokenType.NODE_PAREN,
            TokenType.NODE_BARE,
        ):
            _handle_node(token, nodes, cluster_stack)

        elif token.type in (
            TokenType.EDGE_SOLID,
            TokenType.EDGE_DOTTED,
            TokenType.EDGE_THICK,
        ):
            _handle_edge(token, tokens, nodes, edges, cluster_stack)

        elif token.type == TokenType.EDGE_LABEL:
            # Labels are consumed during edge handling; skip standalone
            continue

    # Validate no unclosed subgraphs remain
    if cluster_stack:
        cluster = cluster_stack[-1]
        raise MermaidSyntaxError(
            line=1,
            column=1,
            detail=f"Unclosed subgraph '{cluster.name}' — missing 'end' keyword",
        )

    return MermaidGraph(
        direction=direction,
        nodes=list(nodes.values()),
        edges=edges,
        clusters=top_level_clusters,
    )


def _extract_direction(tokens: List[Token], text: str) -> str:
    """Extract the graph direction from the token list.

    Args:
        tokens: List of tokens produced by the lexer.
        text: Original input text (used for error reporting context).

    Returns:
        The direction string (TD, LR, TB, or RL) in uppercase.

    Raises:
        MermaidSyntaxError: If no direction declaration token is found.
    """
    for token in tokens:
        if token.type == TokenType.DIRECTION:
            return token.groups["direction"]

    # No direction found — report error at first non-empty line
    first_line = 1
    first_col = 1
    for i, line in enumerate(text.split("\n"), start=1):
        if line.strip():
            first_line = i
            first_col = len(line) - len(line.lstrip()) + 1
            break

    raise MermaidSyntaxError(
        line=first_line,
        column=first_col,
        detail="Missing direction declaration (expected 'graph TD', 'graph LR', 'graph TB', 'graph RL', or 'flowchart' with direction)",
    )


def _handle_subgraph_start(
    token: Token, cluster_stack: List[MermaidCluster]
) -> None:
    """Push a new cluster onto the nesting stack.

    Args:
        token: The SUBGRAPH_START token with the cluster name.
        cluster_stack: The current stack of open clusters.
    """
    cluster = MermaidCluster(name=token.groups["name"])
    cluster_stack.append(cluster)


def _handle_subgraph_end(
    token: Token,
    cluster_stack: List[MermaidCluster],
    top_level_clusters: List[MermaidCluster],
) -> None:
    """Pop a cluster from the stack and attach it to its parent or top-level.

    Args:
        token: The SUBGRAPH_END token.
        cluster_stack: The current stack of open clusters.
        top_level_clusters: The list of completed top-level clusters.

    Raises:
        MermaidSyntaxError: If the stack is empty (unmatched 'end').
    """
    if not cluster_stack:
        raise MermaidSyntaxError(
            line=token.line,
            column=token.column,
            detail="Unexpected 'end' keyword without a matching 'subgraph'",
        )

    completed = cluster_stack.pop()

    if cluster_stack:
        # Nested subgraph — attach as child of parent cluster
        cluster_stack[-1].children.append(completed)
    else:
        # Top-level cluster
        top_level_clusters.append(completed)


def _handle_node(
    token: Token,
    nodes: Dict[str, MermaidNode],
    cluster_stack: List[MermaidCluster],
) -> None:
    """Register a node and associate it with the current cluster if any.

    If the node ID already exists, labeled declarations (bracket/paren)
    update the label; bare references do not override existing labels.
    Nodes are only added to the current cluster's node_ids if they
    are not already present in a deeper nested cluster.

    Args:
        token: A node token (NODE_BRACKET, NODE_PAREN, or NODE_BARE).
        nodes: The node registry mapping ID to MermaidNode.
        cluster_stack: The current stack of open clusters.
    """
    node_id = token.groups["id"]
    label = token.groups["label"]

    if node_id in nodes:
        # Update label only for explicit declarations (not bare refs)
        if token.type in (TokenType.NODE_BRACKET, TokenType.NODE_PAREN):
            nodes[node_id] = MermaidNode(id=node_id, label=label)
    else:
        nodes[node_id] = MermaidNode(id=node_id, label=label)

    # Assign to current cluster if we're inside a subgraph
    if cluster_stack:
        current_cluster = cluster_stack[-1]
        # Only add if not already in this cluster or a child cluster
        if not _node_in_cluster_tree(node_id, current_cluster):
            current_cluster.node_ids.append(node_id)


def _handle_edge(
    token: Token,
    all_tokens: List[Token],
    nodes: Dict[str, MermaidNode],
    edges: List[MermaidEdge],
    cluster_stack: List[MermaidCluster],
) -> None:
    """Build a MermaidEdge from an edge token, resolving source and target.

    Ensures that both source and target nodes are registered in the node
    dictionary (creating bare-reference entries if needed).

    Args:
        token: An edge token (EDGE_SOLID, EDGE_DOTTED, or EDGE_THICK).
        all_tokens: The complete token list (for looking up adjacent labels).
        nodes: The node registry mapping ID to MermaidNode.
        edges: The list of edges to append to.
        cluster_stack: The current stack of open clusters for node association.
    """
    source_id = token.groups["source"]
    target_id = token.groups["target"]

    # Ensure source and target are registered as nodes
    _ensure_node_exists(source_id, nodes, cluster_stack)
    _ensure_node_exists(target_id, nodes, cluster_stack)

    # Determine edge style from token type
    style = _token_type_to_edge_style(token.type)

    # Look for an adjacent edge label token
    label = _find_edge_label(token, all_tokens)

    edges.append(MermaidEdge(
        source_id=source_id,
        target_id=target_id,
        label=label,
        style=style,
    ))


def _ensure_node_exists(
    node_id: str,
    nodes: Dict[str, MermaidNode],
    cluster_stack: List[MermaidCluster],
) -> None:
    """Ensure a node is registered, creating a bare entry if needed.

    Args:
        node_id: The node identifier to check/register.
        nodes: The node registry mapping ID to MermaidNode.
        cluster_stack: The current stack of open clusters.
    """
    if node_id not in nodes:
        nodes[node_id] = MermaidNode(id=node_id, label=node_id)
        if cluster_stack:
            current_cluster = cluster_stack[-1]
            if not _node_in_cluster_tree(node_id, current_cluster):
                current_cluster.node_ids.append(node_id)


def _node_in_cluster_tree(node_id: str, cluster: MermaidCluster) -> bool:
    """Check if a node exists anywhere in a cluster's tree.

    Searches the cluster's own node_ids and recursively checks
    all child clusters.

    Args:
        node_id: The node identifier to search for.
        cluster: The cluster to search within.

    Returns:
        True if the node is found in the cluster or its children.
    """
    if node_id in cluster.node_ids:
        return True
    for child in cluster.children:
        if _node_in_cluster_tree(node_id, child):
            return True
    return False


def _token_type_to_edge_style(token_type: TokenType) -> str:
    """Map an edge token type to the edge style string.

    Args:
        token_type: The TokenType of the edge token.

    Returns:
        One of "solid", "dotted", or "thick".
    """
    if token_type == TokenType.EDGE_DOTTED:
        return "dotted"
    elif token_type == TokenType.EDGE_THICK:
        return "thick"
    return "solid"


def _find_edge_label(token: Token, all_tokens: List[Token]) -> Optional[str]:
    """Find the label associated with an edge token.

    Searches for an EDGE_LABEL token immediately following the edge
    token on the same line.

    Args:
        token: The edge token to find a label for.
        all_tokens: The complete token list.

    Returns:
        The label text if found, or None.
    """
    token_index = _find_token_index(token, all_tokens)
    if token_index is None:
        return None

    # Look for a label token right after this edge on the same line
    for i in range(token_index + 1, len(all_tokens)):
        candidate = all_tokens[i]
        if candidate.line != token.line:
            break
        if candidate.type == TokenType.EDGE_LABEL:
            return candidate.groups["label"]

    return None


def _find_token_index(token: Token, all_tokens: List[Token]) -> Optional[int]:
    """Find the index of a specific token in the token list.

    Uses identity comparison to find the exact token instance.

    Args:
        token: The token to locate.
        all_tokens: The complete token list.

    Returns:
        The index of the token, or None if not found.
    """
    for i, t in enumerate(all_tokens):
        if t is token:
            return i
    return None
