"""Lexical tokenizer for Mermaid graph syntax.

This module provides regex-based tokenization of Mermaid diagram syntax,
producing a list of typed tokens with line/column position information
for downstream parsing and error reporting.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenType(Enum):
    """Types of tokens recognized in Mermaid graph syntax."""

    DIRECTION = auto()       # graph TD, graph LR, etc.
    NODE_BRACKET = auto()    # id[label]
    NODE_PAREN = auto()      # id(label)
    EDGE_SOLID = auto()      # -->
    EDGE_DOTTED = auto()     # -.->
    EDGE_THICK = auto()      # ==>
    EDGE_LABEL = auto()      # |label text|
    SUBGRAPH_START = auto()  # subgraph Name
    SUBGRAPH_END = auto()    # end
    NODE_BARE = auto()       # bare identifier (no brackets/parens)


@dataclass
class Token:
    """A single token from Mermaid graph syntax with position info.

    Attributes:
        type: The classification of this token.
        value: The raw matched text.
        line: 1-based line number where the token starts.
        column: 1-based column position where the token starts.
        groups: Captured groups from the regex match (e.g., id, label).
    """

    type: TokenType
    value: str
    line: int
    column: int
    groups: dict


# Regex patterns for Mermaid syntax elements.
# Order matters: more specific patterns must appear before less specific ones.

# Direction declaration: graph TD, graph LR, etc.
_DIRECTION_PATTERN = re.compile(
    r"(?:graph|flowchart)\s+(TD|LR|TB|RL)\b", re.IGNORECASE
)

# Subgraph start: subgraph Name
_SUBGRAPH_START_PATTERN = re.compile(
    r"subgraph\s+(.+)", re.IGNORECASE
)

# Subgraph end: end (as a standalone keyword)
_SUBGRAPH_END_PATTERN = re.compile(
    r"\bend\b", re.IGNORECASE
)

# Edge with label: A -->|label| B or A -.->|label| B or A ==>|label| B
# Also handles A[label] -->|text| B[label] by matching the node id before brackets
_EDGE_LABELED_PATTERN = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)(?:\[[^\]]*\]|\([^)]*\))?\s*(-->|-.->|==>)\|([^|]*)\|\s*([A-Za-z_][A-Za-z0-9_]*)(?:\[[^\]]*\]|\([^)]*\))?"
)

# Edge without label: A --> B, A -.-> B, A ==> B
# Also handles A[label] --> B[label] by matching the node id before brackets
_EDGE_PLAIN_PATTERN = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)(?:\[[^\]]*\]|\([^)]*\))?\s*(-->|-.->|==>)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\[[^\]]*\]|\([^)]*\))?"
)

# Node with bracket label: id[label text]
_NODE_BRACKET_PATTERN = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\[([^\]]+)\]"
)

# Node with paren label: id(label text)
_NODE_PAREN_PATTERN = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\(([^)]+)\)"
)

# Bare node identifier (standalone word, not a keyword)
_NODE_BARE_PATTERN = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\b"
)

# Keywords that should not be treated as bare nodes
_KEYWORDS = {"graph", "flowchart", "subgraph", "end", "td", "lr", "tb", "rl"}


def _strip_quotes(label: str) -> str:
    """Strip surrounding quotes and shape delimiters from a label.

    Handles Mermaid shape syntax like:
      - "text" -> text
      - ("text") -> text (cylinder)
      - (["text"]) -> text (subroutine)

    Args:
        label: The raw label text.

    Returns:
        Label with surrounding quotes and shape markers removed.
    """
    # Strip outer parens used in shape syntax: ("text") or (text)
    if label.startswith('("') and label.endswith('")'):
        label = label[2:-2]
    elif label.startswith("('") and label.endswith("')"):
        label = label[2:-2]
    elif label.startswith("(") and label.endswith(")"):
        label = label[1:-1]
    # Strip surrounding double quotes
    if label.startswith('"') and label.endswith('"'):
        label = label[1:-1]
    return label


def _extract_subgraph_name(raw_name: str) -> str:
    """Extract the display name from a subgraph declaration.

    Handles formats like:
      - subgraph VPC
      - subgraph aws_pipeline["AWS CI/CD Account"]

    Args:
        raw_name: Everything after 'subgraph ' on the line.

    Returns:
        The clean display name for the cluster.
    """
    import re as _re
    # Match: identifier["label"] or identifier[label]
    m = _re.match(r'[A-Za-z_][A-Za-z0-9_]*\["?([^"\]]+)"?\]', raw_name)
    if m:
        return m.group(1)
    # Match: "label" (just a quoted name)
    m = _re.match(r'"([^"]+)"', raw_name)
    if m:
        return m.group(1)
    return raw_name



def _arrow_to_token_type(arrow: str) -> TokenType:
    """Map an arrow string to its corresponding TokenType.

    Args:
        arrow: The arrow syntax string (-->, -.->, ==>).

    Returns:
        The matching TokenType for the arrow style.
    """
    if arrow == "-.->":
        return TokenType.EDGE_DOTTED
    elif arrow == "==>":
        return TokenType.EDGE_THICK
    return TokenType.EDGE_SOLID


def tokenize(text: str) -> List[Token]:
    """Tokenize Mermaid graph syntax into a list of typed tokens.

    Processes the input text line by line, applying regex patterns in
    priority order to extract structured tokens with position information.

    Args:
        text: Raw Mermaid graph syntax (without Markdown fencing).

    Returns:
        A list of Token objects in the order they appear in the input,
        each carrying its type, matched value, line/column position,
        and captured groups.
    """
    tokens: List[Token] = []
    lines = text.split("\n")

    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("%%"):
            continue

        # Skip Mermaid styling directives (classDef, class, style, linkStyle)
        if stripped.startswith(("classDef ", "class ", "style ", "linkStyle ")):
            continue

        # Try direction declaration first
        match = _DIRECTION_PATTERN.match(stripped)
        if match:
            col = line.index(stripped) + 1
            tokens.append(Token(
                type=TokenType.DIRECTION,
                value=match.group(0),
                line=line_num,
                column=col,
                groups={"direction": match.group(1).upper()},
            ))
            continue

        # Try subgraph start
        match = _SUBGRAPH_START_PATTERN.match(stripped)
        if match:
            col = line.index(stripped) + 1
            raw_name = match.group(1).strip()
            name = _extract_subgraph_name(raw_name)
            tokens.append(Token(
                type=TokenType.SUBGRAPH_START,
                value=match.group(0),
                line=line_num,
                column=col,
                groups={"name": name},
            ))
            continue

        # Try subgraph end (standalone 'end' keyword)
        if _SUBGRAPH_END_PATTERN.fullmatch(stripped):
            col = line.index(stripped) + 1
            tokens.append(Token(
                type=TokenType.SUBGRAPH_END,
                value=stripped,
                line=line_num,
                column=col,
                groups={},
            ))
            continue

        # Try labeled edge: A -->|label| B
        match = _EDGE_LABELED_PATTERN.search(stripped)
        if match:
            _tokenize_labeled_edge_with_nodes(
                match, stripped, line, line_num, tokens
            )
            continue

        # Try plain edge: A --> B
        match = _EDGE_PLAIN_PATTERN.search(stripped)
        if match:
            _tokenize_plain_edge_with_nodes(
                match, stripped, line, line_num, tokens
            )
            continue

        # Try node definitions (bracket or paren)
        if _try_tokenize_nodes(stripped, line, line_num, tokens):
            continue

        # Try bare node identifiers as fallback
        _tokenize_bare_nodes(stripped, line, line_num, tokens)

    return tokens


def _tokenize_labeled_edge(
    match: re.Match, line: str, line_num: int, tokens: List[Token]
) -> None:
    """Extract tokens from a labeled edge match.

    Produces node tokens for source/target and edge + label tokens.

    Args:
        match: The regex match object for the labeled edge.
        line: The full original line text.
        line_num: The 1-based line number.
        tokens: The token list to append to.
    """
    source_id = match.group(1)
    arrow = match.group(2)
    label = match.group(3)
    target_id = match.group(4)

    offset = line.index(line.strip())

    # Source node token
    source_col = offset + match.start(1) + 1
    _emit_node_reference(source_id, line_num, source_col, tokens)

    # Edge token
    edge_col = offset + match.start(2) + 1
    tokens.append(Token(
        type=_arrow_to_token_type(arrow),
        value=arrow,
        line=line_num,
        column=edge_col,
        groups={"source": source_id, "target": target_id},
    ))

    # Label token
    label_col = offset + match.start(3) + 1
    tokens.append(Token(
        type=TokenType.EDGE_LABEL,
        value=label,
        line=line_num,
        column=label_col,
        groups={"label": label},
    ))

    # Target node token
    target_col = offset + match.start(4) + 1
    _emit_node_reference(target_id, line_num, target_col, tokens)


def _tokenize_labeled_edge_with_nodes(
    match: re.Match, stripped: str, line: str, line_num: int, tokens: List[Token]
) -> None:
    """Extract tokens from a labeled edge, including bracketed node definitions.

    Like _tokenize_labeled_edge but also emits NODE_BRACKET/NODE_PAREN tokens
    when source or target nodes have inline label declarations.

    Args:
        match: The regex match object for the labeled edge.
        stripped: The stripped line text.
        line: The full original line text.
        line_num: The 1-based line number.
        tokens: The token list to append to.
    """
    source_id = match.group(1)
    arrow = match.group(2)
    label = match.group(3)
    target_id = match.group(4)

    offset = line.index(stripped)

    # Emit source node (check for bracket/paren label)
    _emit_node_with_label_if_present(
        source_id, stripped, line, line_num, offset, tokens
    )

    # Edge token
    edge_col = offset + match.start(2) + 1
    tokens.append(Token(
        type=_arrow_to_token_type(arrow),
        value=arrow,
        line=line_num,
        column=edge_col,
        groups={"source": source_id, "target": target_id},
    ))

    # Label token
    label_col = offset + match.start(3) + 1
    tokens.append(Token(
        type=TokenType.EDGE_LABEL,
        value=label,
        line=line_num,
        column=label_col,
        groups={"label": label},
    ))

    # Emit target node (check for bracket/paren label)
    _emit_node_with_label_if_present(
        target_id, stripped, line, line_num, offset, tokens
    )


def _tokenize_plain_edge(
    match: re.Match, line: str, line_num: int, tokens: List[Token]
) -> None:
    """Extract tokens from a plain (unlabeled) edge match.

    Produces node tokens for source/target and an edge token.

    Args:
        match: The regex match object for the plain edge.
        line: The full original line text.
        line_num: The 1-based line number.
        tokens: The token list to append to.
    """
    source_id = match.group(1)
    arrow = match.group(2)
    target_id = match.group(3)

    offset = line.index(line.strip())

    # Source node token
    source_col = offset + match.start(1) + 1
    _emit_node_reference(source_id, line_num, source_col, tokens)

    # Edge token
    edge_col = offset + match.start(2) + 1
    tokens.append(Token(
        type=_arrow_to_token_type(arrow),
        value=arrow,
        line=line_num,
        column=edge_col,
        groups={"source": source_id, "target": target_id},
    ))

    # Target node token
    target_col = offset + match.start(3) + 1
    _emit_node_reference(target_id, line_num, target_col, tokens)


def _tokenize_plain_edge_with_nodes(
    match: re.Match, stripped: str, line: str, line_num: int, tokens: List[Token]
) -> None:
    """Extract tokens from a plain edge, including bracketed node definitions.

    Like _tokenize_plain_edge but also emits NODE_BRACKET/NODE_PAREN tokens
    when source or target nodes have inline label declarations.

    Args:
        match: The regex match object for the plain edge.
        stripped: The stripped line text.
        line: The full original line text.
        line_num: The 1-based line number.
        tokens: The token list to append to.
    """
    source_id = match.group(1)
    arrow = match.group(2)
    target_id = match.group(3)

    offset = line.index(stripped)

    # Emit source node (check for bracket/paren label)
    _emit_node_with_label_if_present(
        source_id, stripped, line, line_num, offset, tokens
    )

    # Edge token
    edge_col = offset + match.start(2) + 1
    tokens.append(Token(
        type=_arrow_to_token_type(arrow),
        value=arrow,
        line=line_num,
        column=edge_col,
        groups={"source": source_id, "target": target_id},
    ))

    # Emit target node (check for bracket/paren label)
    _emit_node_with_label_if_present(
        target_id, stripped, line, line_num, offset, tokens
    )


def _emit_node_reference(
    node_id: str, line_num: int, column: int, tokens: List[Token]
) -> None:
    """Emit a bare node reference token for an edge endpoint.

    Args:
        node_id: The node identifier string.
        line_num: The 1-based line number.
        column: The 1-based column position.
        tokens: The token list to append to.
    """
    tokens.append(Token(
        type=TokenType.NODE_BARE,
        value=node_id,
        line=line_num,
        column=column,
        groups={"id": node_id, "label": node_id},
    ))


def _emit_node_with_label_if_present(
    node_id: str,
    stripped: str,
    line: str,
    line_num: int,
    offset: int,
    tokens: List[Token],
) -> None:
    """Emit a node token, checking for bracket or paren labels in the line.

    If the node has an inline label declaration (e.g., id[label] or id(label)),
    emits a NODE_BRACKET or NODE_PAREN token. Otherwise emits NODE_BARE.

    Args:
        node_id: The node identifier string.
        stripped: The stripped line content to search in.
        line: The full original line text.
        line_num: The 1-based line number.
        offset: The offset from line start to stripped content.
        tokens: The token list to append to.
    """
    # Look for id[label]
    bracket_match = re.search(
        re.escape(node_id) + r"\[([^\]]+)\]", stripped
    )
    if bracket_match:
        col = offset + bracket_match.start() + 1
        tokens.append(Token(
            type=TokenType.NODE_BRACKET,
            value=bracket_match.group(0),
            line=line_num,
            column=col,
            groups={"id": node_id, "label": _strip_quotes(bracket_match.group(1))},
        ))
        return

    # Look for id(label)
    paren_match = re.search(
        re.escape(node_id) + r"\(([^)]+)\)", stripped
    )
    if paren_match:
        col = offset + paren_match.start() + 1
        tokens.append(Token(
            type=TokenType.NODE_PAREN,
            value=paren_match.group(0),
            line=line_num,
            column=col,
            groups={"id": node_id, "label": _strip_quotes(paren_match.group(1))},
        ))
        return

    # Bare node reference
    bare_match = re.search(r"\b" + re.escape(node_id) + r"\b", stripped)
    col = offset + (bare_match.start() if bare_match else 0) + 1
    tokens.append(Token(
        type=TokenType.NODE_BARE,
        value=node_id,
        line=line_num,
        column=col,
        groups={"id": node_id, "label": node_id},
    ))


def _try_tokenize_nodes(
    stripped: str, line: str, line_num: int, tokens: List[Token]
) -> bool:
    """Attempt to tokenize node definitions with labels on a line.

    Handles bracket nodes (id[label]) and paren nodes (id(label)).

    Args:
        stripped: The stripped line content.
        line: The full original line text.
        line_num: The 1-based line number.
        tokens: The token list to append to.

    Returns:
        True if at least one node definition was found, False otherwise.
    """
    found = False
    offset = line.index(stripped)

    # Find bracket nodes: id[label]
    for match in _NODE_BRACKET_PATTERN.finditer(stripped):
        node_id = match.group(1)
        label = _strip_quotes(match.group(2))
        col = offset + match.start() + 1
        tokens.append(Token(
            type=TokenType.NODE_BRACKET,
            value=match.group(0),
            line=line_num,
            column=col,
            groups={"id": node_id, "label": label},
        ))
        found = True

    # Find paren nodes: id(label)
    for match in _NODE_PAREN_PATTERN.finditer(stripped):
        node_id = match.group(1)
        label = _strip_quotes(match.group(2))
        col = offset + match.start() + 1
        tokens.append(Token(
            type=TokenType.NODE_PAREN,
            value=match.group(0),
            line=line_num,
            column=col,
            groups={"id": node_id, "label": label},
        ))
        found = True

    return found


def _tokenize_bare_nodes(
    stripped: str, line: str, line_num: int, tokens: List[Token]
) -> None:
    """Tokenize bare node identifiers on a line.

    Only emits tokens for identifiers that are not reserved keywords.

    Args:
        stripped: The stripped line content.
        line: The full original line text.
        line_num: The 1-based line number.
        tokens: The token list to append to.
    """
    offset = line.index(stripped)

    for match in _NODE_BARE_PATTERN.finditer(stripped):
        word = match.group(1)
        if word.lower() not in _KEYWORDS:
            col = offset + match.start() + 1
            tokens.append(Token(
                type=TokenType.NODE_BARE,
                value=word,
                line=line_num,
                column=col,
                groups={"id": word, "label": word},
            ))
