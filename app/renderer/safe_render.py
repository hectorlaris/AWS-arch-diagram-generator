"""Safe rendering wrapper with cleanup on failure.

Wraps the core render_diagram function to ensure that partially-created
output files are cleaned up if rendering fails partway through.
"""

import os
from pathlib import Path
from typing import List

from app.mapper.mapper import MappingResult
from app.parser.models import MermaidGraph
from app.renderer.exceptions import RenderError
from app.renderer.renderer import RenderResult, render_diagram


def safe_render(
    graph: MermaidGraph,
    output_dir: Path,
    output_name: str,
    mappings: List[MappingResult],
) -> RenderResult:
    """Render a diagram with cleanup on failure.

    Delegates to render_diagram but ensures that if Graphviz produces
    partial output before failing, those files are removed before the
    error is re-raised as a RenderError.

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
    png_path = output_dir / f"{output_name}.png"
    svg_path = output_dir / f"{output_name}.svg"

    try:
        return render_diagram(graph, output_dir, output_name, mappings)
    except RenderError:
        # Clean up partial output files
        for path in [png_path, svg_path]:
            if path.exists():
                os.remove(path)
        raise
    except Exception as exc:
        # Clean up partial output files
        for path in [png_path, svg_path]:
            if path.exists():
                os.remove(path)
        raise RenderError(str(exc)) from exc
