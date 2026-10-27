## Purpose

基于当前提问检索本班材料后才生成简短回答，并让回答中的引用标记与可验证的切片出处严格对应。

## ADDED Requirements

### Requirement: Questions are answered only from retrieved class evidence
The system SHALL answer an authenticated user's latest question by first running hybrid retrieval within the user's server-derived class and selecting at most four eligible chunks. It SHALL call the chat provider only when at least one chunk is selected. The provider input SHALL be assembled by the server and contain only the latest question, optional bounded prior conversation, and each selected chunk's material title, chunk number, and text.

#### Scenario: Question has class-scoped evidence
- **WHEN** an authenticated class member asks a question with one or more eligible class-scoped chunks
- **THEN** the system calls the chat provider with no more than four selected chunks and returns a concise answer grounded in those chunks

#### Scenario: Question has no evidence
- **WHEN** hybrid retrieval returns no eligible chunks for the latest question
- **THEN** the system returns `资料中未找到相关内容` with an empty `citations` list and does not call the chat provider

### Requirement: Generated answers expose ordered, verifiable citations
The system SHALL return a citation list for an evidence-backed answer and require answer markers such as `[1]` and `[2]` to refer to that list in the same order. Each citation SHALL expose the matching material title and identifier, chunk number, offsets, and stored chunk excerpt needed to trace the evidence.

#### Scenario: Answer uses multiple retrieved chunks
- **WHEN** the chat provider returns an answer supported by multiple selected chunks
- **THEN** the response's `[n]` markers and `citations[n-1]` entries refer to the same ordered chunk sources

#### Scenario: Provider output lacks a valid citation reference
- **WHEN** the chat provider output cannot be reconciled with the selected citation list
- **THEN** the system does not return an answer with misleading provenance

### Requirement: Clients cannot inject privileged answer context
The system SHALL discard client-supplied system messages and SHALL not expose embedding vectors, raw vector-store objects, or chunks from another class to the chat provider. The chat provider SHALL not be used as a separate retrieval channel.

#### Scenario: Client submits a forged system message
- **WHEN** an authenticated user includes a system-role message in an answer request
- **THEN** the system omits that message from provider input and applies only server-controlled answer instructions

#### Scenario: Prior conversation is included
- **WHEN** the request includes permitted prior conversation for a follow-up question
- **THEN** the system appends only the bounded allowed history after the server-selected evidence and preserves the current user's class scope
