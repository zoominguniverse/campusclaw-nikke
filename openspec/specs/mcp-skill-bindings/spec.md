# mcp-skill-bindings Specification

## Purpose

在现有中文技能文件和确定性技能选择之上增加可验证的远端工具绑定，把配置错误尽量留在教师保存时解决。每次对话只向模型开放命中技能许可的工具，并对发现内容变更后的旧绑定提供明确失效和重新确认过程。

## Requirements

### Requirement: Skill tool fields accept explicit MCP references
Skill files SHALL continue to accept `knowledge_search` and SHALL additionally accept references matching `tool@server`, where tool matches `[a-z][a-z0-9_]*` and server matches `[a-z][a-z0-9_-]*`. Existing separators, deduplication, text limits and routing SHALL remain compatible. Invalid references SHALL return a readable HTTP 400.

#### Scenario: Mixed supported tools
- **WHEN** a teacher submits `工具：knowledge_search，formula_hint@campus-tools`
- **THEN** the parser retains both unique entries and preserves the submitted source text

#### Scenario: Malformed tool reference
- **WHEN** the field contains `Formula_Hint@campus-tools`, `formula-hint@campus-tools` or bare `formula_hint`
- **THEN** saving fails with an error explaining the accepted syntax

### Requirement: Save validates every MCP binding before writing
Skill creation or replacement SHALL resolve each MCP server only in the authenticated class, require it to be connected and require the tool in its latest validated discovery snapshot. A foreign or nonexistent server SHALL produce the same HTTP 404; disconnected, missing-tool or unsupported bindings SHALL produce HTTP 400. Rejection SHALL preserve all prior skill state.

#### Scenario: A foreign server has the desired tool
- **WHEN** a teacher submits a reference existing only in another class
- **THEN** the response matches a nonexistent-server reference and neither a skill nor a binding is written

#### Scenario: Replacement mixes valid and invalid bindings
- **WHEN** an existing skill is replaced with one valid reference and one unavailable reference
- **THEN** the whole replacement is rejected and its original source, tools and confirmation remain unchanged

### Requirement: Changes to discovered declarations require reconfirmation
Bindings SHALL record confirmation of the tool name, complete description and input schema. Reconnecting with unchanged declarations SHALL preserve confirmation. Changed declarations or server connection details SHALL invalidate affected confirmations. A teacher SHALL review the full current declaration and explicitly resave before renewed execution.

#### Scenario: Tool description changes
- **WHEN** rediscovery changes a bound tool's description or schema
- **THEN** the UI marks its binding as needing review and calls are denied until the teacher confirms the new declaration

#### Scenario: Identical rediscovery
- **WHEN** the same server reconnects with identical declarations and connection details
- **THEN** previously confirmed bindings remain eligible without another confirmation

### Requirement: Only the selected skill grants tool candidates
Each turn SHALL retain the existing deterministic selection of at most one bound enabled skill. Only that skill's confirmed, connected and discovered permitted MCP tools SHALL become model candidates. `knowledge_search` SHALL retain its existing built-in retrieval meaning and SHALL NOT cause another remote call or expose the class-wide tool catalog.

#### Scenario: Model is asked to invoke an unbound tool
- **WHEN** a user asks to call a tool belonging to another or unmatched skill
- **THEN** that tool is absent from model declarations and a forged invocation is denied without dispatch

#### Scenario: Skill no longer matches
- **WHEN** a skill is disabled, unbound from the agent or does not match the current question
- **THEN** its tools do not remain candidates from a previous turn

### Requirement: Saved references can outlive availability
Disconnecting, renaming or deleting a server SHALL NOT silently rewrite skill source. Current unavailability SHALL be surfaced as `denied` in turn metadata when a selected skill contains such a reference, without initiating an unauthorized request or disclosing foreign server details. The rest of the turn SHALL continue.

#### Scenario: Previously valid reference is removed
- **WHEN** a selected skill references a tool removed by rediscovery or a server renamed after saving
- **THEN** its source remains intact, metadata explains the unavailable binding generically and tutoring proceeds without that tool
