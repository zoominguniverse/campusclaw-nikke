## Purpose

将已上传的班级材料转换为带来源位置和索引状态的可检索切片，同时始终保留未经改写的材料正文供追溯与展示。

## ADDED Requirements

### Requirement: Material text is indexed as traceable chunks
The system SHALL retain the existing material source text and create ordered, class-scoped chunks for an accepted material before reporting its initial index as ready. Each chunk SHALL retain its material, knowledge-entry, class, sequence number, chunk text, offsets within the text used for chunking, indexing status, and creation time. A chunk SHALL be eligible for retrieval only when its indexing status is ready.

#### Scenario: Teacher upload produces retrievable chunks
- **WHEN** an authorized teacher uploads a valid material to the teacher's server-derived class
- **THEN** the original material body remains available unchanged and the system creates ordered, class-scoped chunks with provenance for that material

#### Scenario: Chunk embedding fails
- **WHEN** creating an embedding for one or more chunks fails during indexing
- **THEN** the material and original body remain available, each failed chunk is marked failed, no incomplete vector is made searchable, and the response does not describe the material as fully indexed

### Requirement: Chunking strategies preserve defined boundaries
The system SHALL support `auto`, `custom`, and `hierarchy` chunking strategies for initial indexing and reindexing. `auto` SHALL use an approximately 800-character maximum with approximately 80-character overlap and prefer paragraph, line, then sentence boundaries before forced splitting. `custom` SHALL validate a maximum length of 100 through 2000 characters and overlap of 0 through 50 percent. `hierarchy` SHALL retain Markdown headings through level three in their chapter chunks and split oversized chapters using the automatic-window behavior.

#### Scenario: No strategy is supplied
- **WHEN** an authorized teacher uploads or reindexes material without a chunking strategy
- **THEN** the system applies the `auto` strategy

#### Scenario: Custom strategy is outside accepted bounds
- **WHEN** an authorized teacher supplies a custom maximum length or overlap outside its allowed range
- **THEN** the system rejects the request with HTTP 400 and does not replace an existing ready index

#### Scenario: Heading chapter exceeds the chunk limit
- **WHEN** hierarchy chunking encounters a Markdown chapter longer than the automatic-window maximum
- **THEN** the system splits that chapter into ordered chunks while retaining the applicable heading in each resulting chunk

### Requirement: Optional preprocessing does not alter source material
The system SHALL allow configured custom-strategy preprocessing to remove URLs, remove email addresses, or collapse consecutive whitespace only from the text supplied to chunking and embedding. The system SHALL retain the original `body_text` unchanged and SHALL identify generated offsets as positions in the preprocessed text whenever preprocessing was applied.

#### Scenario: Whitespace collapsing is requested
- **WHEN** an authorized teacher enables whitespace collapsing for custom chunking
- **THEN** chunk text and offsets are derived from collapsed text while the material preview continues to return the original body text

### Requirement: Teachers can safely rebuild a material index
The system SHALL permit only an authorized teacher to rebuild indexing for a material in the teacher's server-derived class. A rebuild SHALL use the newly supplied strategy, replace the material's previous chunks and vectors as one logical index generation, and prevent stale, partial, or orphaned chunks from being returned by retrieval.

#### Scenario: Teacher rebuilds an existing material
- **WHEN** an authorized teacher requests a rebuild with a different valid strategy
- **THEN** retrieval returns only chunks from the completed replacement generation after the rebuild succeeds

#### Scenario: Student requests a rebuild
- **WHEN** an authenticated student directly calls a material reindex operation
- **THEN** the system returns HTTP 403 and leaves existing chunks and vectors unchanged

#### Scenario: Rebuild fails before completion
- **WHEN** a rebuild fails while generating or persisting its replacement index
- **THEN** the system does not expose a mixed old-and-new index generation or orphaned vectors for that material
