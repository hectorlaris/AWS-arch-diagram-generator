"""Pydantic request and response models for the diagram generation API."""

from pydantic import BaseModel, model_validator
from typing import Optional, List


class GenerateRequest(BaseModel):
    """Request body for diagram generation endpoint.

    Accepts either a file path to a Markdown file containing a Mermaid code
    block, or raw Mermaid diagram text directly. At least one input source
    must be provided.
    """

    file_path: Optional[str] = None
    mermaid_text: Optional[str] = None

    @model_validator(mode="after")
    def validate_at_least_one_input(self) -> "GenerateRequest":
        """Ensure at least one input source is provided."""
        if not self.file_path and not self.mermaid_text:
            raise ValueError(
                "Either 'file_path' or 'mermaid_text' must be provided"
            )
        return self


class WarningEntry(BaseModel):
    """A warning about node mapping during diagram generation.

    Produced when a node label cannot be uniquely resolved to an AWS
    service class, or when no matching service is found.
    """

    node_label: str
    reason: str
    selected_service: Optional[str] = None
    alternatives: Optional[List[str]] = None


class GenerateData(BaseModel):
    """Successful generation result data.

    Contains the list of file paths produced by the diagram renderer.
    """

    files: List[str]


class GenerateResponse(BaseModel):
    """Standard API response envelope.

    All API responses follow this consistent structure regardless of
    success or failure. The `status` field is either "success" or "error".
    """

    status: str
    data: Optional[GenerateData] = None
    warnings: List[WarningEntry] = []
    message: Optional[str] = None
