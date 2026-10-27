# class-mcp-server-management Specification

## Purpose

让本班教师可靠地维护工具服务器及最近一次成功发现的工具清单，清楚区分登记、已连接和失效状态。所有管理操作沿用现有班级隔离与 Bearer 身份，并限制凭据流向和宿主可访问的远端地址。

## Requirements

### Requirement: MCP management is teacher only and class scoped
Only active teacher members SHALL manage or list MCP servers, discovered tools and audits. Effective class SHALL come from authenticated server-side identity. Non-teachers SHALL receive HTTP 403; unauthenticated requests SHALL receive 401. Foreign and nonexistent server IDs SHALL return identical HTTP 404 responses.

#### Scenario: Client claims a foreign class
- **WHEN** a teacher supplies another class in a path, query or JSON body
- **THEN** list results remain scoped to their effective class and foreign object access is indistinguishable from a nonexistent object

#### Scenario: Student accesses management directly
- **WHEN** a student requests server registration, connection, tools or audit routes
- **THEN** the server returns HTTP 403 without modifying state or contacting a remote server

### Requirement: Server registration is durable and unique
A teacher SHALL register, read, update and delete servers using a class-unique valid name and Base URL. Creation SHALL require a token; an omitted or blank token on update SHALL retain the stored token. Duplicate names and invalid fields SHALL return HTTP 400 without partial writes. Registration SHALL survive restart.

#### Scenario: Duplicate name within a class
- **WHEN** a teacher registers an existing name in the same class
- **THEN** registration fails with HTTP 400 while a different class can independently use that name

#### Scenario: Editing connection details
- **WHEN** a teacher changes a server name, URL or token
- **THEN** the new details are saved, the server becomes disconnected and its active discovered tools are cleared

### Requirement: Tokens are write only outside server storage
Stored tokens SHALL be recoverable only by the backend for authenticated outbound calls. Responses SHALL expose `has_token` without token values or ciphertext. Input controls SHALL be password fields cleared after submission. Tokens SHALL NOT enter client persistence, model input, source control, logs or error details.

#### Scenario: Token redaction
- **WHEN** a teacher creates, updates, lists or reads a server and then inspects responses and logs
- **THEN** no token substring or encrypted token field is returned, while `has_token` indicates configuration

### Requirement: Connect publishes only a complete discovery snapshot
Connect SHALL initialize and then discover tools with credentials. It SHALL mark the server connected only after a compatible handshake, complete validated discovery and atomic cache replacement. Any failure SHALL leave the server disconnected with no callable cache and a readable sanitized reason. Reconnecting SHALL replace rather than append tools.

#### Scenario: Discovery changes
- **WHEN** a second successful connection reports a changed tool set
- **THEN** exactly the new set becomes active, removed tools disappear and duplicate rows are absent

#### Scenario: Partial handshake or discovery failure
- **WHEN** initialization succeeds but discovery fails, or negotiation is incompatible
- **THEN** the server remains disconnected, no partial tool list is callable and existing tutoring remains available

### Requirement: Disconnect revokes cached availability
Disconnect SHALL clear the server's active tool cache and prevent subsequent tool dispatch. Deletion SHALL remove registration and cache while preserving historical audit snapshots. In-flight connection results SHALL NOT restore a server that was disconnected, edited or deleted after connection began.

#### Scenario: Saved skill after disconnect
- **WHEN** a skill still references a server that has been disconnected
- **THEN** its source remains readable but that reference cannot cause another remote call

#### Scenario: Disconnect races with connect
- **WHEN** discovery finishes after a later disconnect request
- **THEN** the stale discovery result is discarded and the server remains disconnected

### Requirement: Outbound destinations and responses are bounded
Registration and every outbound request SHALL enforce a deployment-controlled allowlist of exact HTTP or HTTPS origins. Credentials in URLs, unexpected paths, queries, fragments and redirects SHALL be rejected. Calls SHALL have finite time and response-size limits. Allowed private Compose destinations SHALL remain usable.

#### Scenario: Unapproved destination
- **WHEN** a teacher registers an unapproved origin or a permitted service redirects elsewhere
- **THEN** the host rejects the request without forwarding a token to the unexpected destination

#### Scenario: Oversized remote response
- **WHEN** discovery exceeds configured tool-count, schema or response-size bounds
- **THEN** connection fails with a sanitized error and publishes no partial cache
