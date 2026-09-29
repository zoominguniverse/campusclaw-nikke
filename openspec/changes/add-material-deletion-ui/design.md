## Context

The existing material API already enforces teacher role, effective class scope, CSRF validation, chunk/generation cleanup, and source-file deletion.  The materials template renders preview and download buttons for every listed item but does not expose the existing delete capability.

## Goals / Non-Goals

**Goals:**

- Provide a visible teacher-only deletion workflow with a deliberate confirmation step.
- Reuse the existing API and client-side CSRF helper rather than duplicate authorization logic.
- Keep list rendering and feedback safe through text-only DOM updates.

**Non-Goals:**

- Soft deletion, undo/history, bulk deletion, student deletion, or backend deletion-contract changes.

## Decisions

### Render the action conditionally from the authenticated template user

The server-supplied role already controls the upload form, so the material list will add a delete button only when the authenticated page user is a teacher.  The server remains the authority: the existing API continues to reject a forged student deletion request.

### Confirm before issuing DELETE and refresh only after success

Use the native browser confirmation dialog with the material title as plain text.  On confirmation, call the same API helper with `DELETE`; on HTTP 204, set a success message and reload the list.  On failure, retain the list and surface the API `error` text through `textContent` with a generic fallback.

### Do not display sensitive storage details

The browser passes only the material identifier already supplied by the list endpoint.  It does not receive or render filesystem paths, chunk data, or delete-internal state.

## Risks / Trade-offs

- [Native confirmation is visually minimal] → It gives an accessible, browser-standard explicit confirmation without adding dependencies.
- [A stale list can target an already deleted item] → Preserve the API error response and reload only after successful deletion.

## Migration Plan

1. Deploy the template-only change alongside the existing API.
2. Verify teacher deletion, cancellation, and student UI absence.
3. Roll back by restoring the prior Web image; no database migration is involved.
