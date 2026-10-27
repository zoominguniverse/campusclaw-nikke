## Why

Teachers cannot upload course text files whose display names are entirely Chinese (such as `《活着》.txt`), because filename sanitization removes the recognizable extension.  Many course text files are also GBK/GB18030 encoded rather than UTF-8, so valid Chinese teaching material is rejected before indexing.

## What Changes

- Preserve the user-facing original filename, including Chinese characters, while deriving the allowed `.txt` or `.md` extension from the original upload name before generating a safe server storage name.
- Decode supported plain-text uploads as UTF-8 first, then safely fall back to common Chinese encodings (GB18030 and GBK) and normalize stored/indexed text to Unicode.
- Return a precise client-visible validation error when a text file cannot be decoded using any supported encoding.
- Show the server-provided upload error in the materials page instead of replacing it with a generic failure message.

## Capabilities

### New Capabilities

- `localized-text-material-upload`: Teacher uploads accept Chinese display filenames and supported Chinese text encodings without weakening existing extension, size, authorization, storage-path, or class-isolation controls.

### Modified Capabilities

- None.

## Impact

- Affected code: `backend/app/materials.py`, material upload tests, and `frontend/templates/materials.html`.
- No database migration, API authentication change, or new external dependency is expected; decoded Unicode continues through the existing PostgreSQL indexing pipeline.
