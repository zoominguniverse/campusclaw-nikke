# user-authentication-and-authorization Specification

## Purpose

为 CampusClaw 建立可靠的身份、登录态和角色授权边界，使教师与学生能够安全使用受保护功能，并让服务端而非前端承担访问控制责任。

## Requirements

### Requirement: Account password login

The system SHALL allow configured super administrator, class administrator, teacher and student accounts to authenticate with an account identifier and password, and SHALL issue an opaque Bearer credential pair only after verifying the credentials.

#### Scenario: Teacher logs in successfully

- **WHEN** a configured teacher account submits its valid password
- **THEN** the system returns an opaque access/refresh token pair and a `user` object containing the server-resolved `username`, `role`, and `class_id`, as specified by `authorization-only-api-authentication`

#### Scenario: Student logs in successfully

- **WHEN** a configured student account submits its valid password
- **THEN** the system returns the Bearer token pair and a `user` object containing the server-resolved student identity and current class scope

#### Scenario: Invalid credentials are rejected

- **WHEN** a user submits an unknown account or an incorrect password
- **THEN** the system refuses authentication, does not establish an authenticated state, and does not disclose the stored hash or whether only the account or password was incorrect

#### Scenario: New login invalidates old sessions

- **WHEN** a user successfully logs in while that user has one or more active sessions
- **THEN** the system revokes every prior active session for that user before issuing the new session, and any request using an old session receives HTTP 401

### Requirement: Login enumeration resistance and throttling

The system SHALL perform an equivalent bcrypt verification for unknown and known account identifiers, rate-limit repeated failed authentication attempts, and return the same generic HTTP 401 response for invalid or throttled login attempts.

#### Scenario: Unknown and known accounts fail uniformly

- **WHEN** an unknown account or a known account with a wrong password submits a login request
- **THEN** the system performs a bcrypt verification in either case, creates no session, and returns the same generic HTTP 401 response

#### Scenario: Repeated failures are throttled

- **WHEN** failed login attempts for an account identifier exceed the configured limit within the configured window
- **THEN** the system continues returning the same generic HTTP 401 response and does not create a session

### Requirement: Development seed accounts, classes, and core data

The system SHALL provide explicit development seeding using the three-class, four-role roster defined by `role-oriented-teaching-workspace`, with credentials supplied only through server-side runtime configuration. It SHALL retain the six course core structures: classes, users, teaching materials, assignments, assistants and skills. Seed mode MUST be disabled or explicitly controlled for production deployments.

#### Scenario: Development seed data is enabled

- **WHEN** an operator starts the application with development seed mode enabled and supplies the seed configuration
- **THEN** the system provisions 1 班, 2 班 and 3 班, six subjects per class, one super administrator, three class administrators, 17 teachers and one student per class with the defined teacher assignments and usable runtime-configured credentials; the six core structures exist and sample material ownership remains class-scoped

#### Scenario: Production starts without seed mode

- **WHEN** the application starts without explicit development seed mode
- **THEN** the system does not silently create demo accounts or demo class data

#### Scenario: Seed identities are usable and scoped

- **WHEN** seeded users sign in with their privately configured development credentials
- **THEN** each user resolves to their current server-side role, memberships and assignments, including the shared mathematics teacher in 1 班 and 2 班; client parameters cannot enlarge that authorization

### Requirement: Protected page and API access

The system SHALL require a valid Bearer identity before exposing protected workspace data or executing protected APIs. Workspace routes SHALL serve a data-free shell whose client verifies identity through the authenticated API. An unauthenticated client SHALL navigate to login; an unauthenticated API request SHALL return HTTP 401 with `WWW-Authenticate: Bearer`.

#### Scenario: Unauthenticated browser access is redirected

- **WHEN** a user who has no authenticated state requests a protected page
- **THEN** the shell's client navigates to `/login` without rendering protected identity, navigation or business data

#### Scenario: Unauthenticated API access is rejected

- **WHEN** a request without a valid authenticated state calls a protected API
- **THEN** the system rejects the request with HTTP 401 and does not perform the protected operation

#### Scenario: Protected response does not leak business data

- **WHEN** an unauthenticated request targets a protected page or API
- **THEN** the page response contains only an unauthenticated shell and the client navigates to login, while the API returns HTTP 401; neither response exposes material titles, content or storage paths

### Requirement: Server-side role authorization

The system SHALL enforce role permissions on the server for every protected operation, regardless of whether the client hides or shows a corresponding control.

#### Scenario: Student calls a teacher-only operation

- **WHEN** an authenticated student directly calls a teacher-only operation
- **THEN** the system rejects the request with HTTP 403 and performs no state-changing work

#### Scenario: Teacher accesses teacher operations

- **WHEN** an authenticated teacher calls an operation allowed for teachers
- **THEN** the system evaluates the request under the teacher role and permits it when all other authorization conditions pass

### Requirement: Password and secret handling

The system SHALL store passwords only as a secure one-way password hash, SHALL never persist or log plaintext passwords, and SHALL load application secrets only from server-side environment configuration.

#### Scenario: Password storage is inspected

- **WHEN** an account is created or its password is changed
- **THEN** the persisted credential is a password hash and the plaintext password is not stored

#### Scenario: Secret is unavailable to the client

- **WHEN** the application serves frontend assets or API responses
- **THEN** server-side secrets are absent from the response and are not embedded in frontend code

#### Scenario: Required session secret is missing

- **WHEN** the application starts without its required server-side session secret
- **THEN** startup or the dependent session operation fails explicitly and the system does not use a hard-coded or insecure fallback

#### Scenario: Seed credentials are persisted safely

- **WHEN** development seed credentials are provided through environment configuration
- **THEN** the system stores them in a `password_hash`-equivalent field using a recognizable bcrypt or Argon2-family one-way hash and does not write the supplied plaintext values to the database, repository, or logs

#### Scenario: Wrong password does not create a session

- **WHEN** a seeded account submits a wrong password
- **THEN** password verification fails without disclosing credential details and no authenticated session is created
