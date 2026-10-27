## Why

CampusClaw currently stores class-scoped teaching material but cannot locate supporting passages or answer a learner's question from those materials. Adding retrieval without preserving the existing server-side class boundary would make cross-class disclosure and unsupported model answers likely; this change introduces evidence-backed retrieval before later conversational features expand the product.

## What Changes

- Add PostgreSQL-backed, traceable knowledge indexing: split each material's existing `knowledge_entries.body_text` into versioned chunks, retain chunk text and offsets in PostgreSQL, and create a `pgvector` embedding for each successfully indexed chunk.
- Add automatic, configurable, and Markdown-heading chunking strategies, plus teacher-only reindexing that safely replaces an existing material's chunks and embeddings while retaining the source material.
- Add `keyword`, `vector`, and default `hybrid` retrieval modes. Keyword retrieval uses PostgreSQL `pg_trgm` indexes and never calls the embedding provider; vector retrieval uses `pgvector` cosine similarity; hybrid retrieval applies reciprocal-rank fusion with `k = 60`.
- Add class-scoped retrieval results with material provenance, chunk position, text excerpt, and stable citation data. Every query path derives `class_id` from the authenticated request context and applies it at database retrieval and chunk hydration boundaries.
- Add an evidence-grounded question endpoint that runs class-scoped hybrid retrieval for the latest user question, calls a server-only chat provider only when up to four supporting chunks exist, and returns ordered citations matching `[1]`, `[2]`, and subsequent answer markers.
- Return a deterministic no-evidence response without calling the chat provider when retrieval has no usable chunks; reject blank queries, and expose vector-service outages rather than inventing results.
- Add PostgreSQL extension, dependency, configuration, migration/bootstrap, API, frontend-facing contract, and test coverage needed for the feature. No MySQL, Qdrant, orchestration framework, reranking stage, or streaming answer API is introduced.

## Capabilities

### New Capabilities

- `traceable-knowledge-indexing`: chunk existing material text, track indexing state and provenance, and persist server-generated embeddings in PostgreSQL.
- `class-scoped-knowledge-retrieval`: provide keyword, vector, and hybrid class-scoped retrieval with traceable results and failure semantics.
- `evidence-grounded-knowledge-answering`: generate concise answers exclusively from retrieved class chunks and return ordered citations.

### Modified Capabilities

None. The root `openspec/specs/` inventory is empty; the completed baseline change's ingestion and class-isolation delta specs have not yet been synced into main specs. This change therefore introduces retrieval-specific capabilities without redefining those unarchived baseline paths.

## Impact

- Affected backend modules: application configuration, SQLAlchemy models/repositories, material ingestion, new indexing/retrieval/answer services and API blueprints, plus authentication-derived class scope reuse.
- Affected runtime: PostgreSQL image and startup/bootstrap must support the `pgvector` and `pg_trgm` extensions; server-only embedding and chat-provider configuration is added without exposing credentials through the frontend.
- Affected API surface: material upload gains indexing behavior and reindex support; new protected retrieval and question-answering endpoints return chunk provenance, citations, and deterministic error/no-evidence responses.
- Affected tests: existing SQLite unit fixtures need provider/database abstractions or focused PostgreSQL integration coverage for extension-specific search, alongside cross-class, no-evidence, provider-failure, citation-order, and role-authorization tests.
