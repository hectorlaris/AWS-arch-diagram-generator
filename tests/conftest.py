"""Shared fixtures and Hypothesis strategies for the test suite."""

import pytest


@pytest.fixture
def sample_mermaid_text() -> str:
    """Provide a minimal valid Mermaid graph for testing."""
    return """graph TD
    Client[Client] --> APIGateway[API Gateway]
    APIGateway --> Lambda[AWS Lambda]
    Lambda --> DynamoDB[DynamoDB]
"""


@pytest.fixture
def sample_mermaid_with_subgraph() -> str:
    """Provide a Mermaid graph with subgraph clusters for testing."""
    return """graph TD
    Client[Client] --> APIGateway[API Gateway]
    subgraph VPC
        Lambda[AWS Lambda] --> DynamoDB[DynamoDB]
        Lambda --> SQS[SQS]
    end
    APIGateway --> Lambda
"""
