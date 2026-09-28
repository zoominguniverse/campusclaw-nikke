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

The three Compose services and host/container port mappings are fixed for this course project:

| Service | Host port | Container port | Purpose |
| --- | ---: | ---: | --- |
| `frontend` | `5173` | `5173` | Login page and browser-facing protected pages |
| `api` | `8080` | `8080` | Flask HTTP API, authentication, upload/list APIs, and `GET /health` |
| `postgres` | `5432` | `5432` | PostgreSQL persistence for users, classes, materials, knowledge-base records, and seed data |

The frontend calls the API through the documented API base URL. The API connects to PostgreSQL through the Compose service name and `DATABASE_URL`; the host mapping of `5432` is provided for course inspection and local database tools. An equivalent frontend framework is acceptable, but the three externally documented ports and PostgreSQL requirement are not optional.

### 2. Use a modular monolith with a relational persistence boundary

Build the first runtime as a thin frontend service, one Flask API service with modules for authentication, authorization, classes, materials, and knowledge-base ingestion, and one PostgreSQL service. Keep persistence behind repositories so the material list and knowledge-base writer can share a transaction boundary.

This is preferred over separate services because the repository is greenfield and the requested operation is consistency-sensitive: a successful upload must be visible in both the material list and the knowledge-base path. A separate upload/indexing service would introduce partial-success states that are outside the requested contract.

The initial knowledge-base representation stores the material source, class ownership, uploader, content/indexing status, and searchable content or chunks in the relational persistence layer. A future vector index can be added behind the same knowledge-base writer without changing the authorization contract.

### 3. Use Flask sessions and hashed passwords

Use Flask's signed session cookie for the browser login flow. The session records `user_id`, `role`, and `class_id` needed for request context, is signed with `SECRET_KEY`, and is configured as `HttpOnly`, `SameSite=Lax`, and `Secure` in production. The application MUST resolve the current user, role, and class membership from PostgreSQL on protected requests rather than trusting a client-edited session payload; a logout operation clears or revokes the session. On successful login, the API locks the user record, revokes every existing active server-side session for that user, then persists and returns only the new session. `POST /api/auth/login` returns top-level `username`, `role`, and `class_id` fields on success; `POST /api/auth/logout` revokes the session. The frontend redirects unauthenticated page requests while API middleware returns HTTP 401.

The signed-cookie session is preferred here because it keeps the greenfield Flask deployment small while supporting protected-page redirects. If an implementation uses an opaque server-side session table instead, it must preserve the same fields and behavior. Store only a `password_hash` using bcrypt or Argon2id through the selected Flask/Python library, and compare passwords with the library's safe verification function. Password fields, login payloads, seed passwords, and session credentials must not be written to logs. Required secrets such as `SECRET_KEY` are read only from server-side environment variables and missing values fail explicitly.

### 4. Centralize authorization and enforce server-side class filters

Every protected Flask route passes through authentication, role authorization, and class-scope resolution. A class scope is derived from the authenticated user and the server-side membership/teacher assignment; request parameters are only selectors, never proof of access.

Material and knowledge-base queries MUST include the authorized `class_id` predicate before records are returned. For a single-record read, the query must combine the material identifier and authorized class scope rather than loading a record first and filtering in the UI. Cross-class access returns HTTP 403 without material content. Teacher upload additionally requires the teacher role and management rights for the target class.

For this change, the documented response for an authenticated cross-class single-record or list request is HTTP 403. This is preferred over frontend-only filtering because direct HTTP clients must receive the same denial behavior as the browser. It also prevents a future endpoint from accidentally bypassing a UI guard. Pagination, search, sorting, and count queries must apply the same class predicate.

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

The exact framework and response envelope may follow the implementation stack, but status semantics are fixed: unauthenticated API access returns 401, authenticated but unauthorized role or class access returns 403, and successful material creation is not returned until persistence and knowledge-base ingestion both complete.

The browser material list provides an inline preview control for both teacher and student users. It requests the existing class-scoped material-detail operation and assigns returned title and body through DOM text APIs, so material text is not interpreted as HTML.

The browser also provides a download link for each listed material. The API applies the same authenticated class predicate as detail reads before resolving its stored relative path under the upload root. It returns an attachment with `Content-Disposition` and the stored safe original filename, never a raw storage path; preconfigured materials without a file on disk are emitted from their class-scoped knowledge-base text as attachments.

### 7. Use Docker Compose with three services and PostgreSQL persistence

Docker Compose should start `frontend`, `api`, and `postgres` services with the fixed mappings `5173:5173`, `8080:8080`, and `5432:5432`. The PostgreSQL service uses a persistent volume such as `./postgres-data:/var/lib/postgresql/data`; the API mounts `./uploads:/app/uploads`; and the frontend uses the API base URL to call port 8080. Compose must wait for PostgreSQL health before starting API initialization. The API healthcheck calls `http://127.0.0.1:8080/health`; the public endpoint returns `{"status":"ok"}` with HTTP 200 only when Flask, PostgreSQL connectivity, and required upload storage are usable, otherwise a non-healthy status. The image entrypoint runs migrations/schema setup and enables seed data only under explicit development configuration. `.env.example` lists `SECRET_KEY`, `DATABASE_URL`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and frontend API URL placeholders, while real `.env` values remain outside source control. README documents copying the example environment, `docker compose up --build`, `http://localhost:5173/login`, `http://localhost:8080/health`, and the PostgreSQL port for local inspection. Development fixtures create classes A/B; `teacher_a` and `teacher_b` as their respective class teachers; `student_a1`, `student_a2`, `student_b1`, and `student_b2` as read-only students; distinguishable A/B materials; and the six core structures (classes, users, lectures/materials, assignments, assistants, skills).

## Risks / Trade-offs

- **[Risk]** Cookie-based sessions can be exposed to cross-site state-changing requests. → Use `HttpOnly`, `Secure` in production, an explicit `SameSite` policy, and CSRF protection for state-changing browser requests.
- **[Risk]** Upload content and database records can become inconsistent if a process fails mid-write. → Stage file writes, use a database transaction for metadata and knowledge-base records, clean up on rollback, and only return success after both sides are durable.
- **[Risk]** A future endpoint may accidentally omit a class predicate. → Centralize scope resolution, make repositories require a scope object, and add cross-class integration tests for every material read/list/write path.
- **[Risk]** Local development secrets may be committed accidentally. → Provide an environment example containing placeholders only, ignore real `.env` files, fail explicitly when required secrets are absent, and scan the repository and frontend responses in tests.
- **[Risk]** Large or unsupported uploads can exhaust application resources. → Stream uploads to bounded temporary storage and define implementation-level size/type limits before enabling production deployment; this does not alter the authorization contract.

## Migration Plan

This is a greenfield change, so no existing user or material migration is required. The implementation should:

1. Add the frontend/API/PostgreSQL Compose services, fixed port mappings, environment template, schema bootstrap, and `/health` endpoint.
2. Add PostgreSQL migrations, user, role, class-membership, material, knowledge-base, and session persistence.
3. Add the six core data structures and seeded development fixtures only when explicitly enabled by environment configuration; production startup must not silently create demo accounts.
4. Add `.txt`/`.md` validation, parse-to-text ingestion, cleanup on failure, and class-scoped list/read integration tests.
5. Run integration and Compose smoke tests before treating the runtime as deployable.

If a deployment must be rolled back, stop the new Compose stack and restore the previous application image and database snapshot. Do not delete user or material data as part of rollback.

## Open Questions

None. Framework, file-type limits, and future vector-index choices can be selected during implementation without changing the behavior contracts above.
