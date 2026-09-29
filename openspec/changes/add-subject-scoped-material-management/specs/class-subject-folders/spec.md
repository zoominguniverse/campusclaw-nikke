## Purpose

让每个班级拥有相互独立、可管理的学科目录，并使材料及其可追溯知识库数据始终能追溯到唯一的班级学科归属。

## ADDED Requirements

### Requirement: Subjects are unique folders within a class
The system SHALL model each active or archived subject as a folder owned by exactly one class. Subject name and stable subject key SHALL be unique within that class but need not be unique across classes; a subject from one class SHALL never be reused as a folder in another class.

#### Scenario: Different classes create subjects with the same name
- **WHEN** authorized class administrators create a subject named “数学” in two different classes
- **THEN** the system creates two separate subject folders whose materials and assignments remain isolated

#### Scenario: Duplicate subject is created in one class
- **WHEN** a class administrator creates a subject whose normalized name or stable key already exists in that class
- **THEN** the system returns a validation error and preserves the existing folder

### Requirement: Materials and knowledge records have a consistent subject ownership
The system SHALL require every material to reference one class subject in the same class. The corresponding knowledge entry, current index generation, chunks, embeddings, and stored upload file SHALL remain traceable to that material's subject, and no ready chunk from a material may be queried under a different subject.

#### Scenario: Teacher uploads to an assigned subject
- **WHEN** an authorized teacher uploads a valid file to an assigned class subject
- **THEN** the material response, persisted material, generated entry and ready chunks identify the same class and subject

#### Scenario: A mismatched subject identifier is submitted
- **WHEN** a request supplies a subject that belongs to a different class than the effective material scope
- **THEN** the system rejects the request and does not write a material, file, entry, chunk, or vector

### Requirement: Stored upload files are physically scoped by class and subject
The system SHALL store a non-seeded uploaded file beneath a server-generated class-and-subject storage location using an opaque generated filename. API and browser responses SHALL expose the display filename and subject metadata but SHALL NOT expose the physical path, storage key, or directory layout.

#### Scenario: Same filename is uploaded to two subject folders
- **WHEN** authorized teachers upload files with the same display filename to different subjects
- **THEN** both files are retained without collision and each is downloadable only through its authorized material record

#### Scenario: User downloads a material
- **WHEN** an authorized user downloads a subject material
- **THEN** the attachment uses the safe original filename and no storage path appears in the response

### Requirement: Existing materials are migrated into a safe subject folder
The system SHALL migrate every pre-subject material and its knowledge data to a per-class archived “历史待归档” subject (or an explicitly administrator-mapped subject) before subject authorization is enforced. The migration SHALL be idempotent, SHALL retain material identifiers and original text, and SHALL leave no material or ready chunk without a valid same-class subject.

#### Scenario: Existing class material has no explicit mapping
- **WHEN** the migration encounters an existing class material without an administrator-provided subject mapping
- **THEN** it assigns the material and its traceable knowledge records to that class's archived historical subject without rewriting its original body text or vector values

#### Scenario: Migration is restarted
- **WHEN** the migration runs again after a completed or interrupted prior run
- **THEN** it does not duplicate subjects, materials, entries, chunks, vectors, or files
