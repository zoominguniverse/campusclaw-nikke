## Purpose

Allow teachers to upload ordinary Chinese course text files regardless of Chinese display filename or common Chinese text encoding, while preserving the existing protected material workflow.

## ADDED Requirements

### Requirement: Localized text filenames are accepted safely
The system SHALL accept an authorized teacher's `.txt` or `.md` upload when the original filename contains Chinese characters or punctuation, determine eligibility from the original filename's extension, preserve that original filename as material metadata, and use a separate server-generated path for stored bytes.

#### Scenario: Upload a Chinese-named text file
- **WHEN** an authorized teacher uploads `《活着》.txt`
- **THEN** the system accepts the file as text material and returns the original Chinese filename in the material response

#### Scenario: Reject an unsupported original extension
- **WHEN** an authorized teacher uploads a file whose original filename ends in `.pdf`
- **THEN** the system rejects it with HTTP 400 before creating material, entry, chunk, or stored-file records

### Requirement: Common Chinese text encodings are normalized for indexing
The system SHALL decode accepted text uploads using strict UTF-8 (including UTF-8 BOM), GB18030, or GBK decoding, normalize the result to Unicode text before persisting `knowledge_entries.body_text` and indexing, remove U+0000 code points that PostgreSQL text fields cannot store, and SHALL NOT introduce lossy replacement characters during decoding. Original uploaded bytes SHALL remain available through the existing download flow.

#### Scenario: Upload a GBK course text file
- **WHEN** an authorized teacher uploads a valid GBK-encoded `.txt` file
- **THEN** the material upload succeeds and the stored material body equals the intended Unicode text

#### Scenario: Normalize NUL-padded legacy text
- **WHEN** an authorized teacher uploads a supported-encoding text file containing U+0000 padding
- **THEN** the upload succeeds, its normalized stored/indexed body contains no U+0000 code points, and its original download remains available

#### Scenario: Upload an unsupported binary or malformed text file
- **WHEN** an authorized teacher uploads an allowed-extension file that cannot be decoded using UTF-8, GB18030, or GBK
- **THEN** the system returns HTTP 400 with a clear supported-encoding error and creates no material, entry, chunk, or stored file

### Requirement: Upload errors remain actionable in the browser
The materials page SHALL render an API-provided upload validation error as text when an upload fails, while retaining a safe generic fallback for non-JSON or unavailable responses.

#### Scenario: Display decoding failure
- **WHEN** a teacher uploads an undecodable text file
- **THEN** the page displays the returned encoding-validation message rather than only a generic upload-failed message
