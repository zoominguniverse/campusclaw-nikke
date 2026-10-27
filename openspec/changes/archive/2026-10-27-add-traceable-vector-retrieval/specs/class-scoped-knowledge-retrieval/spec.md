## Purpose

让班级成员以关键词、语义或混合方式检索本班材料，并获得可回溯原文且不泄露其他班级信息的结果。

## ADDED Requirements

### Requirement: Users can retrieve traceable class-scoped chunks
The system SHALL allow authenticated teachers and students to retrieve ready chunks from their server-derived class using `keyword`, `vector`, or `hybrid` mode, with `hybrid` as the default. Each returned hit SHALL include the material title and identifier, chunk sequence number, chunk offsets, and an excerpt sourced from the stored chunk text.

#### Scenario: Same-class member retrieves a matching phrase
- **WHEN** an authenticated class member submits a non-empty query matching a ready chunk in the member's class
- **THEN** the response contains only traceable hits from that class and each hit identifies its material and chunk position

#### Scenario: No mode is supplied
- **WHEN** an authenticated class member submits a valid query without a retrieval mode
- **THEN** the system executes hybrid retrieval

### Requirement: Retrieval modes have distinct evidence behavior
The system SHALL perform keyword retrieval without an embedding-provider call, SHALL perform vector retrieval by embedding only the submitted query and excluding candidates below 0.35 cosine similarity, and SHALL perform hybrid retrieval by independently filtering both paths before applying reciprocal-rank fusion with `k = 60`. A chunk absent from one hybrid path SHALL receive no contribution from that path.

#### Scenario: Keyword mode finds literal source terms
- **WHEN** an authenticated class member uses keyword mode with words present in a ready chunk
- **THEN** the system returns keyword-ranked matching chunks without invoking the embedding provider

#### Scenario: Vector mode finds a semantic match
- **WHEN** an authenticated class member uses vector mode with a paraphrased query whose candidate passes the similarity threshold
- **THEN** the system returns the vector-ranked chunk with its stored provenance

#### Scenario: Hybrid mode has one contributing path
- **WHEN** a chunk survives filtering in only one retrieval path
- **THEN** the chunk can appear in the hybrid result with an RRF contribution from only that path

### Requirement: Retrieval never trusts client class selection
The system SHALL derive retrieval scope exclusively from the authenticated server-side request context. It SHALL apply that class scope to keyword candidate selection, vector candidate selection, and retrieval of chunk text after candidate selection; class identifiers supplied in paths, query strings, headers, or JSON SHALL not expand or change the scope.

#### Scenario: Client changes a retrieval class identifier
- **WHEN** a class-A user submits a retrieval request containing class B's identifier
- **THEN** the system searches only class A's ready chunks and returns no class-B metadata, excerpt, count, or vector-derived information

#### Scenario: Cross-class-only query is submitted
- **WHEN** a class-A user queries text that exists only in class B
- **THEN** the system returns HTTP 200 with an empty hit list and no indication that class-B material exists

### Requirement: Retrieval reports invalid, empty, and unavailable states honestly
The system SHALL reject blank retrieval queries with HTTP 400. When all candidates are filtered out, it SHALL return HTTP 200 with an empty hit list and the message `资料中未找到相关内容`. If vector storage or the embedding dependency is unavailable, keyword retrieval SHALL remain available while vector and hybrid requests SHALL return HTTP 503 without fabricated scores or hits.

#### Scenario: Query has no supporting chunk
- **WHEN** a valid retrieval query has no eligible chunk after the selected mode's filtering
- **THEN** the response is HTTP 200 with an empty hit list and `资料中未找到相关内容`

#### Scenario: Vector dependency is unavailable
- **WHEN** the embedding or vector retrieval dependency is unavailable
- **THEN** a keyword request can still return keyword hits while vector and hybrid requests return HTTP 503 without a synthetic result
