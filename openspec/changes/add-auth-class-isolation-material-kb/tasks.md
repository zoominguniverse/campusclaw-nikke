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

- [x] 3.1 Implement account/password verification and the selected Flask session strategy with `user_id`, `role`, and `class_id` request context; revoke all prior active sessions when issuing a new one; use equivalent bcrypt work and generic throttled failures for unknown/known credentials; return top-level `username`, `role`, and `class_id` on successful login; verify valid teacher and student credentials establish the correct session context and invalid credentials establish none
- [x] 3.2 Configure `SECRET_KEY` from a server-only environment variable, secure cookie attributes, logout, and password/session redaction; verify missing `SECRET_KEY` fails explicitly and secrets are absent from frontend assets, logs, and responses
- [x] 3.3 Implement login and logout endpoints plus protected-page/API middleware; verify an unauthenticated page request returns a redirect to `/login`, an unauthenticated API request returns HTTP 401, and neither response leaks material title, body, or storage path
- [x] 3.4 Implement deny-by-default teacher/student authorization on every protected operation; verify a student direct-call to the upload endpoint returns HTTP 403 and creates no material, knowledge-base row, or stored upload file
- [x] 3.5 Add browser state-change protection appropriate to cookie authentication; verify the security tests do not accept forged state-changing requests and do not expose session credentials

## 4. Server-side class isolation

- [x] 4.1 Resolve class scope only from the authenticated user's server-side class; discard client class identifiers after route matching; verify changing, omitting, or falsifying class identifiers in URL, query, form, or JSON cannot expand or change the scope
- [x] 4.2 Add the server-derived `class_id` predicate to every material and knowledge-base read, list, count, search, sort, update, and delete query; verify a class-A user cannot obtain class-B data through pagination or enumeration and cannot mutate it
- [x] 4.3 Make cross-class detail and download responses indistinguishable from absent records with HTTP 404; verify neither response returns a title, body, file path, or storage key
- [x] 4.4 Add integration coverage for both seeded classes and direct HTTP requests; verify frontend button visibility is irrelevant because server-side filtering and authorization still reject crafted requests

## 5. Teacher upload and knowledge-base ingestion

- [x] 5.1 Implement `POST /api/classes/<class_id>/materials` as a teacher-only multipart endpoint using the session-derived class, with safe title/filename handling and bounded `.txt`/`.md` validation; verify an authorized teacher receives a material identity and a supplied different class identifier cannot change the destination scope
- [x] 5.2 Implement temporary-file staging, parse-to-plain-text, class-scoped final storage, and cleanup for invalid extension, empty/oversized file, parse failure, or transaction failure; verify each failure returns an explicit 400-class error with no orphan file or completed database row
- [x] 5.3 Insert the material metadata and knowledge-base body/chunks in one PostgreSQL transaction, retaining class and uploader associations; verify success is returned only when both records are durable and an indexing failure leaves no completed upload
- [x] 5.4 Implement class-scoped material list, detail reads, safe inline preview, and attachment download; verify the uploading teacher and a same-class student can preview and download the new material, while cross-class detail or download returns the same 404 response as an absent material without content
- [x] 5.5 Add direct-request tests for student upload, student update/replace, unauthenticated upload, malformed upload, cross-class upload, and cross-class listing; verify each returns the specified error and makes no unauthorized state change

## 6. Compose, health, and persistence acceptance

- [x] 6.1 Add Compose configuration for `web`, `api`, and `postgres` exposing only `5173:5173`; use internal API/database networking, named PostgreSQL/upload volumes, database health waiting, and schema initialization; verify `docker compose up --build` starts all three services
- [x] 6.2 Implement public same-origin `GET /health` through web port 5173, proxying the internal API health endpoint and returning HTTP 200 JSON such as `{"status":"ok"}` when Flask, PostgreSQL, and upload storage are usable; verify the endpoint never redirects to login
- [x] 6.3 Run a clean-environment Compose smoke test entirely through web port 5173, covering seed login, protected access, student 403, hidden cross-class detail/download 404, teacher upload, PostgreSQL knowledge-base write, same-class material-list visibility, and health; verify the documented flow passes from the host
- [x] 6.4 Stop and restart Compose without deleting PostgreSQL or upload volumes; verify preset users/classes and an uploaded material plus its knowledge-base record remain queryable
- [x] 6.5 Document `.env.example` setup, `DATABASE_URL`, PostgreSQL credentials, seed mode, login URL, same-origin API/health semantics, accepted upload types, material-list endpoint, and the single host port; verify the README commands match the actual Compose configuration

## 7. OpenSpec closeout

- [x] 7.1 Run `openspec validate --strict` for the change; verify validation succeeds and every implementation task remains unchecked until the corresponding work is complete
- [x] 7.2 Perform the final manual acceptance walkthrough; verify unauthenticated redirect/401, cross-class denial without leakage, student upload HTTP 403, successful teacher upload into the knowledge base, and post-upload same-class list visibility
