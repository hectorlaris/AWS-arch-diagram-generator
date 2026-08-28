"""API endpoint definitions for the diagram generation service.

This module implements the POST /generate route that wires together
the full pipeline: input handling → parsing → mapping → rendering → response.
"""

import tempfile
from pathlib import Path
from typing import Tuple

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.models import GenerateData, GenerateRequest
from app.input_handler import extract_mermaid_from_file, extract_mermaid_from_text
from app.mapper.mapper import map_all_nodes
from app.parser.parser import parse_mermaid
from app.renderer.exceptions import RenderError
from app.renderer.safe_render import safe_render
from app.response import binary_response, error_response, success_response


router = APIRouter()


def get_output_params_from_file(file_path: str) -> Tuple[Path, str]:
    """Derive output directory and base name from a source Markdown file path.

    The output files are saved in the same directory as the source file,
    using the source file's stem (filename without extension) as the base name.

    Args:
        file_path: Path to the source Markdown file.

    Returns:
        A tuple of (output_directory, base_name).
    """
    source = Path(file_path)
    output_dir = source.parent
    output_name = source.stem
    return output_dir, output_name


def get_output_params_for_text() -> Tuple[Path, str]:
    """Create a temporary directory and default name for raw text input.

    When no file path is provided, diagrams are rendered to a temporary
    directory with a default base name of "diagram".

    Returns:
        A tuple of (temp_directory_path, "diagram").
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="diagram_"))
    return temp_dir, "diagram"


@router.post("/generate", response_model=None)
async def generate_diagram(
    request: GenerateRequest,
) -> JSONResponse | StreamingResponse:
    """Generate an AWS architecture diagram from Mermaid input.

    Accepts either a file path to a Markdown file containing a Mermaid
    code block, or raw Mermaid text. Produces PNG and SVG outputs via
    the diagrams library and Graphviz.

    For file path input, the rendered files are saved alongside the source
    file and their paths are returned in the response body.

    For raw text input, the rendered files are returned as a downloadable
    zip archive in the response body.

    Args:
        request: The generation request with file_path or mermaid_text.

    Returns:
        JSON response with file paths, or binary response with diagram files.
    """
    # Phase 1: Extract Mermaid text from input source
    file_mode = request.file_path is not None

    try:
        if file_mode:
            mermaid_text = extract_mermaid_from_file(request.file_path)
            output_dir, output_name = get_output_params_from_file(
                request.file_path
            )
        else:
            mermaid_text = extract_mermaid_from_text(request.mermaid_text)
            output_dir, output_name = get_output_params_for_text()
    except FileNotFoundError as exc:
        return error_response(400, str(exc))
    except ValueError as exc:
        return error_response(400, str(exc))

    # Phase 2: Parse Mermaid text into IR
    # MermaidSyntaxError propagates to the registered exception handler
    graph = parse_mermaid(mermaid_text)

    # Phase 3: Map nodes to diagrams.aws classes
    mappings = map_all_nodes(graph.nodes)

    # Phase 4: Render the diagram
    try:
        result = safe_render(graph, output_dir, output_name, mappings)
    except RenderError:
        return error_response(
            500, "Diagram rendering failed. Please check your input."
        )

    # Phase 5: Build response
    warnings = result.warnings

    if file_mode:
        data = GenerateData(
            files=[str(result.png_path), str(result.svg_path)]
        )
        return success_response(data, warnings)
    else:
        # Read rendered files and return as binary download
        png_bytes = result.png_path.read_bytes()
        svg_bytes = result.svg_path.read_bytes()
        return binary_response(png_bytes, svg_bytes, warnings)
