## 1. Teacher deletion workflow

- [x] 1.1 Add a teacher-only material delete control that requests confirmation, sends the existing CSRF-protected class-scoped DELETE request, and reloads the list only after HTTP 204; verify template tests cover action rendering, cancellation, and success wiring.
- [x] 1.2 Render successful deletion and safe API error feedback as text without exposing material storage paths; verify frontend tests cover generic and API-provided failure messaging.

## 2. Verification

- [x] 2.1 Run frontend tests and an authenticated browser-facing API smoke test that creates then deletes a teacher-owned material; verify the material is absent afterward and a student deletion request remains forbidden.
