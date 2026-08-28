"""Input handler for Mermaid diagram extraction and validation.

Provides functions to extract Mermaid code blocks from Markdown files
and to validate raw Mermaid text input. Supports both fenced code blocks
and plain Mermaid files.
"""

import re
from pathlib import Path


MERMAID_BLOCK_PATTERN = re.compile(
    r"```mermaid\s*\n(.*?)```",
    re.DOTALL,
)

GRAPH_DIRECTION_PATTERN = re.compile(
    r"^\s*(?:graph|flowchart)\s+(TD|LR|TB|RL)\b",
    re.MULTILINE | re.IGNORECASE,
)


def extract_mermaid_from_file(file_path: str) -> str:
    """Read a file and extract Mermaid diagram content.

    First attempts to find a fenced mermaid code block. If none is
    found, checks whether the file content itself is valid Mermaid syntax
    (starts with a graph/flowchart direction declaration).

    Args:
        file_path: Absolute or relative path to the file.

    Returns:
        The raw Mermaid text ready for parsing.

    Raises:
        FileNotFoundError: If the file does not exist or is not readable.
        ValueError: If no Mermaid diagram content is found in the file.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Path is not a file: {file_path}")

    content = path.read_text(encoding="utf-8")

    # Try fenced code block first
    match = MERMAID_BLOCK_PATTERN.search(content)
    if match:
        return match.group(1).strip()

    # Fall back: check if the file itself is raw Mermaid content
    stripped = content.strip()
    if GRAPH_DIRECTION_PATTERN.search(stripped):
        return stripped

    raise ValueError(
        "No Mermaid diagram found in file. The file should contain either "
        "a fenced mermaid code block or start with graph/flowchart direction."
    )


def extract_mermaid_from_text(mermaid_text: str) -> str:
    """Validate and normalize raw Mermaid text input.

    Strips leading/trailing whitespace, normalizes line endings from
    CRLF to LF, validates that the text is non-empty and contains a
    valid graph or flowchart direction declaration.

    Args:
        mermaid_text: Raw Mermaid diagram syntax.

    Returns:
        Cleaned Mermaid text ready for parsing.

    Raises:
        ValueError: If the text is empty after stripping or contains
            no graph/flowchart direction declaration.
    """
    # Strip leading/trailing whitespace
    cleaned = mermaid_text.strip()

    # Normalize line endings (\r\n -> \n)
    cleaned = cleaned.replace("\r\n", "\n")

    # Check if text is empty after stripping
    if not cleaned:
        raise ValueError(
            "Mermaid text is empty. Provide valid Mermaid graph syntax."
        )

    # Check for a graph/flowchart direction declaration
    if not GRAPH_DIRECTION_PATTERN.search(cleaned):
        raise ValueError(
            "No graph direction declaration found. "
            "Mermaid text must start with 'graph TD', 'graph LR', "
            "'graph TB', 'graph RL', or use 'flowchart' instead of 'graph'."
        )

    return cleaned
