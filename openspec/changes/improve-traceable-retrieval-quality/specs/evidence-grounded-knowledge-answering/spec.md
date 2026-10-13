# Spec Delta

## Purpose

让知识问答使用当前授权范围内检索到的证据，提供简短回答和可打开原文的引用。把完全无命中、命中但不能支持问题、引用校验失败和模型故障区分开来，并通过可复核的证据跨度和语义评测降低虚假出处的风险。

## ADDED Requirements

### Requirement: Answer generation is gated by authorized evidence
The system SHALL retrieve the latest question in hybrid mode within authenticated class and subject scope, select at most four nonredundant eligible chunks and call chat only when evidence exists. Provider input SHALL contain permitted evidence, subject/material context and bounded allowed history, without vectors, unauthorized content or client system messages.

#### Scenario: No authorized evidence is found
- **WHEN** hybrid retrieval yields no eligible chunk
- **THEN** the system returns `资料中未找到相关内容` with empty citations and does not call chat

#### Scenario: Client supplies privileged history
- **WHEN** history includes system messages or attempts to expand scope
- **THEN** those messages cannot become trusted instructions or expand the retrieved evidence scope

### Requirement: Real answers address the question concisely
In a semantic deployment the system SHALL use a configured real chat provider and return supported factual answers of at most 200 Chinese-visible Unicode code points, excluding citation markers. Demo output SHALL be visibly labelled and SHALL NOT be counted as real answer acceptance. A response exceeding the bound SHALL be rejected or regenerated within a bounded retry policy, not silently truncated through a factual claim.

#### Scenario: Relevant evidence occurs at the end of a long chunk
- **WHEN** the question concerns that evidence
- **THEN** the answer addresses that question rather than reproducing the beginning of the chunk

#### Scenario: Chat is deterministic
- **WHEN** a user asks a question in demo mode
- **THEN** the UI marks the response as demo output and does not imply semantic understanding

### Requirement: Evidence insufficiency is an explicit answer outcome
The system SHALL allow an evidence-insufficient outcome when retrieved chunks do not support the requested fact or when material only supports a different relation. That outcome SHALL use `资料不足以回答该问题` and no asserted factual answer or citations. Shared words or similarity alone SHALL NOT authorize an unsupported answer.

#### Scenario: Query reverses a scientific relation
- **WHEN** retrieved evidence states acceleration is proportional to force and inversely proportional to mass, but the question asserts the reverse
- **THEN** the answer corrects the assertion using supported evidence or reports insufficiency instead of repeating the unsupported assertion

#### Scenario: Retrieved chunk is related but lacks the requested detail
- **WHEN** the question asks for a value or condition absent from the evidence
- **THEN** the system reports evidence insufficiency rather than inventing it

### Requirement: Factual claims have reconciled source references
For evidence-backed answers the system SHALL require each factual claim to identify a supplied evidence item and an exact supporting quote with a valid source span. The server SHALL validate structure, bounds, quote membership and citation indices, then return an ordered citation list containing the actually referenced items and source-opening metadata. Invalid output SHALL NOT be presented as verified provenance.

#### Scenario: Provider cites a nonexistent index or altered quote
- **WHEN** a response refers to an unavailable evidence index or a quote absent from that evidence
- **THEN** the server rejects the answer with a controlled citation-validation error

#### Scenario: Provider uses only two of four supplied chunks
- **WHEN** two selected evidence items support the accepted claims
- **THEN** the final markers and returned citations identify those two items in matching order and omit unused sources

### Requirement: Syntactic provenance is not claimed as semantic proof
The system SHALL evaluate answer support against labelled facts and negative questions in the release corpus. Passing quote or marker validation alone SHALL NOT be reported as proof that the quote entails the claim. A release SHALL have no unsupported factual claim in the reviewed answer acceptance set.

#### Scenario: A correct quote is attached to an incorrect claim
- **WHEN** a provider response passes substring validation but reverses the quote's meaning
- **THEN** semantic acceptance flags it as a failure and the release cannot pass solely because its citation number is valid

### Requirement: Answer failures are actionable and preserve isolation
The system SHALL distinguish HTTP 503 dependency or profile problems, HTTP 502 invalid provider citations and successful no-evidence or insufficient-evidence outcomes. The UI SHALL expose short actionable messages, clear stale answers and sources, and allow users to open only currently permitted citation sources.

#### Scenario: Generation fails after an earlier answer
- **WHEN** the provider is unavailable or returns invalid citations
- **THEN** the previous answer is not presented as the new result and the failure does not leak provider secrets or unauthorized evidence
