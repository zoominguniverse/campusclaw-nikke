# Spec Delta

## Purpose

让师生在授权班级和学科内通过原句、分散关键词或语义改写查找资料，优先看到简短而相关的原文摘录，并能展开证据、定位来源。明确相关性、索引兼容性和依赖故障边界，避免返回冗长内容、无关切片或越权信息。

## ADDED Requirements

### Requirement: Retrieval preserves authorized scope at every stage
The system SHALL derive class and subject scope from authenticated server identity for candidate selection, fusion, deduplication, evidence hydration and source opening. Students SHALL access their class subjects; teachers SHALL access only active assigned subjects. Client filters SHALL only narrow scope. Unauthorized hits, metadata, counts and diagnostic details SHALL NOT be disclosed.

#### Scenario: Caller forges another class or subject
- **WHEN** an authenticated caller submits a forged path, body or header class or an unauthorized subject
- **THEN** no stage returns evidence or metadata outside the effective scope and an unauthorized subject search returns an empty result

#### Scenario: User opens a source after permission revocation
- **WHEN** the source is removed or no longer permitted after retrieval
- **THEN** source opening rechecks permissions and returns the same 404 behavior as a nonexistent material

### Requirement: Keyword mode searches literal terms independently of models
The system SHALL retrieve both exact source phrases and queries containing multiple meaningful Chinese or mixed-language terms that occur separately in a chunk. Exact phrase matches SHALL rank ahead of term-only keyword matches. Matching SHALL account for term coverage and treat user wildcard characters literally. Keyword mode SHALL NOT invoke embedding or chat services.

#### Scenario: Meaningful keywords occur separately
- **WHEN** the source is `细胞是生物体结构和功能的基本单位。` and keyword query is `结构 功能 基本单位`
- **THEN** the source is returned although the whole query is not a contiguous substring

#### Scenario: Source phrase is submitted directly
- **WHEN** an authorized exact phrase occurs in one chunk and only individual terms occur in another
- **THEN** the exact phrase appears first in keyword results

#### Scenario: Query contains wildcard or only filler terms
- **WHEN** a query contains `%` or `_`, or consists only of recognized filler terms
- **THEN** wildcards do not match arbitrary text, filler-only input returns no evidence, and neither model is called

### Requirement: Vector mode uses compatible semantic embeddings
The system SHALL embed the submitted query with the configured compatible real model in semantic deployments and compare only eligible vectors in the authorized scope. Candidates below cosine similarity 0.35 SHALL be excluded. A semantic deployment SHALL support paraphrased queries according to the quality-evaluation contract rather than relying on shared characters.

#### Scenario: Query paraphrases a source statement
- **WHEN** `生物体由什么基本单位构成？` is submitted against the cellular-unit source in the fixed evaluation set
- **THEN** vector and hybrid retrieval return the labelled source within the top five results using the accepted real profile

#### Scenario: Available vectors belong to an incompatible profile
- **WHEN** authorized indexed material requires a rebuild for the active embedding profile
- **THEN** vector and hybrid return HTTP 503 with a sanitized reindex-required code instead of a normal no-evidence response or mixed-profile comparisons

### Requirement: Hybrid combines qualified independent rankings
The system SHALL default to hybrid mode and combine independently qualified keyword and vector rankings with reciprocal-rank fusion at k=60. A missing path SHALL contribute no score. Fusion rank SHALL NOT be interpreted as probability or used as the relevance threshold. Weak candidates SHALL NOT be added merely to fill the requested limit.

#### Scenario: Only one path finds a qualified chunk
- **WHEN** a chunk survives only one path's relevance criteria
- **THEN** it can appear with only that path's rank contribution

#### Scenario: All candidates are irrelevant
- **WHEN** neither path yields qualified evidence
- **THEN** the response is HTTP 200 with empty hits and `资料中未找到相关内容`

### Requirement: Redundant overlap does not dominate evidence
The system SHALL suppress redundant overlapping hits from the same material and generation while retaining distinct relevant evidence. Deduplication SHALL NOT combine separate source spans into invented text, and any grouped display SHALL retain valid individual provenance.

#### Scenario: A sentence is duplicated by overlapping windows
- **WHEN** several qualified chunks contain the same matched source sentence due to overlap
- **THEN** the result list shows one representative evidence item for that sentence rather than consuming multiple slots

#### Scenario: One material contains two different relevant statements
- **WHEN** the statements supply distinct useful evidence at different source positions
- **THEN** deduplication does not remove a statement merely because both belong to the same material

### Requirement: Hits expose concise query-related source excerpts
Each hit SHALL expose material and subject identity, chunk and generation identity, exact chunk offsets and basis, source spans, and an excerpt of at most 160 Unicode code points. The excerpt SHALL be an exact contiguous original-source substring around relevant evidence, with its own source offsets. Full chunk text SHALL remain separately available; omission indicators SHALL NOT be included in the quoted source text.

#### Scenario: Matching sentence occurs near the end of an 800-character chunk
- **WHEN** the user searches that sentence
- **THEN** the short excerpt includes the matching sentence or its relevant bounded portion rather than just the chunk beginning

#### Scenario: A very long sentence exceeds the excerpt limit
- **WHEN** a relevant sentence is longer than 160 code points
- **THEN** a bounded relevant original portion is returned, truncation is explicitly indicated and the complete evidence can be expanded

### Requirement: Users can open and verify evidence in the source
The UI SHALL display short excerpts, subject, title, chunk number and source location for retrieval hits and citations. Users SHALL be able to expand full evidence and open the source at highlighted spans. Source highlighting SHALL use original-source code-point offsets and render untrusted text safely. Current search scope and demo/reindex-required state SHALL remain visible in retrieval and question views.

#### Scenario: User opens an excerpt with emoji or preprocessing
- **WHEN** the user opens the evidence in its original material
- **THEN** the preview scrolls to and highlights the correct original text without treating preprocessed offsets as raw-source positions

#### Scenario: Previous selected subject narrows retrieval
- **WHEN** the user navigates from materials to retrieval or questions
- **THEN** the active subject filter is visible and can be changed within the caller's allowed subjects

### Requirement: Retrieval failures remain distinguishable from no evidence
The system SHALL return HTTP 400 for invalid input, HTTP 200 for genuine no evidence and HTTP 503 for unavailable semantic dependencies or incompatible indexes. Keyword retrieval SHALL remain available when only the embedding provider is unavailable. The UI SHALL clear stale results and explain the appropriate action without presenting an old result as a successful new search.

#### Scenario: Embedding provider is offline
- **WHEN** a valid keyword, vector or hybrid request is made while embedding is unavailable
- **THEN** keyword can return its literal hits and vector/hybrid return 503 without silent fallback or fabricated scores

#### Scenario: A new search fails after a successful search
- **WHEN** the request fails due to a dependency problem
- **THEN** prior results are cleared or explicitly separated from the failed request and the page does not show `资料中未找到相关内容` as the failure explanation
