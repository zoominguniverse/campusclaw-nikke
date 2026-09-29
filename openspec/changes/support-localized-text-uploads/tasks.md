## 1. Localized upload handling

- [ ] 1.1 Derive the allowlisted suffix from the original submitted basename, preserve safe Chinese display filenames in material metadata, and continue using UUID-only server storage paths; verify unit tests cover `《活着》.txt`, path-like names, and unsupported extensions.
- [ ] 1.2 Add strict UTF-8-with-BOM, GB18030, and GBK decoding before material persistence/indexing while retaining existing size, empty-content, rollback, and temporary-file cleanup behavior; verify UTF-8 and GBK fixtures persist identical Unicode body text and undecodable input returns HTTP 400 without records.

## 2. Browser feedback and verification

- [ ] 2.1 Render API-provided upload validation messages with text-only DOM assignment and keep a generic fallback for unavailable/non-JSON responses; verify frontend template tests cover the error path.
- [ ] 2.2 Run the backend material contract suite and an authenticated upload smoke test using Chinese filename plus GBK content; verify source display name, normalized preview text, and existing class/teacher authorization remain correct.
