# mcp-tool-call-observability Specification

## Purpose

让学生在回答正文到达前知道实际用了哪些工具，也让教师能够追查本班某次提问中的成功、失败和拒绝。流式事件、历史快照与独立调用审计通过稳定标识相互对应，同时避免把令牌、完整上下文或其他班级信息带入记录。

## Requirements

### Requirement: MCP turns emit tool metadata before answer text
MCP-enabled turns SHALL emit initial `meta` with skill and citations, then additional `meta` updates with cumulative `tool_calls` before the first `delta`. Each call SHALL expose a stable call ID, reference, round and `ok`, `error` or `denied` status. `tool_calls` SHALL be omitted when there is no outcome to report; repeated metadata SHALL NOT restart the answer.

#### Scenario: Two tool rounds precede text
- **WHEN** the model completes two tool rounds
- **THEN** their metadata updates arrive in order before any answer delta and cumulative entries retain stable identities

#### Scenario: No tool use
- **WHEN** no binding is unavailable and the model chooses no tool
- **THEN** metadata omits `tool_calls` and the client displays no fabricated tool-use badge

#### Scenario: Disconnected binding
- **WHEN** the selected skill contains a disconnected reference
- **THEN** metadata contains a denied outcome even though no remote call was attempted

### Requirement: Tool metadata remains separate from answer text
The client SHALL render tool status separately from assistant prose and citations. Updating metadata SHALL NOT insert text deltas, invent numeric references or clear existing skill and citation state. The final `done` SHALL still be sent only after assistant persistence, with concatenated deltas equal to stored answer content.

#### Scenario: Mixed tool and evidence sources
- **WHEN** a turn uses a remote hint and one authorized material citation
- **THEN** tool status identifies `tool@server`, material references retain their existing numbering and answer persistence matches visible deltas

### Requirement: Historical turns retain sanitized tool snapshots
Conversation history SHALL return tool outcomes associated with the original user message and assistant response. Complete and interrupted responses SHALL preserve available snapshots. Tools used before generation failure SHALL remain traceable even when no assistant text was produced. Old messages SHALL be treated as having no tool outcomes.

#### Scenario: Reload after a completed answer
- **WHEN** a user reopens their conversation
- **THEN** the tool badges and statuses correspond to the original turn without reexecuting tools

#### Scenario: Text generation fails after a successful tool call
- **WHEN** a tool succeeds but no assistant text is generated
- **THEN** the completed tool outcome remains in turn history and audit, and no completed assistant answer is fabricated

### Requirement: Every tool outcome has a class scoped audit record
Each host-observed invocation or unavailable selected binding SHALL record effective class, user, conversation, triggering user message, call ID, reference, round, time, duration and status. Bounded sanitized result summaries or fixed failure reasons SHALL be retained. Unknown or deleted servers SHALL use nullable server identity and same-class snapshots without looking up another class.

#### Scenario: Successful call
- **WHEN** a tool returns a usable text result
- **THEN** an `ok` record correlates with the stream outcome and its triggering stored user message

#### Scenario: Server no longer exists
- **WHEN** a selected reference cannot resolve within the effective class
- **THEN** a denied record can be stored using that class and reference without revealing whether a foreign server exists

### Requirement: Audit reads are bounded and teacher only
Audit listing SHALL expose only the authenticated teacher's effective class, ordered newest first with bounded pagination. Students and administrative roles without teacher membership SHALL receive HTTP 403. Server deletion SHALL preserve snapshots so historical tool references remain identifiable.

#### Scenario: Other class accesses audit
- **WHEN** another class teacher lists audits or filters by a foreign server ID
- **THEN** no foreign records are returned and foreign server filtering is indistinguishable from a nonexistent server

### Requirement: Metadata and audit data are sanitized
Tool metadata, persisted snapshots and audit responses SHALL NOT contain credentials, raw Authorization headers, full prompts, arbitrary exception text or complete outbound parameter payloads. Content length SHALL be bounded. Remote HTML SHALL be rendered as text. Known token values SHALL be redacted before persistence or transmission to a model or browser.

#### Scenario: Remote error echoes a credential
- **WHEN** a remote failure body includes a token or HTML payload
- **THEN** the token does not appear in stream, history, logs or audit, and markup is never executed
