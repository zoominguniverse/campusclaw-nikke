## 1. Repository, documentation, and runtime skeleton

- [x] 1.1 Add or update the root README with the three-line course framing (value, representative scenario, and non-goals), plus the Compose, login, and health-check quick start; verify a new developer can find the startup and acceptance flow without reading implementation code
- [x] 1.2 Add the Flask application entry point, dependency manifest, package/module skeleton, and local run command; verify the dependency installation succeeds and the application imports without business-feature implementation errors
- [x] 1.3 Add frontend and API Dockerfiles or equivalent images, `docker-compose.yml`, `.env.example`, and ignore rules for real `.env`, PostgreSQL data, and upload data; verify `docker compose config` succeeds with placeholder configuration and no real secret is committed

## 2. Persistence model and preconfigured data

- [x] 2.1 Add PostgreSQL migrations/schema for classes, users, roles, memberships/teacher assignments, sessions, materials/lectures, knowledge-base records or chunks, upload metadata, assignments, assistants, and skills; verify a clean PostgreSQL database initializes with the six course core structures present
- [x] 2.2 Add explicit development seed mode for class A and class B, `teacher_a` in A, `student_a1` in A, and `student_b1` in B; add distinguishable sample material titles containing `A 班` and `B 班`; verify a database query shows the expected memberships and both sample titles
- [x] 2.3 Persist every account credential in a `password_hash`-equivalent field using bcrypt or Argon2-family hashes, with seed passwords supplied only through server environment configuration; verify no plaintext password appears in PostgreSQL, logs, repository files, or API responses
- [x] 2.4 Make production startup opt out of seed mode unless explicitly enabled; verify a clean non-development startup does not silently create demo accounts or demo class/material data
- [x] 2.5 Add parameterized repositories/services for users, sessions, class scope, materials, and knowledge-base records; verify repository tests cannot return a class-owned record outside the supplied server-side class scope
- [x] 2.6 Expand development seed data to two teachers and four students across classes A/B, with passwords supplied only through environment variables; verify both teachers can log in, each teacher is scoped to the own class, and all four students remain read-only

## 3. Session, password, and role authorization

- [x] 3.1 Implement account/password verification and the selected Flask session strategy with `user_id`, `role`, and `class_id` request context; verify valid teacher and student credentials establish the correct session context and invalid credentials establish none
- [x] 3.2 Configure `SECRET_KEY` from a server-only environment variable, secure cookie attributes, logout, and password/session redaction; verify missing `SECRET_KEY` fails explicitly and secrets are absent from frontend assets, logs, and responses
- [x] 3.3 Implement login and logout endpoints plus protected-page/API middleware; verify an unauthenticated page request returns a redirect to `/login`, an unauthenticated API request returns HTTP 401, and neither response leaks material title, body, or storage path
- [x] 3.4 Implement deny-by-default teacher/student authorization on every protected operation; verify a student direct-call to the upload endpoint returns HTTP 403 and creates no material, knowledge-base row, or stored upload file
- [x] 3.5 Add browser state-change protection appropriate to cookie authentication; verify the security tests do not accept forged state-changing requests and do not expose session credentials

## 4. Server-side class isolation

- [x] 4.1 Resolve class scope only from the authenticated user's server-side membership or teacher assignment; verify changing, omitting, or falsifying class identifiers in URL, query, form, or JSON cannot expand the scope
- [x] 4.2 Add the server-derived `class_id` predicate to every material and knowledge-base read, list, count, search, sort, update, and delete query; verify a class-A user cannot obtain class-B data through pagination or enumeration and cannot mutate it
- [x] 4.3 Fix the cross-class status contract as HTTP 403 for authenticated unauthorized requests and document it in README/API notes; verify a cross-class request returns no B-class title, body, file path, or storage key
- [x] 4.4 Add integration coverage for both seeded classes and direct HTTP requests; verify frontend button visibility is irrelevant because server-side filtering and authorization still reject crafted requests

## 5. Teacher upload and knowledge-base ingestion

- [x] 5.1 Implement `POST /api/classes/<class_id>/materials` as a teacher-only multipart endpoint using the session-derived class, with safe title/filename handling and bounded `.txt`/`.md` validation; verify an authorized teacher receives a material identity and a teacher targeting another class receives HTTP 403
- [x] 5.2 Implement temporary-file staging, parse-to-plain-text, class-scoped final storage, and cleanup for invalid extension, empty/oversized file, parse failure, or transaction failure; verify each failure returns an explicit 400-class error with no orphan file or completed database row
- [x] 5.3 Insert the material metadata and knowledge-base body/chunks in one PostgreSQL transaction, retaining class and uploader associations; verify success is returned only when both records are durable and an indexing failure leaves no completed upload
- [x] 5.4 Implement `GET /api/classes/<class_id>/materials` from the committed database rows with server-side class filtering; verify the uploading teacher sees the new title after upload and a same-class student sees it read-only
- [x] 5.5 Add direct-request tests for student upload, student update/replace, unauthenticated upload, malformed upload, cross-class upload, and cross-class listing; verify each returns the specified error and makes no unauthorized state change

## 6. Compose, health, and persistence acceptance

- [x] 6.1 Add Compose configuration for `frontend`, `api`, and `postgres` with fixed mappings `5173:5173`, `8080:8080`, and `5432:5432`; mount PostgreSQL data and API upload volumes, load environment variables, wait for database health, and initialize the schema without manual in-container setup; verify `docker compose up --build` starts all three services
- [x] 6.2 Implement public API `GET /health` on port 8080 returning HTTP 200 JSON such as `{"status":"ok"}` when Flask, PostgreSQL, and upload storage are usable, and a non-200 response when a required dependency is unavailable; verify the endpoint never redirects to login
- [x] 6.3 Run a clean-environment Compose smoke test through the frontend on port 5173 and API on port 8080, covering seed login, protected access, student 403, cross-class 403, teacher upload, PostgreSQL knowledge-base write, same-class material-list visibility, and health; verify the documented flow passes from the host
- [x] 6.4 Stop and restart Compose without deleting PostgreSQL or upload volumes; verify preset users/classes and an uploaded material plus its knowledge-base record remain queryable
- [x] 6.5 Document `.env.example` setup, `DATABASE_URL`, PostgreSQL credentials, seed mode, frontend login URL, API status semantics, accepted upload types, material-list endpoint, `GET /health`, and all three ports; verify the README commands match the actual Compose configuration

## 7. OpenSpec closeout

- [x] 7.1 Run `openspec validate --strict` for the change; verify validation succeeds and every implementation task remains unchecked until the corresponding work is complete
- [x] 7.2 Perform the final manual acceptance walkthrough; verify unauthenticated redirect/401, cross-class denial without leakage, student upload HTTP 403, successful teacher upload into the knowledge base, and post-upload same-class list visibility
