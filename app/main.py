"""Application entry point for the AWS Architecture Diagram Generator.

This module re-exports the FastAPI application instance and provides a
uvicorn runner for local development. The app instance from `app.api.server`
already includes all route registrations and exception handler middleware.

Usage:
    python -m app.main          # run via module
    python app/main.py          # run directly
    uvicorn app.main:app        # run via uvicorn CLI
"""

from app.api.server import app


__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
