# Requirements Document

## Introduction

This document defines the requirements for the AWS Architecture Diagram Generator — a Python REST API that accepts Mermaid diagram syntax describing AWS architectures, parses it, and produces visual architecture diagrams in PNG and SVG formats using the `diagrams` library with official AWS icons. The generated output is saved alongside the source Markdown file.

## Glossary

- **API_Server**: The REST API application that exposes endpoints for receiving Mermaid input and returning generated diagrams.
- **Mermaid_Parser**: The component responsible for parsing Mermaid graph syntax into an intermediate representation of nodes, edges, and clusters.
- **Diagram_Renderer**: The component that maps parsed Mermaid elements to `diagrams` library constructs and renders output files using Graphviz.
- **Mermaid_Code_Block**: A fenced code block (` ```mermaid ... ``` `) within a Markdown file describing an AWS architecture using Mermaid graph syntax.
- **Node**: A named element in a Mermaid graph that represents an AWS service (e.g., Lambda, DynamoDB, APIGateway).
- **Edge**: A directional connection between two Nodes in a Mermaid graph, representing data flow or interaction between AWS services.
- **Cluster**: A subgraph grouping in Mermaid syntax that maps to a logical boundary (e.g., VPC, region, or service group) rendered as a `Cluster` context in the `diagrams` library.
- **AWS_Icon**: An official AWS service icon provided by the `diagrams` library's AWS providers.
- **Output_Directory**: The filesystem directory where the source Markdown file containing the Mermaid_Code_Block is located; all generated diagrams are saved here.

## Requirements

### Requirement 1: Accept Mermaid Input via REST API

**User Story:** As a developer, I want to submit a Mermaid code block describing an AWS architecture through a REST API endpoint, so that I can programmatically generate architecture diagrams.

#### Acceptance Criteria

1. THE API_Server SHALL expose a POST endpoint that accepts a request body containing a file path to a Markdown file with a Mermaid_Code_Block.
2. THE API_Server SHALL expose a POST endpoint that accepts a request body containing raw Mermaid diagram text directly.
3. WHEN a valid file path is provided, THE API_Server SHALL read the Markdown file and extract the first Mermaid_Code_Block from it.
4. IF the provided file path does not exist or is not readable, THEN THE API_Server SHALL return an HTTP 400 response with a descriptive error message indicating the file could not be found or read.
5. IF the Markdown file contains no Mermaid_Code_Block, THEN THE API_Server SHALL return an HTTP 400 response with a message indicating no Mermaid diagram was found.
6. IF the request body is missing required fields, THEN THE API_Server SHALL return an HTTP 422 response with a validation error describing the missing fields.

### Requirement 2: Parse Mermaid Graph Syntax

**User Story:** As a developer, I want the system to parse Mermaid graph syntax accurately, so that all AWS service nodes, edges, and clusters are correctly identified for diagram generation.

#### Acceptance Criteria

1. WHEN a valid Mermaid_Code_Block is provided, THE Mermaid_Parser SHALL extract all Node identifiers and their display labels.
2. WHEN a valid Mermaid_Code_Block is provided, THE Mermaid_Parser SHALL extract all Edge connections including source node, target node, and optional edge labels.
3. WHEN the Mermaid_Code_Block contains `subgraph` definitions, THE Mermaid_Parser SHALL extract Cluster names and their contained Nodes.
4. THE Mermaid_Parser SHALL support Mermaid `graph TD`, `graph LR`, `graph TB`, and `graph RL` direction declarations.
5. IF the Mermaid_Code_Block contains syntax errors, THEN THE Mermaid_Parser SHALL return a descriptive error identifying the location and nature of the syntax issue.
6. THE Mermaid_Parser SHALL preserve the hierarchical relationship between Clusters and their nested Nodes.
7. WHEN an Edge has a label (e.g., `-->|label text|`), THE Mermaid_Parser SHALL capture the label text for rendering on the connection.

### Requirement 3: Map Mermaid Nodes to AWS Diagram Components

**User Story:** As a developer, I want Mermaid node labels to be automatically mapped to the correct AWS `diagrams` library component, so that the generated diagram uses official AWS icons.

#### Acceptance Criteria

1. THE Diagram_Renderer SHALL maintain a mapping of recognized AWS service names to their corresponding `diagrams` library classes (e.g., "Lambda" maps to `diagrams.aws.compute.Lambda`, "DynamoDB" maps to `diagrams.aws.database.Dynamodb`).
2. WHEN a Node label matches a recognized AWS service name after case-insensitive comparison and stripping of whitespace, hyphens, and underscores, THE Diagram_Renderer SHALL instantiate the corresponding `diagrams` library component with the official AWS_Icon.
3. THE Diagram_Renderer SHALL perform case-insensitive matching and ignore whitespace, hyphens, and underscores when mapping Node labels to AWS service names (e.g., "api_gateway", "API Gateway", and "apigateway" all match "APIGateway").
4. IF a Node label does not match any recognized AWS service name and cannot be resolved via the `diagrams.aws` provider hierarchy, THEN THE Diagram_Renderer SHALL render the node using the `diagrams.aws.general.General` class as the fallback representation and include a warning entry in the API response body listing each unrecognized service name.
5. THE Diagram_Renderer SHALL support at minimum the following AWS service mappings: APIGateway, Cognito, KMS, SecretsManager, Lambda, ECS, StepFunctions, SQS, SNS, Dynamodb, Cloudwatch, Cloudtrail, XRay, and Client.
6. WHEN the Mermaid_Code_Block references an AWS service not in the default mapping, THE Diagram_Renderer SHALL search all submodules of the `diagrams.aws` package for a class whose name matches the Node label using the same case-insensitive and delimiter-stripping rules, and if found, include the appropriate import automatically.
7. IF the dynamic resolution in criterion 6 finds no matching class in the `diagrams.aws` provider hierarchy, THEN THE Diagram_Renderer SHALL apply the fallback behavior defined in criterion 4.

### Requirement 4: Generate Visual Diagrams in PNG and SVG Formats

**User Story:** As a developer, I want the system to generate architecture diagrams in both PNG and SVG formats, so that I can use the output in documentation and presentations.

#### Acceptance Criteria

1. WHEN diagram generation is requested, THE Diagram_Renderer SHALL produce a PNG file of the architecture diagram.
2. WHEN diagram generation is requested, THE Diagram_Renderer SHALL produce an SVG file of the architecture diagram.
3. THE Diagram_Renderer SHALL render each Node as its associated icon with the Node name displayed below the icon.
4. THE Diagram_Renderer SHALL render Clusters as labeled bounding boxes grouping their contained Nodes.
5. THE Diagram_Renderer SHALL render Edges as directional arrows between the corresponding Node icons.
6. WHEN an Edge has a label, THE Diagram_Renderer SHALL display the label text adjacent to the midpoint of the rendered arrow without overlapping Node icons or other labels.
7. THE Diagram_Renderer SHALL use Graphviz as the underlying rendering engine for graph layout.
8. THE Diagram_Renderer SHALL produce PNG output with a minimum resolution of 150 DPI and minimum dimensions of 1024×768 pixels.
9. IF the Graphviz rendering engine fails to produce output, THEN THE Diagram_Renderer SHALL raise an error indicating the cause of the rendering failure without producing a partial output file.

### Requirement 5: Save Output to Source File Directory

**User Story:** As a developer, I want generated diagrams to be saved in the same directory as the source Markdown file, so that I can easily locate and reference them.

#### Acceptance Criteria

1. WHEN a file path is provided as input, THE Diagram_Renderer SHALL save generated PNG and SVG files in the Output_Directory.
2. THE Diagram_Renderer SHALL name output files using the base name of the source Markdown file with the appropriate extension (e.g., `architecture.md` produces `architecture.png` and `architecture.svg`).
3. IF the Output_Directory is not writable, THEN THE API_Server SHALL return an HTTP 500 response with a descriptive error message indicating the output could not be saved.
4. WHEN raw Mermaid text is provided without a file path, THE API_Server SHALL return the generated diagram files in the HTTP response body (as downloadable content).
5. WHEN diagram files are saved to the Output_Directory, THE API_Server SHALL return an HTTP 200 response containing the file paths of the generated PNG and SVG files.

### Requirement 6: Handle Unsupported or Ambiguous Service References

**User Story:** As a developer, I want clear feedback when my Mermaid diagram references AWS services that cannot be automatically mapped, so that I can correct or augment my input.

#### Acceptance Criteria

1. IF a Node label matches 2 or more AWS services, THEN THE Diagram_Renderer SHALL select the first match by alphabetical service name order and include a warning in the API response identifying the Node label, the selected service, and up to 5 alternative candidate services.
2. THE API_Server SHALL include a `warnings` field in successful responses listing any Nodes that matched zero AWS services or matched multiple AWS services, where each warning entry identifies the Node label and the reason it was flagged.
3. WHEN all Nodes in the Mermaid_Code_Block are successfully mapped to exactly one AWS service each, THE API_Server SHALL return an empty `warnings` list.
4. IF no Nodes in the Mermaid_Code_Block can be mapped to any AWS service, THEN THE API_Server SHALL still generate the diagram using rectangular placeholder shapes without AWS_Icon imagery and include a warning for each unmapped Node identifying the Node label and indicating that no matching AWS service was found.
5. IF the `warnings` list contains 1 or more entries, THEN THE API_Server SHALL still return a successful response containing both the rendered diagram and the `warnings` list.

### Requirement 7: REST API Response Structure

**User Story:** As a developer, I want consistent and predictable API responses, so that I can integrate the diagram generator into my workflow tooling.

#### Acceptance Criteria

1. THE API_Server SHALL return responses in JSON format with a consistent structure containing `status`, `data`, `warnings`, and `message` fields, where `data` defaults to `null` on error responses and `warnings` defaults to an empty list when no warnings are present.
2. WHEN diagram generation succeeds, THE API_Server SHALL return an HTTP 200 response within 30 seconds with `status` set to "success" and `data` containing an object with a `files` field listing the output file paths produced.
3. IF a client error occurs due to invalid input or a malformed request, THEN THE API_Server SHALL return an HTTP 4xx response with `status` set to "error" and a `message` field containing a human-readable string that identifies the invalid field or parameter.
4. IF an internal error occurs, THEN THE API_Server SHALL return an HTTP 500 response with `status` set to "error" and a `message` field containing a general failure description without exposing internal stack traces, file paths, or dependency names.
5. THE API_Server SHALL include a `Content-Type: application/json` header in all JSON responses and a `Content-Type` header with the appropriate media type (e.g., `image/png`, `image/svg+xml`) when returning binary diagram file content.
6. WHEN the API_Server returns an HTTP 200 response, THE API_Server SHALL ensure the response body is valid JSON parseable by any RFC 8259-compliant parser.

### Requirement 8: Mermaid Parser Round-Trip Property

**User Story:** As a developer, I want confidence that the Mermaid parser faithfully captures the structure of my diagrams, so that no information is lost during processing.

#### Acceptance Criteria

1. THE Mermaid_Parser SHALL produce an intermediate representation that preserves all Node identifiers, Edge connections, Edge labels, and Cluster hierarchies from the original Mermaid_Code_Block.
2. THE Mermaid_Parser SHALL provide a serialization method that outputs the intermediate representation back into valid Mermaid syntax.
3. FOR ALL valid Mermaid_Code_Blocks, parsing then serializing then parsing again SHALL produce an equivalent intermediate representation (round-trip property).
4. THE intermediate representation SHALL be inspectable as a structured data format (e.g., dictionary or dataclass) for testing and debugging purposes.
