## Why

CampusClaw currently authenticates web users through a Flask session Cookie and CSRF token, while the API proxy does not forward `Authorization`. The required target architecture is a uniform header-based API contract with no authentication Cookies, which makes API-client behavior explicit and eliminates Cookie/CSRF dual-mode complexity.

This is a deliberate security and compatibility trade-off: browser tokens must be readable by JavaScript, so the design must constrain their lifetime, storage, XSS exposure, CORS behavior, revocation, and migration more tightly than the current HttpOnly Cookie model.

## What Changes

- **BREAKING** Replace Cookie-session authentication entirely: all protected APIs SHALL require `Authorization: Bearer <token>`; Cookie-based login state is no longer accepted.
- **BREAKING** Change browser login to return an opaque access token and opaque refresh token in JSON; the browser client stores them in `sessionStorage` for the active tab and sends the relevant token in Authorization headers.
- Add short-lived access tokens, one-time refresh-token rotation through an Authorization header, server-side token families, current-account checks, immediate revocation, and the existing single-active-login behavior.
- Remove Cookie issuance/clearing, Cookie CSRF validation, credentials-mode browser fetches, Cookie forwarding, and `Set-Cookie` proxy requirements from authentication flows.
- Refactor frontend page access so the `/materials` page is an unauthenticated shell that bootstraps identity with a Bearer-authenticated API request; protected data remains unavailable until that request succeeds.
- Apply exact-origin non-credentialed CORS, no-store authentication responses, restrictive Content Security Policy, secret redaction, HTTPS enforcement, and client storage/documentation constraints.
- Add a staged migration that invalidates existing Cookie sessions at cutover and gives users a clear re-login path; include rollback behavior and security/regression coverage.

## Capabilities

### New Capabilities

- `authorization-only-api-authentication`: Defines the Bearer-only login, token lifecycle, browser storage, authentication, authorization, CORS, revocation, and Cookie-session removal contract for CampusClaw APIs.

### Modified Capabilities

- None; the project has no existing OpenSpec capability specifications to modify.

## Impact

- Backend: authentication routes/decorators, configuration, token persistence and migration, removal of Flask session/CSRF use, protected-route behavior, API headers, and redacted lifecycle events.
- Frontend: login, materials bootstrap, API request helper, downloads, logout, static CSP, server-rendered page guards, and proxy request-header allowlist.
- Compatibility: existing browser Cookies cease functioning after deployment; API consumers must add Authorization headers and renew their credentials through the specified Bearer refresh flow.
- Operations: token-secret and TTL configuration, CORS/CSP/HTTPS deployment settings, sessionStorage/XSS risk documentation, deployment cutover and rollback playbook, plus backend/frontend security tests.
