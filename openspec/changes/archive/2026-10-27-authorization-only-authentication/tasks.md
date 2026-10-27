## 1. Configuration and durable token state

- [x] 1.1 Add Authorization-only feature/cutover settings, distinct token-digest secret, access/refresh TTLs, exact trusted origins, and production HTTPS/CORS validation in `backend/app/config.py`; verify unsafe secret/origin configurations fail at startup while documented development settings work.
- [x] 1.2 Add opaque access-token and rotating refresh-token persistence linked to the existing `LoginSession` family, including token kind, one-way digest, expiry, revocation, rotation linkage, and indexed lookups; verify fresh SQLite initialization succeeds and tests prove no plaintext token persists.
- [x] 1.3 Extend the idempotent schema-upgrade path with token-table/index migration markers and a cutover migration that revokes all existing Cookie-era active sessions; verify upgrade is repeatable, preserves schema integrity, and legacy session ids no longer authenticate.
- [x] 1.4 Add redacted authentication lifecycle event helpers; verify logs, exceptions, and error responses never include passwords, full Authorization values, access/refresh tokens, or legacy Cookie values.

## 2. Bearer-only backend authentication

- [x] 2.1 Implement cryptographically secure token generation, keyed one-way digest lookup, expiry/revocation checks, and constant-time verification; verify valid, malformed, unknown, expired, revoked, and mismatched token cases with focused unit tests.
- [x] 2.2 Replace Cookie identity loading with a single access-token Authorization resolver that sets `g.current_user`, returns generic `401` with `WWW-Authenticate: Bearer`, and rejects refresh tokens outside refresh; verify all protected API route families reject Cookie-only requests.
- [x] 2.3 Remove Cookie-session writes/clears and CSRF issuance/validation from authentication and protected mutations while retaining current role/class/subject authorization through `g.current_user`; verify Bearer unsafe requests work without CSRF and authorization-denied mutations still make no side effects.
- [x] 2.4 Implement `POST /api/auth/login` token-pair response with existing password throttle and single-active-family revocation, plus `POST /api/auth/me` Bearer identity response; verify success JSON/no-store headers, generic failed-login behavior, and absence of Set-Cookie.
- [x] 2.5 Implement Authorization-header-only refresh rotation, transactional replay detection/family revocation, and Bearer logout; verify one refresh wins under concurrency, replay invalidates its family, logout returns `204`, and neither flow accepts or emits Cookies.
- [x] 2.6 Add exact-origin non-credentialed CORS/OPTIONS, cache prevention, security headers, and token response redaction for direct API requests; verify trusted Authorization preflights are minimally allowed and untrusted origins receive no credentialed or wildcard permission.

## 3. Browser and proxy conversion

- [x] 3.1 Refactor login browser code into a CSP-safe external module that stores successful token pairs only in sessionStorage, clears them on failure/logout, and never interpolates tokens into DOM, URLs, or logs; verify token state survives same-tab navigation/reload but not a fresh tab session.
- [x] 3.2 Convert `/login` and `/materials` server routes from Cookie-gated user pages to neutral shells that contain no server-rendered identity/class data; verify the materials client calls Bearer `/api/auth/me` before rendering protected content and redirects missing/invalid token state to login.
- [x] 3.3 Build a shared browser auth/API client that attaches the access token, serializes one refresh attempt, retries idempotent failed requests once, clears/redirects after failed refresh, and never auto-replays unsafe operations; verify this behavior with frontend tests and simulated 401 sequences.
- [x] 3.4 Move materials role-specific UI rendering to post-bootstrap client logic and replace authenticated download links with Bearer-authorized fetch/object-URL downloads; verify no protected identity/data appears before bootstrap and downloads succeed only with Authorization.
- [x] 3.5 Update the frontend proxy to forward Authorization, omit Cookie/CSRF authentication forwarding, and retain only required response headers; verify proxied login, refresh, protected requests, logout, and download operations never depend on Cookie or Set-Cookie behavior.
- [x] 3.6 Externalize remaining inline token-handling scripts and apply restrictive CSP, referrer, frame, and content-type protections; verify page tests and browser smoke tests pass with inline script execution blocked and third-party scripts disallowed.

## 4. Regression, cutover, and operations verification

- [x] 4.1 Add backend contracts for missing/repeated/malformed/refresh/expired/revoked Bearer tokens, Cookie-only rejection, login pair shape, refresh protocol, no Cookie headers, family supersession, logout, and current authorization parity; verify focused SQLite tests pass.
- [x] 4.2 Add security tests for sessionStorage client constraints, CORS/CSP headers, secret redaction, cache prevention, token replay, deactivated users, changed role/class/subject scope, and unauthorized download behavior; verify no test output or response leaks token material.
- [x] 4.3 Update existing backend and frontend Cookie/CSRF tests to the Authorization-only contract and run the complete suites; verify the test suite no longer assumes Cookie login, CSRF headers, or server-rendered authenticated pages.
- [x] 4.4 Document breaking migration, required environment variables, token storage/XSS residual risk, HTTPS and CSP deployment requirements, client refresh protocol, cutover communication, monitoring, and rollback re-login behavior; verify documentation includes no live secrets and matches actual endpoint/configuration names.
- [x] 4.5 Execute a production-like HTTPS staging cutover: login → protected API/UI → download → access expiry/refresh → logout → legacy-Cookie rejection → fresh login after rollback; verify all outcomes and redacted operational events before enabling production cutover.
