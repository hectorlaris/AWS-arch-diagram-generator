"""Integration tests for the full diagram generation pipeline.

Tests the complete flow from API request through parsing, mapping, rendering,
and response delivery, verifying that Graphviz and the diagrams library are
operational and that file system interactions work correctly.
"""

import io
import os
import platform
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Generator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.server import app


pytestmark = pytest.mark.integration


@pytest.fixture
def temp_markdown_file() -> Generator[Path, None, None]:
    """Create a temporary Markdown file with a valid Mermaid code block.

    Yields:
        Path to the temporary Markdown file.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="integration_test_"))
    md_file = temp_dir / "architecture.md"
    md_file.write_text(
        "# Architecture\n\n"
        "```mermaid\n"
        "graph LR\n"
        "    Client[Client] --> Lambda[AWS Lambda]\n"
        "    Lambda --> DynamoDB[DynamoDB]\n"
        "```\n",
        encoding="utf-8",
    )
    yield md_file
    # Cleanup temp directory after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def async_client() -> AsyncClient:
    """Create an httpx AsyncClient configured for the FastAPI test app.

    Returns:
        An AsyncClient instance using ASGI transport.
    """
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestFullPipelineFilePath:
    """Test the complete generation pipeline using file path input."""

    @pytest.mark.asyncio
    async def test_generate_from_markdown_file(
        self, async_client: AsyncClient, temp_markdown_file: Path
    ) -> None:
        """Valid Markdown file -> POST /generate -> PNG + SVG created.

        Verifies:
        - Response is HTTP 200 with status="success"
        - data.files contains 2 paths (one .png, one .svg)
        - The PNG and SVG files actually exist on disk
        - Output files are named based on the source file stem
        """
        response = await async_client.post(
            "/generate",
            json={"file_path": str(temp_markdown_file)},
        )

        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "success"
        assert body["data"] is not None
        assert "files" in body["data"]
        assert len(body["data"]["files"]) == 2

        files = body["data"]["files"]
        png_files = [f for f in files if f.endswith(".png")]
        svg_files = [f for f in files if f.endswith(".svg")]

        assert len(png_files) == 1, "Expected exactly one PNG file"
        assert len(svg_files) == 1, "Expected exactly one SVG file"

        # Verify files exist on disk
        png_path = Path(png_files[0])
        svg_path = Path(svg_files[0])
        assert png_path.exists(), f"PNG file not found at {png_path}"
        assert svg_path.exists(), f"SVG file not found at {svg_path}"

        # Verify output file naming matches source file stem
        expected_stem = temp_markdown_file.stem  # "architecture"
        assert png_path.stem == expected_stem
        assert svg_path.stem == expected_stem

        # Verify output directory is the same as the source file directory
        assert png_path.parent == temp_markdown_file.parent
        assert svg_path.parent == temp_markdown_file.parent


class TestGraphvizAvailability:
    """Test that Graphviz is installed and available on the system."""

    def test_graphviz_dot_is_available(self) -> None:
        """Verify that the Graphviz 'dot' command is accessible on PATH.

        The diagrams library and this application require Graphviz to be
        installed as a system dependency. This test confirms the dot
        executable can be found.
        """
        dot_path = shutil.which("dot")
        assert dot_path is not None, (
            "Graphviz 'dot' command not found on PATH. "
            "Install Graphviz: https://graphviz.org/download/"
        )


class TestDiagramsLibraryLoading:
    """Test that the diagrams library AWS provider modules load correctly."""

    def test_diagrams_aws_importable(self) -> None:
        """Verify that diagrams.aws can be imported and has submodules.

        The diagrams library must be installed with its AWS provider
        assets for service mapping and icon rendering to work.
        """
        import diagrams.aws

        assert hasattr(diagrams.aws, "__path__"), (
            "diagrams.aws should be a package with submodules"
        )

    def test_diagrams_aws_compute_module(self) -> None:
        """Verify that diagrams.aws.compute is available with Lambda class."""
        from diagrams.aws.compute import Lambda

        assert Lambda is not None

    def test_diagrams_aws_database_module(self) -> None:
        """Verify that diagrams.aws.database is available with Dynamodb class."""
        from diagrams.aws.database import Dynamodb

        assert Dynamodb is not None

    def test_diagrams_aws_general_module(self) -> None:
        """Verify the General fallback class is importable."""
        from diagrams.aws.general import General

        assert General is not None


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="File permission tests are unreliable on Windows",
)
class TestFileSystemPermissions:
    """Test file system permissions handling for non-writable directories."""

    @pytest.mark.asyncio
    async def test_non_writable_directory_returns_500(
        self, async_client: AsyncClient
    ) -> None:
        """Non-writable output directory produces an HTTP 500 error.

        When the output directory (derived from the source file location)
        is not writable, rendering fails and the API returns an appropriate
        error response without exposing internal details.
        """
        # Create a temp directory with a Markdown file, then make it read-only
        temp_dir = Path(tempfile.mkdtemp(prefix="readonly_test_"))
        md_file = temp_dir / "diagram.md"
        md_file.write_text(
            "```mermaid\n"
            "graph LR\n"
            "    A[Lambda] --> B[DynamoDB]\n"
            "```\n",
            encoding="utf-8",
        )

        try:
            # Make directory non-writable
            os.chmod(temp_dir, 0o555)

            response = await async_client.post(
                "/generate",
                json={"file_path": str(md_file)},
            )

            # Should fail with 500 since output can't be written
            assert response.status_code == 500
            body = response.json()
            assert body["status"] == "error"
            assert body["message"] is not None
            # Verify no internal details are leaked
            assert "Traceback" not in body["message"]
            assert "\\app\\" not in body["message"]
            assert "/app/" not in body["message"]
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_dir, 0o755)
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestRawMermaidTextBinaryResponse:
    """Test raw Mermaid text input returning a binary zip response."""

    @pytest.mark.asyncio
    async def test_raw_text_returns_zip_with_diagrams(
        self, async_client: AsyncClient
    ) -> None:
        """Raw Mermaid text input -> binary response with diagram.png and diagram.svg.

        When no file_path is provided, the API should return a downloadable
        zip archive containing the rendered PNG and SVG files.
        """
        mermaid_text = (
            "graph LR\n"
            "    Client[Client] --> Lambda[AWS Lambda]\n"
            "    Lambda --> S3[S3]\n"
        )

        response = await async_client.post(
            "/generate",
            json={"mermaid_text": mermaid_text},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

        # Read the zip content from the response
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            names = zf.namelist()
            assert "diagram.png" in names, (
                f"Expected 'diagram.png' in zip, got: {names}"
            )
            assert "diagram.svg" in names, (
                f"Expected 'diagram.svg' in zip, got: {names}"
            )

            # Verify the files have non-zero content
            png_data = zf.read("diagram.png")
            svg_data = zf.read("diagram.svg")
            assert len(png_data) > 0, "PNG file in zip should not be empty"
            assert len(svg_data) > 0, "SVG file in zip should not be empty"
