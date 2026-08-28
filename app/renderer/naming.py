"""Output file naming logic for the diagram renderer.

This module determines where to save generated diagram files
based on the input type:
- File path input: output goes to the same directory with the
  same base name as the source Markdown file.
- Raw text input: output goes to a temporary directory with a
  default base name.
"""

import tempfile
from pathlib import Path


def get_output_params_from_file(file_path: str) -> tuple[Path, str]:
    """Extract output directory and base name from a source Markdown file path.

    Derives the output location from the source file: the output directory
    is the parent directory of the file, and the base name is the filename
    without its extension.

    Args:
        file_path: Absolute or relative path to the source Markdown file.

    Returns:
        A tuple of (output_dir, output_name) where output_dir is the
        directory containing the source file and output_name is the
        filename stem (without extension).

    Examples:
        >>> get_output_params_from_file("/docs/architecture.md")
        (PosixPath('/docs'), 'architecture')

        >>> get_output_params_from_file("diagrams/my-system.md")
        (PosixPath('diagrams'), 'my-system')
    """
    source = Path(file_path)
    output_dir = source.parent
    output_name = source.stem
    return output_dir, output_name


def get_output_params_for_text() -> tuple[Path, str]:
    """Generate output directory and base name for raw Mermaid text input.

    Creates a temporary directory to store the rendered files and uses
    a default base name of "diagram". The temporary directory persists
    until the caller cleans it up or the OS removes it.

    Returns:
        A tuple of (output_dir, output_name) where output_dir is a
        freshly created temporary directory and output_name is "diagram".
    """
    output_dir = Path(tempfile.mkdtemp(prefix="mermaid_diagram_"))
    output_name = "diagram"
    return output_dir, output_name
