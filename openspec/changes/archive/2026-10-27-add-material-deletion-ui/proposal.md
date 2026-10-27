## Why

Teachers can upload materials but cannot remove obsolete or incorrectly uploaded items from the browser, even though the protected backend deletion endpoint already exists.  The materials page needs a deliberate, teacher-only control to complete the lifecycle safely.

## What Changes

- Add a delete action beside each material only for teachers.
- Require an explicit browser confirmation before issuing the existing DELETE request.
- Reuse the same class-scoped, CSRF-protected endpoint and refresh the material list after success.
- Show success and API failure messages as text without exposing storage paths or bypassing existing authorization.

## Capabilities

### New Capabilities

- `material-deletion-ui`: Teachers can intentionally delete an in-class material from the protected browser workflow with confirmation and clear feedback.

### Modified Capabilities

- None.

## Impact

- Affected code: `frontend/templates/materials.html` and frontend template tests.
- Existing backend `DELETE /api/classes/<class_id>/materials/<material_id>` behavior, database cleanup, and authorization are reused unchanged.
