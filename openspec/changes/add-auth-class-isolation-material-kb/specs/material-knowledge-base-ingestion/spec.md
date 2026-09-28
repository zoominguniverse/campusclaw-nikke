## Purpose

为教师提供受班级权限保护的教学材料上传能力，并保证成功上传的材料同时形成知识库记录，使本班材料列表能够反映真实可查询的知识库内容。

## ADDED Requirements

### Requirement: Teacher can upload class materials

The system SHALL allow an authenticated teacher to upload a teaching material for a class the teacher is authorized to manage.

The MVP SHALL accept bounded plain-text or Markdown material (`.txt` and `.md`), derive a display title from the supplied title or safe filename, and store the uploaded file under storage scoped to its owning class.

#### Scenario: Authorized teacher uploads material

- **WHEN** an authenticated teacher uploads a valid teaching material for the teacher's class
- **THEN** the system accepts the material, associates it with that class and uploader, and returns a success result containing the material record identity or equivalent reference

#### Scenario: Unsupported or unparseable material is rejected

- **WHEN** an upload has an unsupported extension, is empty, exceeds the configured size limit, or cannot be parsed into text
- **THEN** the system returns an explicit HTTP 400-class error, creates no completed material or knowledge-base row, and removes any staged or orphaned file

#### Scenario: Teacher uploads to an unauthorized class

- **WHEN** an authenticated teacher attempts to upload material for a class the teacher does not manage
- **THEN** the system rejects the request with HTTP 403 and does not persist or index the material

### Requirement: Student cannot upload materials

The system SHALL reject material-upload requests from authenticated students at the server-side authorization boundary.

#### Scenario: Student directly calls upload interface

- **WHEN** an authenticated student calls the material-upload interface, whether or not an upload button is visible
- **THEN** the system returns HTTP 403 and does not persist the material or write it to the knowledge base

### Requirement: Successful upload writes to the knowledge base

The system SHALL write an accepted teacher-uploaded material to the knowledge base within the same externally observable success operation, with class ownership and uploader metadata retained.

#### Scenario: Uploaded material creates a knowledge-base record

- **WHEN** an authorized teacher upload completes successfully
- **THEN** the material's parsed text is available as a class-scoped knowledge-base record with the correct class, material, and uploader association; this change does not require retrieval-augmented question answering

#### Scenario: Knowledge-base write fails

- **WHEN** material persistence or knowledge-base indexing fails during an upload
- **THEN** the system returns a failure result and does not report the material as successfully uploaded or list it as a completed knowledge-base record

### Requirement: Class material list reflects successful uploads

The system SHALL make a successfully uploaded material discoverable in the material list for its owning class and SHALL not expose it in another class's list.

#### Scenario: Teacher lists own class materials after upload

- **WHEN** the uploading teacher requests the authorized class material list after a successful upload
- **THEN** the list contains a record for the uploaded material

#### Scenario: Same-class student sees the uploaded record read-only

- **WHEN** a student in the owning class requests the material list after a successful teacher upload
- **THEN** the list contains the new material title or record, while any direct student update, replace, or upload request remains rejected with HTTP 403

#### Scenario: Other class lists materials

- **WHEN** a user requests a material list for another class
- **THEN** the response does not contain the uploaded material and the request is rejected when the caller is not authorized for that class

### Requirement: Class-scoped online material preview

The system SHALL let an authenticated teacher or student open an online preview of a material in the caller's authorized class. The browser SHALL render the returned material body as text, not executable HTML.

#### Scenario: Authorized user previews own-class material

- **WHEN** an authenticated user selects a material in the user's authorized class from the material list
- **THEN** the system returns the material title and parsed text through the class-scoped material-detail operation and the browser displays that text inline

#### Scenario: User attempts to preview another class's material

- **WHEN** an authenticated user requests a material preview for a class outside the user's authorized scope
- **THEN** the system returns HTTP 403 without returning the material title or body, and the browser displays no preview content
