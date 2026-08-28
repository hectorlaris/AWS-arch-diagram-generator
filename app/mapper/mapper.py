"""Orchestrator for mapping all Mermaid nodes to diagrams.aws classes.

This module provides the high-level `map_all_nodes` function that iterates
over a list of MermaidNode objects and resolves each to a diagrams.aws class
using the two-tier resolution strategy in `app.mapper.resolver`.
"""

from dataclasses import dataclass
from typing import List, Optional, Type

from app.api.models import WarningEntry
from app.mapper.resolver import resolve_service
from app.parser.models import MermaidNode


@dataclass
class MappingResult:
    """Result of mapping a single Mermaid node label to a diagrams class.

    Attributes:
        node_id: The Mermaid node identifier from the IR.
        node_label: The display label used for service resolution.
        diagrams_class: The resolved diagrams.aws class for rendering.
        warning: Optional warning if the mapping was ambiguous or unresolved.
    """

    node_id: str
    node_label: str
    diagrams_class: Type
    warning: Optional[WarningEntry] = None


def map_all_nodes(nodes: List[MermaidNode]) -> List[MappingResult]:
    """Map all nodes in a parsed Mermaid graph to diagrams.aws classes.

    Iterates over each node, calls the two-tier service resolver, and
    collects the results into MappingResult objects. Warnings are attached
    to individual results for nodes that matched ambiguously or fell back
    to the General class.

    Args:
        nodes: List of MermaidNode objects from the parser IR.

    Returns:
        List of MappingResult objects with resolved classes and any warnings.
    """
    results: List[MappingResult] = []

    for node in nodes:
        diagrams_class, warning = resolve_service(node.label)
        result = MappingResult(
            node_id=node.id,
            node_label=node.label,
            diagrams_class=diagrams_class,
            warning=warning,
        )
        results.append(result)

    return results
