## Purpose

为学科材料提供按任课教师授权的写管理边界，同时让学生继续只读访问其本班的全部学科资料。

## ADDED Requirements

### Requirement: Teachers manage only assigned subject materials
The system SHALL allow a teacher to list, preview, download, upload, rename, rebuild, and delete materials only for active subjects to which that teacher is explicitly assigned in the teacher's effective class. A client-supplied class or subject identifier SHALL be treated only as a requested narrowing value and SHALL never expand the teacher's server-derived authorization.

#### Scenario: Assigned teacher manages own subject material
- **WHEN** a teacher assigned to class A mathematics uploads, reindexes, renames, or deletes a mathematics material in class A
- **THEN** the system permits the operation and retains the material's class and subject provenance

#### Scenario: Teacher targets another subject in the same class
- **WHEN** a class-A mathematics teacher calls a material endpoint for class A language material or submits language's subject identifier during upload
- **THEN** the system returns an authorization-safe denial and does not disclose that subject's material title, file, chunks, vectors, or counts

### Requirement: Students read all subjects in their own class
The system SHALL allow a student to list, filter, preview, and download materials from every active or archived subject in the student's effective class. Students SHALL not create, modify, rebuild, or delete any material regardless of a supplied subject identifier.

#### Scenario: Student views materials across subjects
- **WHEN** a class-A student opens the materials page without selecting a subject
- **THEN** the system returns readable materials from all class-A subjects with each material's subject identity

#### Scenario: Student attempts a material mutation
- **WHEN** a student directly calls upload, rename, reindex, or delete for any subject material
- **THEN** the system returns HTTP 403 and leaves the material, file, index generations, chunks, and vectors unchanged

### Requirement: Subject-aware material responses are safely filterable
The system SHALL expose a material's subject identifier and display name in authorized material-list, detail, upload, and search responses. Material list filtering by subject SHALL return only subjects within the caller's allowed class/subject scope; an unauthorized or cross-class subject selection SHALL not expose its existence.

#### Scenario: Teacher opens aggregated material list
- **WHEN** a teacher with assignments to multiple subjects requests an unfiltered material list
- **THEN** the system returns only materials from the teacher's assigned subjects and identifies their subjects

#### Scenario: Cross-class material identifier is requested
- **WHEN** a user requests a material belonging to another class
- **THEN** the system returns the same not-found response as for a nonexistent material and returns no subject metadata

### Requirement: Browser controls mirror but do not replace server authorization
The material-management page SHALL present subject administration controls only to authorized class administrators and material mutation controls only for an assigned teacher's subjects. It SHALL let students browse and filter all own-class subjects read-only, and all server-side endpoints SHALL enforce the same restrictions independent of rendered controls.

#### Scenario: Teacher opens the materials page
- **WHEN** a teacher signs in
- **THEN** the page offers uploads and mutations only after a subject assigned to that teacher is selected and never renders another subject's management action as usable

#### Scenario: Student opens the materials page
- **WHEN** a student signs in
- **THEN** the page offers subject browsing, preview, download, retrieval, and question answering but no material mutation control
