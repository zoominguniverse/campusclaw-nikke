# documented-api-verification Specification

## Purpose

让第 5 课的主要接口有与实现同源、能在浏览器试调的文档，并通过按 URL 组织的脚本验证响应和数据库结果。把一键报告、流式契约、权限负例和人工验收状态记录下来，避免只检查状态码或把演示输出计为真实通过。

## Requirements

### Requirement: OpenAPI is generated from handler metadata
The system SHALL generate OpenAPI from annotations colocated with route handlers and expose it at `/openapi.json`. It SHALL document actual paths, methods, schemas, success and error responses, role restrictions and Bearer requirements for auth login/refresh/logout/me, material list/upload/detail/download/reindex, retrieval/ask, agents, skills and conversations/messages. Operation IDs SHALL be unique and stable; public routes SHALL declare no authentication.

#### Scenario: Document matches registered routes
- **WHEN** the document is generated during verification
- **THEN** each documented operation maps to a registered handler and every required main operation appears with its actual input and output contract

### Requirement: Swagger supports same origin Bearer trial calls
The browser SHALL open `/swagger/` and `/swagger/index.html` and load the generated document and required assets under the existing content security policy. Swagger SHALL permit supplying a Bearer token for protected trial calls without saving it persistently. SSE operations SHALL document frame examples and a fetch or command-line streaming example when Swagger cannot display incremental events.

#### Scenario: Login then call a protected endpoint
- **WHEN** a user obtains a token from documented login and authorizes Swagger for the current page
- **THEN** a main protected operation can be called through the public same-origin entry and responses follow the document

### Requirement: Interface scripts are organized by URL and method
The repository SHALL contain `apitest/cases/` with one runnable script for each covered URL/method pair, preserving path parameter placeholders in directories. `apitest/run_all.py` SHALL discover and run them once, report independent failures, exit nonzero on failure and produce an HTML summary with per-case assertions, timings and pass/fail/skip outcomes. Reports SHALL NOT be committed to Git.

#### Scenario: One command executes all interface cases
- **WHEN** a developer invokes the documented runner in its configured test environment
- **THEN** it runs the available case scripts and produces a readable HTML report even when a case fails

### Requirement: Verification checks response and database agreement
Interface cases SHALL cover login, retrieval, agent prompts/bindings, skill management, conversation creation and one SSE message. Assertions SHALL verify response content plus corresponding database state, including token hashing, ownership, title, agent, message order, selected skill, citations and concatenated text. Rejected writes SHALL assert unchanged database state. Credentials and Authorization values SHALL be redacted from logs and reports.

#### Scenario: Stream and stored assistant disagree
- **WHEN** a done event claims success but stored content differs from concatenated deltas or citations differ from metadata
- **THEN** the case fails even if every HTTP response had a successful status code

### Requirement: Verification uses isolated data and tests denied access
Tests SHALL target an explicitly configured isolated database and upload store and SHALL NOT reset the running development database. They SHALL cover unauthenticated access, student writes, same-class other-user conversations, foreign-class resources, disabled agents, unbound evidence and current subject revocation. Foreign and nonexistent resource checks SHALL compare status and body, not status alone.

#### Scenario: Misconfigured runner points at the active development stack
- **WHEN** the runner cannot establish that its destructive fixtures target the dedicated test environment
- **THEN** it fails before any fixture reset or write

### Requirement: Acceptance distinguishes automated fixtures from real behavior
Acceptance SHALL include visible incremental delivery through the web entry, empty-evidence behavior, skill toggle effects, fixed-agent conversations and real-provider review of mathematics and language guidance. Verification records SHALL identify provider mode and include peer-check evidence for ownership, agent isolation, class boundary and skill switching. Skipped real-provider or peer checks SHALL remain pending rather than count as passed.

#### Scenario: Only deterministic provider tests were run
- **WHEN** automated transport and routing cases pass using a fixture provider
- **THEN** the report labels them as fixture validation and retains real guidance behavior and peer acceptance as uncompleted items
