## 1. PostgreSQL runtime and schema evolution

- [ ] 1.1 Select an extension-capable PostgreSQL 16 image and update Compose/bootstrap configuration to create and verify `pgvector` and `pg_trgm`; verify a clean Compose database reports both extensions installed and the API fails clearly if either prerequisite is unavailable.
- [ ] 1.2 Add server-only embedding/chat provider configuration, fixed embedding-dimension validation, dependency manifests, and documentation placeholders without exposing credentials through frontend assets or API responses; verify missing required provider configuration and a dimension mismatch fail safely.
- [ ] 1.3 Add a versioned PostgreSQL schema-upgrade path for chunk generations, `knowledge_chunks`, indexing status/metadata, vector storage, and class/status/provenance indexes; verify applying the upgrade to a database with existing `knowledge_entries` preserves all source material rows.
- [ ] 1.4 Add the pgvector cosine and trigram GIN indexes required by the retrieval queries; verify query plans or PostgreSQL integration assertions confirm the indexes exist and retrieval remains constrained by class and ready status.

## 2. Chunking and index generation

- [ ] 2.1 Implement pure auto, custom, and hierarchy chunking functions with character offsets and deterministic sequence numbering; verify unit tests cover 800/80 default windows, forced splits, custom 100–2000 and 0–50% validation, Markdown heading retention, and oversized chapters.
- [ ] 2.2 Implement optional URL removal, email removal, and whitespace-collapse preprocessing as a derived working text only; verify tests prove original `knowledge_entries.body_text` is unchanged and preprocessing-origin offsets are labeled correctly.
- [ ] 2.3 Define narrow embedding-client and indexing-service interfaces that validate returned vector dimensions, assign per-chunk state, and prevent incomplete vectors from becoming searchable; verify fake-provider tests cover successful, failed, and dimension-mismatched embeddings.
- [ ] 2.4 Integrate initial indexing with the existing authorized upload path while retaining the original material/body on indexing failure and returning an honest index state; verify upload integration tests cover ready chunks and a failed chunk with no searchable vector.
- [ ] 2.5 Implement teacher-only material reindexing as an isolated replacement generation that retains the old ready generation until the replacement is complete; verify integration tests show no mixed generation after success or failure and no orphan vectors.
- [ ] 2.6 Add a bounded backfill command or bootstrap migration for pre-existing knowledge entries using the auto strategy; verify it is idempotent, records failures, and never deletes source material.

## 3. Class-scoped retrieval service

- [ ] 3.1 Implement PostgreSQL keyword retrieval over ready chunks using trigram matching and server-derived class scope, with no embedding-client call; verify literal Chinese phrase retrieval and a mocked embedding client proving it is unused.
- [ ] 3.2 Implement pgvector cosine retrieval that embeds only the query, filters by server-derived class and ready state before ranking, and rejects candidates below 0.35 similarity; verify PostgreSQL integration tests cover a passing semantic hit and a below-threshold exclusion.
- [ ] 3.3 Implement hybrid retrieval by independently filtering keyword and vector candidates before RRF fusion with `k=60`; verify unit tests cover shared candidates, candidates present in one path only, deterministic rank order, and no raw-score addition.
- [ ] 3.4 Hydrate all retrieval DTOs from class-filtered PostgreSQL chunk/material records and expose material title/id, chunk number, offsets, and chunk-text excerpt only; verify responses contain no vectors or provider-specific raw records.
- [ ] 3.5 Define retrieval error translation for blank input (400), no evidence (200 with empty `hits` and `资料中未找到相关内容`), and vector/provider outage (503 for vector and hybrid while keyword remains usable); verify contract tests cover every status and body shape.

## 4. Protected retrieval and reindex API

- [ ] 4.1 Add authenticated retrieval and teacher-only reindex routes under the established `/api/classes/<class_id>` namespace, immediately replacing route/query/body class identifiers with the authenticated effective class; verify direct calls from students and forged class identifiers meet the 403/no-leakage contracts.
- [ ] 4.2 Apply effective class scope in keyword candidate queries, vector candidate queries, and post-ranking chunk/material hydration; verify a class-A query containing only class-B text returns HTTP 200 with empty hits and no B-class metadata or counts.
- [ ] 4.3 Add request/response validation and JSON contracts for strategy settings, retrieval mode/limit, hit provenance, and index status; verify malformed bodies and out-of-range custom strategy settings return 400 without replacing a ready index.

## 5. Evidence-grounded answer service

- [ ] 5.1 Implement an answer orchestrator that runs only hybrid retrieval on the latest question, selects at most four eligible hits, and bypasses the chat client entirely when no evidence exists; verify the no-hit test returns `资料中未找到相关内容`, empty `citations`, and zero chat-client calls.
- [ ] 5.2 Implement server-owned chat request construction containing only selected material titles, chunk numbers/text, the latest question, and bounded validated prior user/assistant history; verify tests reject client system messages and demonstrate that vectors, other-class chunks, and database handles are absent.
- [ ] 5.3 Validate generated `[n]` markers against the server-selected citation order and return a controlled generation failure for malformed/unreconcilable provider output; verify multi-citation tests match each marker to `citations[n-1]` and invalid output cannot produce misleading provenance.
- [ ] 5.4 Add the authenticated question endpoint using the same server-derived class scope and error envelope as retrieval; verify only evidence-backed requests call the fake chat provider and cross-class-only questions behave as no evidence.

## 6. Protected browser workflow and documentation

- [ ] 6.1 Extend the protected materials UI with mode selection, non-empty search submission, result rendering, and traceable source controls using only the new same-origin API DTOs; verify excerpts and titles are rendered as text and source controls use existing class-scoped material preview behavior.
- [ ] 6.2 Add the ask interaction and citation list UI, preserving `[n]`/citation order and the deterministic no-evidence state; verify frontend tests cover successful cited output, empty citations, and no exposure of vectors or provider configuration.
- [ ] 6.3 Update README and environment documentation with PostgreSQL extension/image prerequisites, provider environment variable semantics, migration/backfill order, reindexing behavior, supported chunk strategies, retrieval modes, and the no-evidence/503 behavior; verify documented Compose startup and verification commands match the implementation.

## 7. Integration verification and OpenSpec closeout

- [ ] 7.1 Add PostgreSQL integration coverage for extension bootstrap, pgvector thresholding, trigram keyword search, RRF hybrid behavior, class predicates at all query stages, and atomic generation replacement; verify the suite runs against the Compose or dedicated PostgreSQL target rather than SQLite.
- [ ] 7.2 Run the existing SQLite-compatible unit suite with fake provider clients and repair regressions unrelated to PostgreSQL-specific search; verify the full unit command succeeds.
- [ ] 7.3 Run a clean Compose acceptance walkthrough through the browser-facing port covering teacher upload/indexing, same-class student retrieval, keyword-without-embedding behavior, vector/hybrid failure semantics, reindex authorization, cross-class no leakage, no-evidence answer gating, and citation order; verify all expected status codes and response bodies.
- [ ] 7.4 Run `openspec validate add-traceable-vector-retrieval --strict` and resolve every validation error; verify the final change status reports all required planning artifacts complete before implementation begins.
