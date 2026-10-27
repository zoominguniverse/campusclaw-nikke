# traceable-knowledge-indexing Specification

## Purpose

将已上传的班级材料转换为带来源位置和索引状态的可检索切片，同时始终保留未经改写的材料正文供追溯与展示。

## Requirements

### Requirement: Material text is indexed as traceable chunks
The system SHALL retain the existing material source text and create ordered, class-scoped chunks for an accepted material before reporting its initial index as ready. Each chunk SHALL retain its material, knowledge-entry, class, sequence number, chunk text, offsets within the text used for chunking, indexing status, and creation time. A chunk SHALL be eligible for retrieval only when its indexing status is ready.

#### Scenario: Teacher upload produces retrievable chunks
- **WHEN** an authorized teacher uploads a valid material to the teacher's server-derived class
- **THEN** the original material body remains available unchanged and the system creates ordered, class-scoped chunks with provenance for that material

#### Scenario: Chunk embedding fails
- **WHEN** creating an embedding for one or more chunks fails during indexing
- **THEN** the material and original body remain available, each failed chunk is marked failed, no incomplete vector is made searchable, and the response does not describe the material as fully indexed

### Requirement: Chunking strategies preserve defined boundaries
The system SHALL support `auto`, `custom` and `hierarchy` for upload and reindexing. Auto SHALL default to an 800-code-point window with 80-code-point overlap, preferring paragraph, line and sentence boundaries. Custom SHALL accept lengths 100–2000 and overlap 0–50 percent. Hierarchy SHALL preserve Markdown headings through level three as separate context and split oversized chapters without fabricating source text or offsets.

#### Scenario: No strategy is supplied
- **WHEN** an authorized teacher uploads or reindexes material without a chunking strategy
- **THEN** the system applies the `auto` strategy

#### Scenario: Custom strategy is outside accepted bounds
- **WHEN** an authorized teacher supplies a custom maximum length or overlap outside its allowed range
- **THEN** the system rejects the request with HTTP 400 and does not replace an existing ready index

#### Scenario: Heading chapter exceeds the chunk limit
- **WHEN** hierarchy chunking encounters a Markdown chapter longer than the automatic-window maximum
- **THEN** the system splits the chapter into ordered source-exact chunks with the applicable heading retained as separate context rather than inserted at an unrelated source offset

### Requirement: Optional preprocessing does not alter source material
The system SHALL allow custom preprocessing to remove URLs, email addresses or repeated whitespace only from working text used for chunking and embedding. Original `body_text` SHALL remain unchanged. Chunk offsets SHALL identify their working-text basis; ordered source-span mappings SHALL locate surviving content in the original body for excerpts and highlighting.

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

### Requirement: Indexed text preserves source coverage
The system SHALL preserve the accepted original body and uploaded file. Without explicit removal preprocessing, every non-whitespace source character SHALL occur in at least one chunk. Markdown preambles SHALL remain indexed, and inserted heading context SHALL NOT be represented as source text at an unrelated offset.

#### Scenario: Markdown contains text before its first heading
- **WHEN** a teacher indexes a document containing a preamble and Markdown chapters
- **THEN** the preamble and all chapter bodies are searchable and heading context is distinguishable from the exact chunk body

#### Scenario: A chapter is longer than the configured window
- **WHEN** a chapter is split into overlapping child chunks
- **THEN** each child's stored body corresponds to its declared text range and the chapter title remains available as separate context

### Requirement: Chunk offsets are exact and explicitly based
The system SHALL use zero-based, end-exclusive Unicode code-point offsets. For each chunk, slicing its declared source or working text at its offsets SHALL equal its stored body. Preprocessed chunks SHALL retain ordered mappings to original source spans, and mappings SHALL exclude synthesized context.

#### Scenario: Chunk edges contain whitespace or emoji
- **WHEN** chunking trims edge whitespace or handles non-BMP characters
- **THEN** both endpoints are adjusted correctly and source highlighting selects exactly the corresponding characters

#### Scenario: URLs and repeated whitespace are removed
- **WHEN** configured preprocessing changes the working text
- **THEN** the original body is unchanged, the chunk is labelled preprocessed, and its surviving content can be located through valid original source spans

### Requirement: Teachers can configure reproducible chunking
The system SHALL support auto, custom and hierarchy for upload and reindex. Auto SHALL retain the 800-character/80-character default and paragraph-before-line-before-sentence boundary preference. Custom SHALL accept lengths 100–2000 and overlap 0–50 percent. The complete normalized options and preprocessing version SHALL be recorded and shown to authorized teachers.

#### Scenario: Teacher changes custom options
- **WHEN** an authorized teacher selects length, overlap, separators and preprocessing in the UI
- **THEN** upload and reindex apply those options, show them on the resulting generation and leave existing indexes unchanged when validation fails

#### Scenario: Teacher inspects prospective chunking
- **WHEN** the teacher requests a chunk preview for permitted material and valid options
- **THEN** the system shows sample chunks, boundaries and total count without calling providers or replacing the active index

### Requirement: Semantic indexes have a compatible model identity
The system SHALL record embedding provider, model revision, dimensions and text-processing versions for every new generation. Query vectors SHALL only be compared with compatible embeddings. Model configuration changes SHALL NOT silently reuse old vectors, including equal-dimension vectors from a different model. Missing compatibility SHALL be reported as reindex-required.

#### Scenario: Real model has different dimensions
- **WHEN** a teacher rebuilds a 64-dimensional demo index using a configured real model with another supported dimension
- **THEN** new embeddings are stored with their identity and dimension, existing sources remain intact and the old vectors remain recoverable

#### Scenario: Model name changes without dimension change
- **WHEN** the configured model identity differs from the current generation
- **THEN** semantic retrieval does not compare these incompatible vectors and reports reindex-required rather than ordinary no-match

### Requirement: Demo providers are explicitly identified
The system SHALL identify deterministic embedding and chat as demo capabilities in authorized UI state. A deployment claiming real semantic retrieval or passing semantic release acceptance SHALL use a configured real provider. Provider outputs SHALL be validated for expected length, finite numeric values and nonzero magnitude before use.

#### Scenario: User opens retrieval in demo mode
- **WHEN** deterministic embeddings are active
- **THEN** the page indicates that semantic understanding is unavailable in the demo and no semantic acceptance success is claimed

#### Scenario: Provider returns malformed or zero vectors
- **WHEN** an embedding response has incorrect dimensions, nonnumeric/nonfinite elements or zero magnitude
- **THEN** the generation fails without exposing invalid searchable vectors and the authorized caller receives a sanitized failure reason

### Requirement: Reindex cutover is atomic and scope protected
The system SHALL restrict reindex to teachers assigned to the material's effective class and subject. A material SHALL have at most one current generation. A replacement SHALL become current only after all required chunks, mappings and embeddings are ready. Failed or competing rebuilds SHALL retain the previous complete generation without exposing a partial replacement.

#### Scenario: One embedding request fails during rebuild
- **WHEN** the replacement generation cannot complete
- **THEN** the prior current generation remains searchable, the latest attempt is failed and retry is available to the authorized teacher

#### Scenario: Two rebuilds target the same material
- **WHEN** concurrent requests attempt to publish replacement generations
- **THEN** at most one generation is current and the other request is safely serialized or receives a conflict response

#### Scenario: Student or unassigned teacher requests rebuild
- **WHEN** a caller lacks the required teacher assignment
- **THEN** no chunk, vector, generation or source is modified and the existing authorization contract applies

### Requirement: Index state is honestly exposed
The system SHALL distinguish source-save success, searchable-generation state, latest indexing attempt state and reindex-required state. Initial failed indexing SHALL preserve the source and expose failure. HTTP success alone SHALL NOT cause the UI to claim indexing succeeded. Errors SHALL omit credentials, provider payloads and unauthorized metadata.

#### Scenario: Upload saves material but embedding fails
- **WHEN** the original file is accepted and indexing returns failed
- **THEN** the page states that the material was saved but indexing failed, displays its retry action and does not show index-ready

#### Scenario: Rebuild fails while the old index is ready
- **WHEN** the latest attempt fails but a complete prior generation exists
- **THEN** material metadata shows both the usable previous index and the failed attempt rather than hiding the failure behind ready

### Requirement: Backfill is bounded resumable and model aware
The system SHALL select missing, failed or explicitly requested incompatible indexes before applying batch limits, use stable continuation, isolate per-material failures and report completed, failed and skipped accurately. A force-rebuild mode SHALL include already-indexed materials. Repeating or resuming the operation SHALL preserve sources and avoid duplicate current generations.

#### Scenario: More than one hundred materials need indexes
- **WHEN** multiple batches are processed, including previously indexed entries and a failed material
- **THEN** later eligible materials are reached, progress resumes from stable state and one failure does not roll back previously completed materials

#### Scenario: Indexing returns a failure result instead of raising
- **WHEN** the generation builder returns status failed
- **THEN** the backfill failed count increases and the material is not counted as completed

#### Scenario: Operator migrates all demo embeddings
- **WHEN** force-rebuild targets a new real model profile
- **THEN** existing current demo generations are included, replacements are published only when complete and failures remain individually retryable
