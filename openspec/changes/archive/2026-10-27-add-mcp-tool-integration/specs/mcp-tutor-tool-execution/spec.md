# Spec Delta

## Purpose

把模型提出工具请求与宿主实际行使权限分开，让教学对话能够在有限轮次内获取远端提示并继续推理。成功、错误与拒绝都必须可见，外部文本不成为系统指令，且工具故障不能使原有检索和流式辅导整体失效。

## ADDED Requirements

### Requirement: The model proposes calls within a host controlled candidate set
For a matched skill with eligible MCP tools, the host SHALL send declarations derived from confirmed discovery to the configured chat model. The model SHALL choose whether to call, which candidate to call and its arguments. The host SHALL NOT infer a call merely from a tool name appearing in user text or automatically execute every eligible binding.

#### Scenario: Model declines a tool
- **WHEN** a question matches a tool-enabled skill but the model requests no tool
- **THEN** no eligible binding is automatically invoked and the answer is generated normally

#### Scenario: Two tools share a name across servers
- **WHEN** eligible tools have the same remote name on different servers
- **THEN** declarations use unambiguous identities and each model request resolves to exactly one confirmed reference

### Requirement: Every dispatch is reauthorized and schema validated
Before each remote call the host SHALL recheck current user and conversation access, selected-skill permission, same-class server availability, declaration confirmation and deployment permission. Arguments SHALL be validated against the discovered input schema. Failed checks SHALL produce `denied` without network dispatch or token disclosure.

#### Scenario: Model fabricates a tool or arguments
- **WHEN** the model requests a candidate-external name or supplies arguments outside its input schema
- **THEN** the host returns a bounded denied result to the model, records the attempt and contacts no remote server

#### Scenario: Permission changes between rounds
- **WHEN** a teacher disconnects the server or revokes the binding before a later dispatch
- **THEN** that later call is denied even though the model saw an earlier candidate snapshot

### Requirement: Tool results support multiple model rounds
Authorized calls SHALL use the stored Bearer credential and remote `tools/call`. Success and failure SHALL be returned as correlated data messages to the model, allowing another tool round or answer generation. Multiple proposed calls in one round SHALL each be checked and counted. The host SHALL never treat an empty or failed result as a successful hint.

#### Scenario: Two dependent calls
- **WHEN** the model requests a formula hint and then requests a conversion hint after seeing the first result
- **THEN** both rounds execute within budget, preserve their call identities and feed results into the next model request

#### Scenario: Local tool failure
- **WHEN** a remote tool times out, returns `isError`, emits malformed content or is unreachable
- **THEN** the failure is returned as a bounded error result and the model can continue using available evidence

### Requirement: Tool planning and execution have finite budgets
The host SHALL enforce configurable positive limits for tool rounds, proposals per turn, remote attempts per turn, cumulative remote attempts per conversation and total tool-phase time. Every remote attempt SHALL reserve quota before dispatch, including attempts that fail. Reaching a limit SHALL stop further dispatch, report the limit and proceed to answer generation without tools.

#### Scenario: Model repeats calls indefinitely
- **WHEN** the model continues requesting tools until a round or call budget is exhausted
- **THEN** no further tool request reaches the network and a final answer is attempted using collected results

#### Scenario: One round contains several calls
- **WHEN** a model response proposes more calls than the remaining budget
- **THEN** only calls within the remaining budget can execute, the rest are denied and all displayed outcomes accurately distinguish execution from refusal

#### Scenario: A conversation is reused
- **WHEN** a later question arrives in a conversation that has exhausted cumulative tool quota
- **THEN** it cannot reset that quota by reloading the page or restarting the API, while ordinary tutoring remains possible

### Requirement: Untrusted tool text cannot gain instruction authority
Remote descriptions and results SHALL NOT be inserted as system instructions or expand permissions. Tool results SHALL be bounded, source-labeled data. Known instruction-like payloads SHALL be discarded as a whole and replaced by a fixed explanation. Final answer input SHALL include sanitized results in the user-side data section alongside retrieval evidence.

#### Scenario: Tool returns an instruction payload
- **WHEN** a result says to ignore prior instructions, reveal credentials or invoke an unrelated tool
- **THEN** the known payload is replaced, its original text is excluded from model context and the call cannot grant another capability

#### Scenario: Result tries to manufacture a material citation
- **WHEN** tool text contains numeric citation markers without corresponding material evidence
- **THEN** tool data creates no new material citation and the existing output citation filter still applies

### Requirement: Tool failures preserve the tutoring contract
Tools unavailable at runtime, planner incompatibility and tool-phase timeouts SHALL degrade to explicit tool status or warning plus ordinary final generation. Retrieval scope, stored history bounds, guidance restrictions and citation validation SHALL remain enforced. Turns without MCP candidates SHALL retain the existing direct streaming path.

#### Scenario: Provider does not support tool declarations
- **WHEN** the configured model rejects tool-planning requests but can generate ordinary text
- **THEN** the turn reports a sanitized planner warning and attempts normal streaming generation rather than pretending a tool ran

#### Scenario: No MCP binding
- **WHEN** the selected skill contains only `knowledge_search` or there is no selected skill
- **THEN** no tool-planning request or MCP network request is added and existing behavior remains compatible
