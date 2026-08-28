"""Response builder functions for the diagram generation API.

Provides helper functions that construct consistent JSON and binary
responses following the standard API envelope structure:
{status, data, warnings, message}.
"""

import io
import zipfile
from typing import List

from fastapi.responses import JSONResponse, StreamingResponse

from app.api.models import GenerateData, GenerateResponse, WarningEntry


def success_response(
    data: GenerateData,
    warnings: List[WarningEntry],
) -> JSONResponse:
    """Build a successful HTTP 200 JSON response.

    Args:
        data: The generation result data containing file paths.
        warnings: List of warnings from the mapping phase.

    Returns:
        JSONResponse with status="success", Content-Type application/json.
    """
    response_model = GenerateResponse(
        status="success",
        data=data,
        warnings=warnings,
        message=None,
    )
    return JSONResponse(
        status_code=200,
        content=response_model.model_dump(),
        media_type="application/json",
    )


def error_response(
    status_code: int,
    message: str,
) -> JSONResponse:
    """Build an error JSON response with the given HTTP status code.

    Args:
        status_code: HTTP status code (4xx or 5xx).
        message: Human-readable error description.

    Returns:
        JSONResponse with status="error", Content-Type application/json.
    """
    response_model = GenerateResponse(
        status="error",
        data=None,
        warnings=[],
        message=message,
    )
    return JSONResponse(
        status_code=status_code,
        content=response_model.model_dump(),
        media_type="application/json",
    )


def binary_response(
    png_bytes: bytes,
    svg_bytes: bytes,
    warnings: List[WarningEntry],
) -> StreamingResponse:
    """Return diagram content as a zip archive containing PNG and SVG files.

    When raw Mermaid text is provided (no file path), this function packages
    both rendered outputs into a zip archive streamed back to the client.

    Args:
        png_bytes: The rendered PNG content.
        svg_bytes: The rendered SVG content.
        warnings: List of mapping warnings.

    Returns:
        StreamingResponse with Content-Type application/zip containing
        diagram.png and diagram.svg.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagram.png", png_bytes)
        zf.writestr("diagram.svg", svg_bytes)

    buffer.seek(0)

    headers = {
        "Content-Disposition": "attachment; filename=diagrams.zip",
    }

    # Include warnings as a custom header for client consumption
    if warnings:
        import json
        warnings_json = json.dumps(
            [w.model_dump() for w in warnings]
        )
        headers["X-Diagram-Warnings"] = warnings_json

    return StreamingResponse(
        content=buffer,
        media_type="application/zip",
        headers=headers,
    )
