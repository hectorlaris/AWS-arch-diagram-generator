"""FastAPI application instance with error handling middleware."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.endpoints import router
from app.parser.exceptions import MermaidSyntaxError


logger = logging.getLogger(__name__)

app = FastAPI(
    title="AWS Architecture Diagram Generator",
    description="Converts Mermaid graph syntax into visual AWS architecture diagrams.",
)

app.include_router(router)


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all handler that prevents internal details from leaking.

    Logs the full exception for debugging while returning a safe
    generic message to the client. Never exposes stack traces,
    internal file paths, or dependency names.

    Args:
        request: The incoming HTTP request.
        exc: The unhandled exception.

    Returns:
        A JSON response with HTTP 500 and a generic error message.
    """
    logger.exception("Unhandled error during request processing")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "data": None,
            "warnings": [],
            "message": "An internal error occurred. Please try again.",
        },
    )


@app.exception_handler(MermaidSyntaxError)
async def mermaid_syntax_error_handler(
    request: Request, exc: MermaidSyntaxError
) -> JSONResponse:
    """Handle Mermaid syntax errors with location detail.

    Returns a 400 response including the line number, column position,
    and description of the syntax issue to help the user fix their input.

    Args:
        request: The incoming HTTP request.
        exc: The MermaidSyntaxError with line, column, and detail.

    Returns:
        A JSON response with HTTP 400 and syntax error details.
    """
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "data": None,
            "warnings": [],
            "message": (
                f"Mermaid syntax error at line {exc.line}, "
                f"column {exc.column}: {exc.detail}"
            ),
        },
    )
