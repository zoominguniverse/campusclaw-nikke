# streaming-tutor-answering Specification

## Purpose

把智能体角色、所选技能、授权绑定材料和有界历史接入同一次流式解题回答，使学生先看到证据再逐段看到正文。为有依据、无依据及流开始前后故障提供清晰契约，保留原单次知识问答的证据门槛与兼容性。

## Requirements

### Requirement: Retrieval is constrained before ranking
Every turn SHALL retrieve in hybrid mode only from the intersection of the agent's currently bound materials, authenticated effective class and current authorized subjects. Empty bindings SHALL mean no retrieval evidence, never all class materials. Incompatible unbound materials SHALL NOT block the turn. Retrieval SHALL retain existing profile and evidence eligibility rules and return at most four chunks before skill title-scope filtering.

#### Scenario: Unbound material has the best match
- **WHEN** an unbound or unauthorized material matches better than the agent's bound materials
- **THEN** it does not enter candidates, rank competition, provider input or citations

#### Scenario: Unbound index needs rebuilding
- **WHEN** an unrelated unbound material has an incompatible embedding profile
- **THEN** it does not cause a reindex-required failure for this conversation

### Requirement: Selected evidence receives stable source references
The system SHALL remove empty evidence and, when a skill specifies `资料`, retain only hits whose material title contains that value. Remaining sources SHALL receive contiguous one-based numbers, with at most 800 code points of source text per item. Citations SHALL contain title, material ID, subject, chunk index, generation and source-opening metadata from authorized stored evidence, never model-invented metadata.

#### Scenario: Filtering removes the first hit
- **WHEN** title filtering removes one or more retrieved chunks
- **THEN** the remaining citation numbers start at 1 without gaps and source metadata corresponds to the supplied text

### Requirement: Prompt assembly separates instructions and source data
The system SHALL construct instructions from the current agent prompt or default role, the single selected skill, guidance restrictions, evidence rules and a boundary identifying uploaded skill descriptions and materials as untrusted data. Numbered source text SHALL appear in a user message with the current question, not as system instructions. The assembly SHALL use bounded stored history and exclude client-controlled role or scope claims.

#### Scenario: Uploaded evidence contains instruction text
- **WHEN** a source or skill description says to ignore boundaries or reveal other classes
- **THEN** it cannot expand authorized retrieval or become a tool-execution privilege and the assembled input explicitly marks its untrusted boundary

### Requirement: Empty evidence still permits uncited tutoring
If retrieval or title filtering yields no evidence, or no material is bound, the turn SHALL still generate according to the agent and selected skill. Citations SHALL be an empty array and visible or stored text SHALL contain no numeric `[n]` citation markers or invented source claims. This behavior SHALL be confined to conversation messages; existing single-question evidence answering SHALL retain its no-evidence refusal contract.

#### Scenario: No material is bound
- **WHEN** an agent with an empty material binding receives a question
- **THEN** chat generation is attempted, references are empty and the answer is not merely the fixed no-evidence refusal

#### Scenario: Existing single-question endpoint has no evidence
- **WHEN** the existing knowledge ask endpoint receives a question with no eligible evidence
- **THEN** it still returns its existing no-evidence response without invoking chat

### Requirement: SSE sends metadata before incremental text
The message POST SHALL return `text/event-stream` without caching or intermediary buffering. It SHALL start with `meta` containing `status: ok`, skill or null and citations. MCP turns MAY emit cumulative tool metadata before the first `delta`, as defined by `mcp-tool-call-observability`; other turns retain one meta. After incremental deltas and successful persistence it SHALL emit one `done` with the assistant message ID. Joined deltas SHALL equal visible and stored content.

#### Scenario: Multiple actual model chunks
- **WHEN** a provider produces multiple chunks over time
- **THEN** the client receives metadata and text before provider completion, through the public web proxy, rather than an artificially split completed answer

### Requirement: Numeric markers cannot invent citations
Before emitting text, the system SHALL remove numeric citation markers when citations are empty and reject or suppress markers outside the supplied citation range. Marker validation SHALL work across provider and network chunk boundaries. Historical citation snapshots SHALL remain stable after index rebuilding; opening any source SHALL recheck current access and existence. Marker validation SHALL NOT be described as proof of semantic support.

#### Scenario: Citation marker is split across chunks
- **WHEN** an uncited provider emits `[` then `12` then `]` in separate chunks
- **THEN** no part of that citation marker appears in client deltas or persisted answer text

### Requirement: Failure behavior depends on whether the stream started
Before the first SSE frame, invalid input, missing resources, concurrent turns and unavailable dependencies SHALL return normal HTTP 400, 404, 409 or 503 responses. After `meta`, failure SHALL produce an `error` event with a generic message and no success `done`. Already emitted text SHALL be persisted as interrupted when storage is available; the stream SHALL close and release resources without leaking secrets.

#### Scenario: Failure after metadata but before any text
- **WHEN** the provider fails after metadata was sent but before a delta
- **THEN** the stream returns an error event, creates no completed assistant message and does not attempt to change its HTTP 200 status

#### Scenario: Storage failure after visible output
- **WHEN** saving the final assistant message fails
- **THEN** the system emits error rather than done and the UI does not claim the answer was saved

### Requirement: Stream transport preserves existing Bearer authentication
The system SHALL authenticate the POST using the existing Authorization Bearer access token. The client SHALL consume the response body using fetch streaming, without credentials in URLs or cookies. Unauthorized stream requests SHALL follow existing HTTP 401 behavior. Once a turn is accepted, token refresh or network recovery SHALL NOT automatically replay it.

#### Scenario: Unauthorized question submission
- **WHEN** the question POST carries no live access token
- **THEN** the system returns HTTP 401 before creating messages or opening an SSE stream
