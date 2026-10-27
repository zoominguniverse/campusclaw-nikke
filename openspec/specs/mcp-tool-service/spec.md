# mcp-tool-service Specification

## Purpose

在 CampusClaw 同一仓库交付可独立探测和真实调用的教学工具服务，让宿主通过握手、发现与执行验证完整接入链路。工具只提供学习提示，凭据由运行环境注入，并明确本课 HTTP JSON-RPC 子集的兼容边界。

## Requirements

### Requirement: Tool service runs alongside CampusClaw
The project SHALL provide `mcp-server/` and build it with the main Compose configuration. The API SHALL reach it over the internal network using its Base URL. `GET /health` SHALL return HTTP 200 without authentication. MCP unavailability SHALL NOT prevent the main API from becoming healthy.

#### Scenario: Independent service startup
- **WHEN** the project is built and started with valid environment configuration
- **THEN** the tool service health check succeeds and the API can make real HTTP requests to its `/mcp` endpoint

#### Scenario: Tool service is stopped
- **WHEN** the MCP service becomes unavailable
- **THEN** existing material, retrieval and tutoring routes remain available subject to their own dependencies

### Requirement: MCP endpoint authenticates every request
`POST /mcp` SHALL require the exact Bearer token configured at runtime using `MCP_AUTH_TOKEN`. Missing or incorrect credentials SHALL return HTTP 401 before method execution. No token SHALL be embedded in source, image layers, health responses or logs.

#### Scenario: Wrong token cannot list tools
- **WHEN** a caller submits `tools/list` without a token or with an incorrect token
- **THEN** the service returns HTTP 401 and does not execute discovery

### Requirement: JSON-RPC methods have readable errors
The endpoint SHALL support JSON-RPC 2.0 `initialize`, `tools/list` and `tools/call`, correlating response IDs with requests. Initialization SHALL report the supported protocol version and tools capability. Malformed JSON, invalid request envelopes, unknown methods and invalid parameters SHALL yield readable JSON-RPC errors without stack traces.

#### Scenario: Initialization and discovery
- **WHEN** an authenticated caller initializes using a supported version and lists tools
- **THEN** responses report the service capability and tool names, descriptions and object input schemas

#### Scenario: Invalid request
- **WHEN** an authenticated caller sends malformed JSON, a non-object envelope or an unknown method
- **THEN** it receives the corresponding JSON-RPC error with an appropriate request ID or null when no ID can be determined

### Requirement: Two discovered tools provide bounded teaching hints
The service SHALL expose `formula_hint` and `unit_convert`. Each SHALL accept a bounded `query` string, return text content and indicate tool failure through `isError`. Formula hints SHALL explain a next check; conversion hints SHALL explain unit relationships and steps without returning the requested final numerical answer.

#### Scenario: Formula hint
- **WHEN** `formula_hint` is called with a question about `2(x+3)=16` and an incorrect expansion
- **THEN** the result reminds the learner to multiply every term without solving for x

#### Scenario: Conversion hint
- **WHEN** `unit_convert` is asked to convert 5 meters to centimeters
- **THEN** it explains the unit relationship and operation direction without giving the final converted value

#### Scenario: Unsupported question
- **WHEN** a supported tool receives valid parameters about an unsupported topic
- **THEN** it returns a readable bounded tool error rather than fabricated guidance

### Requirement: Course transport scope is explicit
Service documentation SHALL identify this endpoint as the course's HTTP JSON-RPC tools subset and SHALL NOT claim complete MCP transport interoperability. Supported versions, input bounds and text-only result behavior SHALL be documented.

#### Scenario: Compatibility review
- **WHEN** a developer reads the service instructions
- **THEN** they can distinguish supported course methods from unimplemented stdio, resources, prompts and general streaming transport features
