## Purpose

让可追溯的知识库检索与问答在学科权限范围内运行，向学生覆盖全班学科，向任课教师限制为已分配学科。

## ADDED Requirements

### Requirement: Retrieval applies effective class and subject scope before ranking
The system SHALL derive the effective class and authorized subject set from the authenticated server-side identity before keyword, vector, and hybrid candidate selection. Students SHALL receive candidates from all subjects in their effective class; teachers SHALL receive candidates only from their active teacher-subject assignments. An optional requested subject filter SHALL only narrow that effective scope.

#### Scenario: Student retrieves evidence from two class subjects
- **WHEN** a student submits a valid unfiltered retrieval query matching ready chunks in two subjects of the student's class
- **THEN** eligible hits from both subjects can appear, with no hit from another class

#### Scenario: Teacher queries another teacher's subject
- **WHEN** a teacher queries text that exists only in a same-class subject not assigned to that teacher
- **THEN** the response is HTTP 200 with no matching hit and no indication that the subject, material, chunk, or vector exists

### Requirement: All retrieval modes preserve subject isolation
The system SHALL apply the same authorized class-and-subject predicate to PostgreSQL keyword candidates, vector candidates before similarity thresholding, hybrid RRF inputs, and final chunk/material metadata lookup. Keyword mode SHALL not call the embedding provider; vector and hybrid behavior, including the 0.35 similarity threshold and RRF k=60, SHALL remain unchanged within the narrowed scope.

#### Scenario: Cross-subject candidate exists only in vector storage
- **WHEN** an unassigned subject contains a high-similarity vector for a teacher query
- **THEN** vector and hybrid retrieval omit that candidate before returning scores or provenance

#### Scenario: Student uses keyword retrieval
- **WHEN** a student uses keyword mode for a phrase in an own-class subject
- **THEN** the result is limited to own-class subject chunks and no embedding-provider request occurs

### Requirement: Evidence and answers identify their subject
Every authorized retrieval hit and question-answer citation SHALL include the subject identifier and display name together with existing material and chunk provenance. The answer operation SHALL supply the chat model only the already-authorized top four hybrid chunks and their subject/material provenance; it SHALL not allow the model to run another retrieval or access unassigned subject content.

#### Scenario: Answer cites evidence from more than one subject
- **WHEN** a student's answer is grounded in chunks from multiple own-class subjects
- **THEN** each numbered citation contains the matching subject and material provenance in the same order as the answer's citation list

#### Scenario: No authorized subject has evidence
- **WHEN** a teacher or student question has no ready chunk in the caller's effective subject scope
- **THEN** the system returns `资料中未找到相关内容` with empty citations and does not call the chat model
