## Context

See `proposal.md` for the motivation and scope. The repository is currently greenfield: it contains OpenSpec configuration but no application implementation, existing data model, API conventions, or runtime stack to preserve. The design therefore establishes a small deployable baseline that can support the requested security and material-ingestion contracts without implementing the out-of-scope AI and teaching workflows.

## Goals / Non-Goals

**Goals:**

- Provide a browser-friendly authenticated session for teacher and student accounts.
- Make authorization and class scoping server-side, deny-by-default, and reusable across page and API handlers.
- Keep account credentials and runtime secrets out of plaintext storage and client-visible artifacts.
- Make an authorized teacher upload produce one class-scoped material record and one class-scoped knowledge-base record as one externally successful operation.
- Provide a reproducible Docker Compose development/deployment baseline and readiness-aware `/health` behavior.
- Make the core contracts testable through HTTP integration tests and a Compose smoke test.

**Non-Goals:**

- Implementing retrieval-based question answering, a conversation assistant, assignment submission, or grading in this change.
- Adding SSO, third-party identity providers, production HA, multi-region failover, or autoscaling.
- Adding self-service registration, password reset, administrator UI, or cross-class management features.
- Treating frontend route guards or hidden controls as security mechanisms.

## Decisions

### 1. Use a frontend, Flask API, and PostgreSQL

Use a small browser frontend for login and protected pages, a Flask API for authentication, authorization, class isolation, material ingestion, and `/health`, and PostgreSQL for all persistent application data. The API modules remain separated into authentication, authorization, class scope, materials, knowledge-base ingestion, and runtime health. Use SQLAlchemy or an equivalent PostgreSQL persistence layer with parameterized queries and transaction support.

The Compose stack has three services; only the web service receives a host-port mapping:

| Service | Host port | Container port | Purpose |
| --- | ---: | ---: | --- |
| `web` | `5173` | `5173` | Login page, browser-facing protected pages, and same-origin `/api` and `/health` proxy |
| `api` | none | `8080` | Internal Flask API, authentication, upload/list APIs, and `GET /health` |
| `postgres` | none | `5432` | Internal PostgreSQL persistence for users, classes, materials, knowledge-base records, and seed data |

The browser calls only same-origin Web URLs; the web service proxies `/api` and `/health` to `api:8080`. The API connects to PostgreSQL through the Compose service name and `DATABASE_URL`. An equivalent frontend framework is acceptable, but PostgreSQL and the internal service boundaries remain required.

### 2. Use a modular monolith with a relational persistence boundary

Build the first runtime as a thin frontend service, one Flask API service with modules for authentication, authorization, classes, materials, and knowledge-base ingestion, and one PostgreSQL service. Keep persistence behind repositories so the material list and knowledge-base writer can share a transaction boundary.

This is preferred over separate services because the repository is greenfield and the requested operation is consistency-sensitive: a successful upload must be visible in both the material list and the knowledge-base path. A separate upload/indexing service would introduce partial-success states that are outside the requested contract.

The initial knowledge-base representation stores the material source, class ownership, uploader, content/indexing status, and searchable content or chunks in the relational persistence layer. A future vector index can be added behind the same knowledge-base writer without changing the authorization contract.

### 3. Use Flask sessions and hashed passwords

Use Flask's signed session cookie for the browser login flow. The session records `user_id`, `role`, and `class_id` needed for request context, is signed with `SECRET_KEY`, and is configured as `HttpOnly`, `SameSite=Lax`, and `Secure` in production. The application MUST resolve the current user, role, and class membership from PostgreSQL on protected requests rather than trusting a client-edited session payload; a logout operation clears or revokes the session. On successful login, the API locks the user record, revokes every existing active server-side session for that user, then persists and returns only the new session. Unknown accounts receive a bcrypt comparison against a dummy hash; all failed attempts use persistent, keyed rate-limit state and return the same generic 401 response. `POST /api/auth/login` returns top-level `username`, `role`, and `class_id` fields on success; `POST /api/auth/logout` revokes the session. The frontend redirects unauthenticated page requests while API middleware returns HTTP 401.

The signed-cookie session is preferred here because it keeps the greenfield Flask deployment small while supporting protected-page redirects. If an implementation uses an opaque server-side session table instead, it must preserve the same fields and behavior. Store only a `password_hash` using bcrypt or Argon2id through the selected Flask/Python library, and compare passwords with the library's safe verification function. Password fields, login payloads, seed passwords, and session credentials must not be written to logs. Required secrets such as `SECRET_KEY` are read only from server-side environment variables and missing values fail explicitly.

### 4. Centralize authorization and enforce server-side class filters

Every protected Flask route passes through authentication, role authorization, and class-scope resolution. A class scope is derived from the authenticated user and the server-side membership/teacher assignment; class identifiers in requests are discarded after route matching and never select a different scope.

Material and knowledge-base queries MUST include the authorized `class_id` predicate before records are returned. For a single-record read, the query must combine the material identifier and authorized class scope rather than loading a record first and filtering in the UI. Cross-class detail and download return the same HTTP 404 as absent material without content; teachers can upload only into their derived class, regardless of a supplied class path value.

Client class identifiers are non-authoritative selectors and are discarded after route matching. Every list, detail, download, upload, update, and delete operation derives its effective class only from the authenticated identity. Detail and download requests for records outside that derived class return the same 404 response as an absent record, preventing existence disclosure. Pagination, search, sorting, and count queries must apply the same class predicate.

### 5. Make material persistence and knowledge-base ingestion atomic

Use a multipart upload endpoint `POST /api/classes/<class_id>/materials`, accepting bounded `.txt` and `.md` files for the MVP. The request flow is: authenticate the session; require the teacher role; resolve and verify the teacher's class scope; validate extension, size, and non-empty content; stream content to a bounded temporary file; parse it to plain text; create the material metadata and display title; create the class-scoped knowledge-base record or chunks containing `body_text`; then commit only when both PostgreSQL records succeed.

Use a mounted Compose volume for uploaded content, with a final path such as `uploads/{class_id}/{uuid}_{safe_filename}`. Move the temporary file into its final location only after the PostgreSQL transaction commits, or remove it if validation, parsing, transaction, or indexing fails. The API must not return a successful upload response for an incomplete knowledge-base write, and invalid uploads must leave no orphan file or completed row. After success, `GET /api/classes/<class_id>/materials` reads the committed class-scoped material row, so the teacher and same-class students can immediately see the uploaded record; students remain read-only.

### 6. Define explicit HTTP boundaries

The initial API surface should include:

- `POST /api/auth/login` for account/password authentication.
- `POST /api/auth/logout` to revoke the current session.
- `POST /api/classes/<class_id>/materials` for teacher-only uploads.
- `GET /api/classes/<class_id>/materials` for class-scoped material records.
- `GET /api/classes/<class_id>/materials/<material_id>` for an authorized material's title and parsed text, used by the browser's inline preview.
- `GET /api/classes/<class_id>/materials/<material_id>/download` for an authorized attachment download using the stored safe original filename.
- `GET /health` for readiness-aware health reporting.

The exact framework and response envelope may follow the implementation stack, but status semantics are fixed: unauthenticated API access returns 401, authenticated but unauthorized roles return 403, cross-class detail/download and absent detail/download return an identical 404, and successful material creation is not returned until persistence and knowledge-base ingestion both complete.

The browser material list provides an inline preview control for both teacher and student users. It requests the existing class-scoped material-detail operation and assigns returned title and body through DOM text APIs, so material text is not interpreted as HTML.

The browser also provides a download link for each listed material. The API applies the same authenticated class predicate as detail reads before resolving its stored relative path under the upload root. It returns an attachment with `Content-Disposition` and the stored safe original filename, never a raw storage path; preconfigured materials without a file on disk are emitted from their class-scoped knowledge-base text as attachments.

### 7. Use Docker Compose with three services and PostgreSQL persistence

Docker Compose starts `web`, `api`, and `postgres`, exposing only `5173:5173` from `web`. The web service proxies same-origin `/api` and `/health` requests to the internal API; PostgreSQL and uploaded files use named volumes, so `docker compose down -v` is the intentional data reset. Compose waits for PostgreSQL health before API initialization. The public health endpoint is `http://localhost:5173/health`. The image entrypoint runs migrations/schema setup and enables seed data only under explicit development configuration.

## Risks / Trade-offs

- **[Risk]** Cookie-based sessions can be exposed to cross-site state-changing requests. → Use `HttpOnly`, `Secure` in production, an explicit `SameSite` policy, and CSRF protection for state-changing browser requests.
- **[Risk]** Upload content and database records can become inconsistent if a process fails mid-write. → Stage file writes, use a database transaction for metadata and knowledge-base records, clean up on rollback, and only return success after both sides are durable.
- **[Risk]** A future endpoint may accidentally omit a class predicate. → Centralize scope resolution, make repositories require a scope object, and add cross-class integration tests for every material read/list/write path.
- **[Risk]** Local development secrets may be committed accidentally. → Provide an environment example containing placeholders only, ignore real `.env` files, fail explicitly when required secrets are absent, and scan the repository and frontend responses in tests.
- **[Risk]** Large or unsupported uploads can exhaust application resources. → Stream uploads to bounded temporary storage and define implementation-level size/type limits before enabling production deployment; this does not alter the authorization contract.

## Migration Plan

This is a greenfield change, so no existing user or material migration is required. The implementation should:

1. Add the web/API/PostgreSQL Compose services, a single web host-port mapping, environment template, schema bootstrap, and proxied `/health` endpoint.
2. Add PostgreSQL migrations, user, role, class-membership, material, knowledge-base, and session persistence.
3. Add the six core data structures and seeded development fixtures only when explicitly enabled by environment configuration; production startup must not silently create demo accounts.
4. Add `.txt`/`.md` validation, parse-to-text ingestion, cleanup on failure, and class-scoped list/read integration tests.
5. Run integration and Compose smoke tests before treating the runtime as deployable.

If a deployment must be rolled back, stop the new Compose stack and restore the previous application image and database snapshot. Do not delete user or material data as part of rollback.

## Open Questions

None. Framework, file-type limits, and future vector-index choices can be selected during implementation without changing the behavior contracts above.
