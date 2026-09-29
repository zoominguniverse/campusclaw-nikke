## Purpose

将既有教学材料、知识检索问答和管理操作组织为清晰的角色工作区内容，同时保持所有已实现的业务能力、只读限制与服务端授权结果不变。

## ADDED Requirements

### Requirement: Teacher material-management workspace
The teacher workspace SHALL organize existing subject selection, material listing, file upload, material preview, download, rename, reindex, and confirmed deletion operations into a labelled material-management view. The view MUST show upload and mutation controls only for a server-authorized teacher and only for the selected active subject, while preserving the existing API response feedback and confirmed deletion behavior.

#### Scenario: Teacher manages materials in an active assigned subject
- **WHEN** an authenticated teacher selects an active subject they are authorized to manage
- **THEN** the material-management view exposes the existing upload and allowed material-management controls together with their status feedback

#### Scenario: Teacher selects no subject or an archived subject
- **WHEN** an authenticated teacher has no selected subject or selects an archived subject
- **THEN** the workspace does not offer a usable upload control for that subject
- **AND** existing server-side authorization remains the authority for any direct API call

### Requirement: Student learning workspace
The student workspace SHALL present existing class-scoped material browsing, download, retrieval, evidence display, and grounded question-answering as read-only learning views. It MUST not render controls that initiate material upload, rename, reindex, deletion, subject administration, teacher assignment, or class-administrator management.

#### Scenario: Student uses material and knowledge views
- **WHEN** an authenticated student navigates among their available learning views
- **THEN** the student can browse class-authorized materials, request retrieval, and ask grounded questions with existing citation output
- **AND** no teacher or administrator mutation control is visible

### Requirement: Administration workspace preserves role partitions
The class-administrator workspace SHALL present the existing subject, teacher-assignment, subject-status, and material-reassignment controls; the super-administrator workspace SHALL present the existing class-administrator creation, activation, and class-grant controls. Each workspace MUST retain the existing result feedback and MUST not expose the other administrator role's controls unless the server-resolved role has that authority.

#### Scenario: Class administrator uses class governance view
- **WHEN** an authenticated class administrator opens its administration view
- **THEN** the view includes existing class-subject and teacher-assignment management functions
- **AND** it does not include super-administrator account-management controls

#### Scenario: Super administrator uses institution governance view
- **WHEN** an authenticated super administrator opens its administration view
- **THEN** the view includes existing class-administrator management functions

### Requirement: Workspace content is readable and communicates state
Workspace views SHALL use descriptive headings, grouped panels, responsive lists or tables, and accessible live status messages so that material, knowledge, and administrative outcomes remain understandable in the reference-aligned visual language. Material bodies and retrieval evidence MUST continue to be inserted as text rather than executable HTML.

#### Scenario: Material preview and knowledge evidence are rendered
- **WHEN** an authorized user opens a material preview or receives retrieval or answer evidence
- **THEN** the workspace renders the returned body and excerpts as text content in a readable, bounded region
- **AND** markup present in the returned content is not executed by the browser

### Requirement: Three-class role demonstration fixture
When explicit local demo seeding is enabled, the system SHALL idempotently provision three demonstration classes named 1 班, 2 班, and 3 班. Each class MUST contain the six active subjects 语文、数学、英语、物理、化学、生物 and enough class-scoped relationships to exercise the workspace for every role. The fixture MUST provision exactly one `super_admin`, three `class_admin` accounts with one distinct class grant each, 17 `teacher` accounts, and at least one `student` account in each class. It MUST assign a single mathematics teacher to both 1 班 and 2 班 and retain a distinct teacher account for every other class-subject assignment.

All fixture account identifiers MUST be unique lower-case pinyin renderings of Chinese personal-style names, rather than English-word or role-name identifiers. Before it writes fixture records, the system MUST validate a complete runtime credential mapping for the roster. Passwords MUST be memorable random phrases supplied from a local ignored environment file, hashed using the existing password mechanism, absent from committed source/configuration, and never returned by an API or rendered in the browser. Re-running the fixture MUST create missing records and relationships without duplicating existing ones or changing already-provisioned credentials.

#### Scenario: Complete local roster supports all roles
- **WHEN** local demo seeding is enabled with a complete valid credential mapping
- **THEN** the system provisions 1 班, 2 班, and 3 班 with their six active subjects
- **AND** it provisions one 教务管理员, three class-specific 班主任, 17 teachers, and a student in each class using pinyin personal-name account identifiers
- **AND** the same mathematics teacher is an assigned subject teacher for both 1 班 and 2 班

#### Scenario: Credential mapping is incomplete or invalid
- **WHEN** local demo seeding is enabled but the required credential mapping is absent, malformed, or does not cover the full roster
- **THEN** the system does not partially seed the demonstration roster
- **AND** it reports a configuration error without logging or exposing a plaintext password

#### Scenario: Fixture runs more than once
- **WHEN** the complete local demonstration fixture is run again against an already provisioned database
- **THEN** no duplicate user, membership, subject, class-administrator grant, or teacher-subject-assignment record is created
- **AND** existing fixture account password hashes are preserved

#### Scenario: Explicit legacy-fixture replacement is enabled
- **WHEN** local demo seeding is enabled with the explicit legacy-fixture purge setting
- **THEN** the system removes only the recognized old A 班/B 班 seed classes, their known legacy seed users, and records dependent on those seed classes or users
- **AND** it then leaves exactly 1 班、2 班、3 班 and the requested current demonstration roster
- **AND** the setting is disabled by default so an ordinary demo-seed run does not delete data
