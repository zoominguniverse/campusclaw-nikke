## Context

See `proposal.md` for motivation. The current Flask modular monolith uses Flask-SQLAlchemy with PostgreSQL in Compose, `db.create_all()`-based schema bootstrap, class scope derived from `g.current_user`, and `knowledge_entries.body_text` as the original parsed material. Material uploads currently commit a `Material` and `KnowledgeEntry` atomically from the API perspective, while the existing test suite uses SQLite fixtures. There is no retrieval provider, vector type, migration runner, or main-spec inventory yet.

## Goals / Non-Goals

**Goals:**

- Keep source text, chunks, embeddings, and class predicates in one PostgreSQL deployment while preserving the current source-material APIs.
- Make every retrieval result and generated citation recoverable to a PostgreSQL chunk and its material.
- Reuse the current authentication and class-scope mechanism at every new endpoint and repository boundary.
- Isolate provider calls behind narrow embedding and chat interfaces so they can be mocked in unit tests and configured only in the API container.
- Introduce an explicit, repeatable PostgreSQL schema-upgrade path for extensions and index tables rather than relying on `create_all()` to alter a deployed database.

**Non-Goals:**

- Migrating to an external vector database, adding a generic RAG framework, reranking, streaming output, or tool/agent execution.
- Treating SQLite as a substitute for PostgreSQL vector or trigram semantics.
- Automatically reindexing every material merely because chunking configuration changes.

## Decisions

### 1. Keep chunks and embeddings in PostgreSQL

Add PostgreSQL `pgvector` and `pg_trgm` extensions through a versioned database upgrade/bootstrap step. Use a PostgreSQL image that provides the extensions and fail API startup clearly if extensions cannot be created. Store one `knowledge_chunks` row per current index generation with its text, provenance, ready/failed/building state, strategy metadata, preprocessing metadata, and a nullable fixed-dimension `vector` embedding. Add a `vector` cosine-distance index appropriate to the selected pgvector index method and a `GIN ... gin_trgm_ops` index over chunk text; combine both with selective `class_id`, entry, and status indexes.

This keeps source, vector, and citation joins transactionally close and eliminates dual-store consistency concerns. An external Qdrant service was rejected because it adds a second availability and cleanup boundary without a user requirement. PostgreSQL's default full-text tokenization was rejected for Chinese literal/phrase retrieval; trigram search offers predictable matching for Chinese source text. The exact embedding dimension is an environment-controlled, server-side compatibility contract and must be validated against provider responses before persistence.

### 2. Build an explicit index-generation lifecycle

Represent reindexing as a new generation for one `knowledge_entry`. Persist generated chunks in a non-searchable state, embed them, then atomically make the generation current and retire the preceding generation. On failure, remove or retire the incomplete generation and retain the previous current generation where one exists. Initial upload keeps the source material if indexing fails but reports its indexing state honestly.

This lifecycle prevents a retriever from mixing old and newly cut chunks. Deleting and recreating the only chunks in place was rejected because retrieval could observe a partially rebuilt index; asynchronous background jobs were rejected because the requested contract does not require a job queue and would complicate completion status.

### 3. Separate pure chunking from provider and persistence services

Implement chunking as deterministic, side-effect-free strategy functions (`auto`, `custom`, `hierarchy`) that return text, position, and preprocessing-origin metadata. Put embedding requests behind an embedding client; make the index service orchestrate chunking, provider calls, and generation persistence. The upload and reindex handlers invoke that service only after authorization and source-text validation.

This makes boundary cases testable without a provider or PostgreSQL. Preprocessing produces a derived working string only; its offset basis is carried in the chunk metadata so callers cannot mistake it for an offset in the uploaded file.

### 4. Use independent retrieval paths and hydrate evidence from chunks

The retrieval service receives an effective class scope, query, mode, and limit. Keyword mode runs only the PostgreSQL trigram query over ready chunks. Vector mode calls the embedding client for the query, runs a PostgreSQL cosine search with `class_id` and ready-state filtering, and rejects candidates below 0.35 similarity. Hybrid starts both paths independently, applies each path's filter before combining ranks through RRF with `k=60`, then hydrates all result fields from the class-filtered chunk rows.

The service returns typed hits, including provenance and excerpt, rather than raw ORM or provider objects. This ensures vector data is never sent to the browser or chat provider and provides a second class predicate during hydration. A score-weighted fusion alternative was rejected because trigram and cosine scores are not directly comparable.

### 5. Keep API paths compatible with existing class-scoped resources

Add protected JSON endpoints under the existing `/api/classes/<class_id>` namespace: a retrieval operation, a teacher-only material reindex operation, and a question operation. Handlers accept the path component for route consistency but immediately replace it with `g.current_user.class_id`, as material handlers already do. Define response DTOs for hits and citations rather than exposing ORM models. Blank input is a 400, unavailable vector/provider dependencies are 503 for vector-dependent modes, and no evidence is a successful 200 with the fixed no-evidence text.

The protected materials page will consume those DTOs to offer mode selection, search results, an ask action, and source links/previews while rendering excerpts and answers as text. A global `/api/ask` route was rejected because using the existing class-scoped namespace makes the caller's scope visible in the route convention without making it authoritative.

### 6. Gate chat generation and validate citations server-side

The answer service calls the retrieval service only in hybrid mode and takes the first four qualified hits. It constructs a server-owned chat request from those chunk records, the latest user question, and a bounded, validated subset of prior user/assistant messages; it discards all client system-role content. The provider receives no database handles, vector values, arbitrary class filter, or ability to retrieve additional context. The server validates that returned bracket markers map to selected citations; malformed or unsupported provider output is surfaced as an answer-generation failure rather than returned with false provenance.

Calling the model before retrieval, or allowing it to call tools directly, was rejected because both permit answers without class-scoped evidence.

### 7. Split test layers by database capability

Keep deterministic chunker, RRF, response-mapping, provider-gating, and authorization tests fast through fake provider clients and repository interfaces. Add PostgreSQL integration coverage through the Compose stack or a dedicated PostgreSQL test target for extension creation, trigram search, pgvector threshold filtering, vector/hybrid 503 failures, atomic generation replacement, and indexes. Do not assert pgvector/trigram behavior against the current SQLite fixture.

## Risks / Trade-offs

- **[Risk]** The configured embedding dimension and provider output can diverge. → Validate dimension at client boundary, reject mismatches, mark affected chunks failed, and document the required environment value.
- **[Risk]** pgvector and trigram indexes add storage and ingestion latency. → Index only ready current-generation chunks, bound chunking inputs, and use database-side class/status predicates before ranking.
- **[Risk]** A PostgreSQL extension may be unavailable in a local image or deployment. → Use an extension-capable image, run a startup health/upgrade check, and make vector-dependent routes fail explicitly instead of silently degrading hybrid semantics.
- **[Risk]** Model output can omit or misuse citations. → Validate markers against the selected ordered hits and return a controlled generation failure when reconciliation is impossible.
- **[Risk]** Existing material upload response timing may increase because indexing occurs during ingestion. → Surface index state clearly; no background queue is introduced in this scope.

## Migration Plan

1. Add the extension-capable PostgreSQL runtime, server-only provider configuration, Python dependencies, and a versioned schema upgrade that creates extensions, chunk/generation structures, vector/trigram indexes, and status defaults without touching existing source bodies.
2. Deploy the API with retrieval disabled until the upgrade completes; run a bounded backfill that creates automatic-strategy generations for existing `knowledge_entries`, recording failures without deleting source materials.
3. Enable the retrieval, reindex, and question endpoints plus the protected-page controls after a successful PostgreSQL integration check.
4. Roll back API code by disabling the new endpoints and controls; preserve source material and chunk tables. Rollback does not delete existing materials, embeddings, or successful generations. If required, restore the database snapshot taken before the schema upgrade.

## Open Questions

None. Provider base URLs, model names, timeouts, and maximum history length are deployment configuration values that can be selected during implementation without altering these contracts.
