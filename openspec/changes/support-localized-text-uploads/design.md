## Context

See `proposal.md` for the motivation.  The upload endpoint currently calls `secure_filename` before checking the suffix, which turns an all-Chinese filename such as `《活着》.txt` into `txt` and loses the extension.  It subsequently decodes the temporary file only as UTF-8.  The same endpoint owns authorization, size limits, temporary-file cleanup, material persistence, and indexing.

## Goals / Non-Goals

**Goals:**

- Derive the allowed extension from the untrusted original basename without allowing it to influence any server filesystem path.
- Preserve the original display filename in metadata and normalize supported input encodings to Unicode before the existing indexing pipeline.
- Give browser users the concrete validation error returned by the API.

**Non-Goals:**

- Automatic character-set detection, support for arbitrary legacy encodings, binary document parsing, or changes to the `.txt`/`.md` allowlist.
- Re-encoding previously stored material or changing vector/chunk schemas.

## Decisions

### Separate display-name validation from storage-name generation

Read the suffix from the submitted filename with `Path(...).suffix.lower()` before applying any filename sanitization.  Retain the submitted basename as `original_filename` after rejecting path-like/empty values, and continue generating storage filenames solely from a UUID plus the validated suffix.

This prevents the storage path from inheriting user-controlled characters while retaining a user-recognizable name.  Using `secure_filename` as the material display name was rejected because it destroys non-ASCII names and cannot reliably preserve their extension.

### Use a deterministic strict decoding sequence

Decode raw upload bytes strictly with `utf-8-sig`, then `gb18030`, then `gbk`; the first successful decoding is the Unicode body used for the existing material, chunking, embedding, and download flows.  No decoder uses `errors="replace"` or a heuristic detector.

`gb18030` covers most modern Chinese legacy text and is more complete than GBK; explicit GBK remains in the supported contract for compatibility and clear behavior.  A third-party charset detector was rejected because detection ambiguity can silently corrupt teaching content and adds a dependency.

### Preserve atomic upload behavior

All validation and decoding occur before a material or entry is created and before moving the temporary file to its final UUID path.  Existing rollback and cleanup continue to remove the temporary data on any failure.

### Surface API validation messages safely

The browser extracts an `error` string only from a JSON failure response and assigns it with `textContent`; otherwise it uses the existing generic failure text.  This adds useful diagnosis without introducing HTML injection.

## Risks / Trade-offs

- [Some arbitrary byte sequences can decode under GB18030] → Use strict decoding, keep the supported set intentionally small, and retain existing non-empty validation.
- [Original filenames can include confusing Unicode] → They are display metadata only; UUID-derived storage paths and existing class-scoped download authorization remain authoritative.
- [Downloaded source bytes may retain their original encoding while indexed text is Unicode] → Preserve original uploaded bytes for download and document that indexing/preview operate on normalized Unicode.

## Migration Plan

1. Deploy the endpoint and browser change without a schema migration.
2. Exercise UTF-8, GBK, and Chinese-name uploads in the existing protected workflow.
3. Roll back by redeploying the prior application image; no data conversion is required.
