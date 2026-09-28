## Purpose

为 CampusClaw 建立可靠的身份、登录态和角色授权边界，使教师与学生能够安全使用受保护功能，并让服务端而非前端承担访问控制责任。

## ADDED Requirements

### Requirement: Account password login

The system SHALL allow both teacher and student accounts to authenticate with an account identifier and password, and SHALL establish an authenticated login state only after the credentials are verified.

#### Scenario: Teacher logs in successfully

- **WHEN** the preconfigured `teacher_a` account submits its valid password
- **THEN** the system establishes an authenticated state and returns a success response containing top-level `username`, `role`, and `class_id` fields for the server-resolved teacher identity and class A scope

#### Scenario: Student logs in successfully

- **WHEN** `student_a1` or `student_b1` submits its valid password
- **THEN** the system establishes an authenticated state containing the server-resolved user identity, student role, and the corresponding A or B class scope

#### Scenario: Invalid credentials are rejected

- **WHEN** a user submits an unknown account or an incorrect password
- **THEN** the system refuses authentication, does not establish an authenticated state, and does not disclose the stored hash or whether only the account or password was incorrect

#### Scenario: New login invalidates old sessions

- **WHEN** a user successfully logs in while that user has one or more active sessions
- **THEN** the system revokes every prior active session for that user before issuing the new session, and any request using an old session receives HTTP 401

### Requirement: Development seed accounts, classes, and core data

The system SHALL provide an explicit development seed mode that creates class A and class B; `teacher_a` for A; `teacher_b` for B; `student_a1` and `student_a2` for A; and `student_b1` and `student_b2` for B, so teacher upload, student read-only access, role authorization, and class isolation can be demonstrated without manually creating accounts. The persisted data model SHALL also establish the six course core structures: classes, users, lectures or teaching materials, assignments, assistants, and skills. Seed mode MUST be disabled or explicitly controlled for production deployments.

#### Scenario: Development seed data is enabled

- **WHEN** an operator starts the application with development seed mode enabled and supplies the seed configuration
- **THEN** the system creates one teacher and two students in each class with usable login credentials and correct role/class associations; `teacher_a` can manage A only, `teacher_b` can manage B only, and all four students are read-only; at least one distinguishable sample material exists for each class (for example, titles containing `A 班` and `B 班`); the lectures/materials, assignments, assistants, and skills structures also exist, even if the latter three only contain placeholder data

#### Scenario: Production starts without seed mode

- **WHEN** the application starts without explicit development seed mode
- **THEN** the system does not silently create demo accounts or demo class data

#### Scenario: Seed identities are usable and scoped

- **WHEN** the seeded users sign in with the documented development credentials
- **THEN** `teacher_a`, `student_a1`, and `student_a2` resolve to class A; `teacher_b`, `student_b1`, and `student_b2` resolve to class B; and none of these identities can select a different class by changing request parameters

### Requirement: Protected page and API access

The system SHALL require authentication for protected pages and APIs. An unauthenticated browser request to a protected page SHALL be directed to the login page, while an unauthenticated API request SHALL be rejected with an authentication error.

#### Scenario: Unauthenticated browser access is redirected

- **WHEN** a user who has no authenticated state requests a protected page
- **THEN** the system redirects the browser to the login page and preserves enough context to return to the originally requested page after login

#### Scenario: Unauthenticated API access is rejected

- **WHEN** a request without a valid authenticated state calls a protected API
- **THEN** the system rejects the request with HTTP 401 and does not perform the protected operation

#### Scenario: Protected response does not leak business data

- **WHEN** an unauthenticated request targets a protected page or API
- **THEN** the page response redirects without material titles, content, or storage paths, and the API response returns HTTP 401 without those fields

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
