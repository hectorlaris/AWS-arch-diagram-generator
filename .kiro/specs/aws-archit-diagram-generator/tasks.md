# Implementation Plan: AWS Architecture Diagram Generator

## Overview

This plan implements a Python REST API service that converts Mermaid graph syntax into visual AWS architecture diagrams using the `diagrams` library with official AWS icons. The implementation follows an incremental approach: project scaffolding → data models → parser → mapper → renderer → input handler → API layer → response builder, with testing woven in after each component.

## Tasks

- [x] 1. Set up project structure and dependencies
  - [x] 1.1 Create project directory structure and configuration files
    - Create `app/` directory with `__init__.py`, `app/api/`, `app/parser/`, `app/mapper/`, `app/renderer/` subdirectories
    - Create `pyproject.toml` (or `requirements.txt`) with dependencies: `fastapi`, `uvicorn`, `pydantic`, `diagrams`, `hypothesis`, `pytest`, `httpx`
    - Create `tests/` directory structure: `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/conftest.py`
    - Add a minimal `README.md` with setup instructions noting Graphviz as a system dependency
    - _Requirements: All (project foundation)_

- [x] 2. Implement data models and custom exceptions
  - [x] 2.1 Create intermediate representation (IR) dataclasses
    - Implement `MermaidNode`, `MermaidEdge`, `MermaidCluster`, and `MermaidGraph` dataclasses in `app/parser/models.py`
    - Include `__eq__`, `__hash__` on `MermaidNode`; `serialize()` method stub on `MermaidGraph`
    - Include `get_node_by_id()` and `get_cluster_for_node()` helper methods on `MermaidGraph`
    - _Requirements: 2.1, 2.2, 2.3, 8.1, 8.4_

  - [x] 2.2 Create Pydantic request/response models
    - Implement `GenerateRequest` with `model_validator` ensuring at least one input in `app/api/models.py`
    - Implement `WarningEntry`, `GenerateData`, `GenerateResponse` Pydantic models
    - _Requirements: 1.1, 1.2, 1.6, 7.1_

  - [x] 2.3 Create custom exception classes
    - Implement `MermaidSyntaxError` (with `line`, `column`, `detail`) in `app/parser/exceptions.py`
    - Implement `RenderError` (with `cause`) in `app/renderer/exceptions.py`
    - Implement `ServiceMappingError` in `app/mapper/exceptions.py`
    - _Requirements: 2.5, 4.9, 7.4_

- [x] 3. Checkpoint - Ensure data models are correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Mermaid Parser
  - [x] 4.1 Implement the lexical phase (regex tokenization)
    - Create `app/parser/tokenizer.py` with regex patterns for: direction declaration, node definitions (bracket, paren, bare), edge connections (solid `-->`, dotted `-.->`, labeled `-->|text|`), subgraph boundaries (`subgraph Name` / `end`)
    - Define token types and a tokenize function that returns a list of tokens with line/column positions
    - _Requirements: 2.1, 2.2, 2.4, 2.7_

  - [x] 4.2 Implement the structural phase (IR builder)
    - Create `app/parser/parser.py` with `parse_mermaid(text: str) -> MermaidGraph` function
    - Process tokens sequentially: extract direction, build nodes, connect edges, track subgraph nesting via stack
    - Raise `MermaidSyntaxError` with line/column/detail on invalid input
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 4.3 Implement the `serialize()` method on `MermaidGraph`
    - Output valid Mermaid graph syntax from the IR (direction line, node declarations, edges, subgraphs)
    - Ensure round-trip property: `parse(serialize(parse(input))) == parse(input)`
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 4.4 Write property tests for the Mermaid Parser
    - **Property 2: Parser Completeness** — For any valid graph with N nodes, M edges, K clusters, the IR contains exactly N nodes, M edges, K clusters with correct structure
    - **Property 3: Parser Round-Trip** — `parse(serialize(parse(input))) == parse(input)` for all valid inputs
    - **Property 4: Parser Error Reporting** — All malformed inputs produce `MermaidSyntaxError` with line/column/detail
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.5, 2.6, 2.7, 8.1, 8.2, 8.3**

  - [ ]* 4.5 Write unit tests for the Mermaid Parser
    - Test each direction declaration (TD, LR, TB, RL)
    - Test node shapes: `id[label]`, `id(label)`, bare `id`
    - Test edge types: solid, dotted, labeled
    - Test subgraph nesting (single level, nested)
    - Test syntax error cases: unclosed subgraph, missing direction, invalid edge
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 5. Checkpoint - Ensure parser tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Service Mapper
  - [x] 6.1 Implement normalization and static mapping
    - Create `app/mapper/normalizer.py` with `normalize_service_name(label: str) -> str` (lowercase, strip whitespace/hyphens/underscores)
    - Create `app/mapper/static_map.py` with `STATIC_SERVICE_MAP` dictionary covering the 14+ required services and common aliases
    - _Requirements: 3.1, 3.2, 3.3, 3.5_

  - [x] 6.2 Implement dynamic resolution and fallback
    - Create `app/mapper/resolver.py` with `resolve_service(node_label: str) -> tuple[Optional[Type], Optional[WarningEntry]]`
    - Implement Tier 1 lookup (static map) then Tier 2 (introspect `diagrams.aws` submodules at runtime)
    - Fall back to `diagrams.aws.general.General` when unresolved, producing a `WarningEntry`
    - Handle ambiguous matches: select first alphabetical class, produce warning with up to 5 alternatives
    - _Requirements: 3.2, 3.4, 3.6, 3.7, 6.1, 6.2, 6.4_

  - [x] 6.3 Implement `map_all_nodes` orchestrator
    - Create `app/mapper/mapper.py` with `map_all_nodes(nodes: List[MermaidNode]) -> List[MappingResult]`
    - Define `MappingResult` dataclass with `node_id`, `node_label`, `diagrams_class`, `warning`
    - _Requirements: 3.1, 3.4, 6.2, 6.3, 6.5_

  - [ ]* 6.4 Write property tests for the Service Mapper
    - **Property 5: Service Name Normalization Consistency** — All case/delimiter variations of a known service resolve to the same class
    - **Property 6: Unknown Service Fallback** — All unresolvable labels return `General` class + warning
    - **Property 7: Ambiguous Match Resolution** — Multiple matches select first alphabetical + produce warning with alternatives
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.7, 6.1**

  - [ ]* 6.5 Write unit tests for the Service Mapper
    - Test all 14 required service mappings individually
    - Test case-insensitive matching ("lambda", "LAMBDA", "Lambda")
    - Test delimiter-stripping ("api_gateway", "API Gateway", "api-gateway")
    - Test fallback to General class for unknown labels
    - Test ambiguous match warning structure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 6.1_

- [x] 7. Checkpoint - Ensure mapper tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Diagram Renderer
  - [x] 8.1 Implement diagram rendering pipeline
    - Create `app/renderer/renderer.py` with `render_diagram(graph, output_dir, output_name, mappings) -> RenderResult`
    - Build `diagrams.Diagram` context with direction, output format (png + svg), graph attributes (dpi=150, size)
    - Create nodes within appropriate `Cluster` context managers for cluster membership
    - Connect edges with optional labels using `diagrams.Edge`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 8.2 Implement safe rendering with cleanup on failure
    - Create `app/renderer/safe_render.py` with `safe_render()` wrapper
    - On Graphviz failure, remove any partially-created PNG/SVG files before re-raising as `RenderError`
    - _Requirements: 4.9, 5.3_

  - [x] 8.3 Implement output file naming logic
    - For file path input: derive base name from source Markdown filename, save to same directory
    - For raw text input: use a generated name (e.g., "diagram") in a temp directory
    - _Requirements: 5.1, 5.2, 5.4_

  - [ ]* 8.4 Write property test for output file naming
    - **Property 8: Output File Naming** — For any valid file path with base name B, output files are named `B.png` and `B.svg` in the source directory
    - **Validates: Requirements 5.2**

  - [ ]* 8.5 Write unit tests for the Diagram Renderer
    - Test that rendering produces both PNG and SVG files
    - Test cluster nesting renders correctly
    - Test cleanup on render failure (no partial files left)
    - Test output file naming from various source file paths
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.9, 5.1, 5.2_

- [x] 9. Checkpoint - Ensure renderer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement Input Handler
  - [x] 10.1 Implement file reading and Mermaid extraction
    - Create `app/input_handler.py` with `extract_mermaid_from_file(file_path: str) -> str`
    - Use regex `MERMAID_BLOCK_PATTERN` to find first ` ```mermaid ... ``` ` block
    - Raise `FileNotFoundError` for missing files, `ValueError` for files without a Mermaid block
    - _Requirements: 1.3, 1.4, 1.5_

  - [x] 10.2 Implement raw text validation
    - Create `extract_mermaid_from_text(mermaid_text: str) -> str` in same module
    - Validate non-empty input and presence of a `graph` direction declaration
    - Strip leading/trailing whitespace and normalize line endings
    - _Requirements: 1.2_

  - [ ]* 10.3 Write property tests for Input Handler
    - **Property 1: Mermaid Code Block Extraction** — For any Markdown with embedded mermaid blocks, extraction returns the first block's contents
    - **Property 11: No-Mermaid Detection** — For any Markdown without mermaid blocks, extraction raises `ValueError`
    - **Validates: Requirements 1.3, 1.5**

  - [ ]* 10.4 Write unit tests for Input Handler
    - Test extraction from Markdown with one mermaid block
    - Test extraction from Markdown with multiple mermaid blocks (returns first)
    - Test FileNotFoundError for non-existent path
    - Test ValueError for empty file and file without mermaid
    - Test raw text validation with valid and invalid inputs
    - _Requirements: 1.2, 1.3, 1.4, 1.5_

- [x] 11. Implement API Server and Response Builder
  - [x] 11.1 Create FastAPI application with error handling middleware
    - Create `app/api/server.py` with FastAPI app instance
    - Register global exception handler for unhandled exceptions (500, generic message, no internals)
    - Register `MermaidSyntaxError` handler (400 with line/column/detail)
    - _Requirements: 7.3, 7.4_

  - [x] 11.2 Implement POST /generate endpoint
    - Create `app/api/endpoints.py` with the `/generate` route
    - Wire together: input handling → parsing → mapping → rendering → response
    - Handle `FileNotFoundError` → 400, `ValueError` (no mermaid) → 400, `RenderError` → 500
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.4, 5.5_

  - [x] 11.3 Implement Response Builder functions
    - Create `app/response.py` with `success_response()`, `error_response()`, `binary_response()`
    - Ensure all responses follow the JSON envelope: `{status, data, warnings, message}`
    - Set `Content-Type: application/json` for JSON responses, appropriate media type for binary
    - _Requirements: 7.1, 7.2, 7.5, 7.6_

  - [ ]* 11.4 Write property tests for API responses
    - **Property 9: Response Envelope Consistency** — All responses contain `status`, `data`, `warnings`, `message` keys; HTTP 200 responses are valid JSON
    - **Property 10: Error Response Sanitization** — HTTP 500 responses contain no stack traces, internal paths, or dependency names
    - **Validates: Requirements 7.1, 7.4, 7.6**

  - [ ]* 11.5 Write unit tests for API Server
    - Test 422 response for missing required fields
    - Test 400 response for non-existent file path
    - Test 400 response for file without mermaid block
    - Test 400 response for invalid Mermaid syntax
    - Test 200 response with successful generation (file path mode)
    - Test 200 response with successful generation (raw text mode)
    - Test warnings field populated for unrecognized services
    - Test Content-Type headers on all response types
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 5.4, 5.5, 6.2, 6.3, 6.5, 7.1, 7.2, 7.3, 7.5_

- [x] 12. Checkpoint - Ensure all unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Integration and end-to-end validation
  - [x] 13.1 Write integration tests
    - Test full pipeline: valid Markdown file → POST /generate → PNG + SVG created in correct directory
    - Test Graphviz availability check
    - Test `diagrams` library AWS provider module loading
    - Test file system permissions handling (non-writable directory)
    - _Requirements: 4.7, 5.1, 5.2, 5.3_

  - [x] 13.2 Wire application entry point
    - Create `app/main.py` importing the FastAPI app and registering all routes and middleware
    - Add uvicorn runner for local development (`if __name__ == "__main__"`)
    - Verify the app starts and `/docs` (OpenAPI) is accessible
    - _Requirements: All (final wiring)_

- [x] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after major components
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Graphviz must be installed as a system dependency before running renderer or integration tests
- The `diagrams` library requires Graphviz's `dot` command to be available on PATH

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 2, "tasks": ["4.1", "6.1"] },
    { "id": 3, "tasks": ["4.2", "6.2"] },
    { "id": 4, "tasks": ["4.3", "6.3", "10.1", "10.2"] },
    { "id": 5, "tasks": ["4.4", "4.5", "6.4", "6.5", "10.3", "10.4"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3"] },
    { "id": 8, "tasks": ["8.4", "8.5"] },
    { "id": 9, "tasks": ["11.1", "11.3"] },
    { "id": 10, "tasks": ["11.2"] },
    { "id": 11, "tasks": ["11.4", "11.5"] },
    { "id": 12, "tasks": ["13.1", "13.2"] }
  ]
}
```
