## Context

The current Flask API uses a signed Cookie containing a `sid`, user id, and CSRF token. The `sessions` table validates expiry/revocation, and browser pages are server-gated by forwarding the Cookie to `/api/auth/me`. Every protected mutation supplies `X-CSRF-Token`; download links rely on browser Cookie navigation. The frontend proxy currently forwards Cookie and CSRF headers but not Authorization. Its templates contain inline JavaScript and conditionally render user/role data server-side.

The target is intentionally Authorization-only. See [proposal.md](proposal.md) for the migration decision and `specs/authorization-only-api-authentication/spec.md` for the externally observable protocol. It requires client-visible browser secrets, so protecting against XSS and preventing accidental persistence are first-class design constraints.

## Goals / Non-Goals

**Goals:**

- Remove all authentication dependence on Cookies and CSRF tokens.
- Use opaque, revocable, server-validated access/refresh pairs for every client type.
- Keep current role, active-user, class, and subject authorization enforcement authoritative on every request.
- Make browser behavior work with the present multi-page frontend without exposing token data through server rendering or URLs.
- Support reliable cutover, explicit compatibility break, testing, and operational rollback.

**Non-Goals:**

- Preserving existing browser login sessions, silent cross-tab sign-in, OAuth/OIDC, API keys, JWTs, SSO, or third-party delegated access.
- Persisting browser tokens beyond the tab session, storing them in HttpOnly Cookies, or claiming Authorization-only removes XSS risk.
- Changing existing role/class/subject policy or allowing multiple concurrent credential families per user.

## Decisions

### 1. Use opaque access and refresh tokens in Authorization, backed by server state

Issue high-entropy opaque access and refresh values. Both are syntactically Bearer credentials, but token metadata constrains an access token to protected APIs and a refresh token to `/api/auth/token/refresh` only. Store a keyed one-way digest, token kind, parent family id, expiry, revocation, creation, and refresh-rotation linkage; never store plaintext. Recommended defaults are a 15-minute access lifetime and an 8-hour refresh lifetime, configurable in deployment settings.

The existing `LoginSession` record becomes a server-side credential family with no Cookie representation. Add access/refresh child records and indexed digest lookups. This preserves atomic one-login-per-user revocation and gives immediate logout, disabled-user, and refresh-replay invalidation. Self-contained JWTs were rejected because fast individual revocation would require an additional blacklist/version scheme and does not simplify the current service.

### 2. Use direct password-to-token login and Authorization-only refresh

`POST /api/auth/login` validates password and rate limits exactly as now, revokes existing user families, creates a new family and token pair, and returns no-store JSON. `POST /api/auth/token/refresh` accepts exactly one Authorization Bearer value, verifies that it is a refresh token, locks the row, marks it rotated, and returns a replacement pair. Concurrent refresh requests are serialized: one succeeds and a loser is treated as replay, revoking the family.

The refresh token is not accepted in JSON, Cookie, query string, or URL fragment. This makes the two token endpoints consistently header-authenticated after login while keeping the password exchange unambiguous. A body refresh token was considered but rejected to minimize logging/middleware leak paths and preserve one credential transport rule.

### 3. Replace Cookie resolver and CSRF decorators with a single Bearer resolver

Replace the Cookie identity loader with one parser that requires one well-formed Authorization header, looks up an active access token, checks its family, expiry and current user, and sets `g.current_user` plus a Bearer credential context. It returns generic `401` plus `WWW-Authenticate: Bearer` for all credential failures. Refresh-token use outside its endpoint is rejected as `401`.

Remove `require_csrf`, CSRF issue/return fields, Cookie `session` writes/clears, and Cookie-based authentication. Current authorization modules remain unchanged because they continue to consume `g.current_user`; they re-read memberships, roles, and subject assignments rather than accepting claims embedded in a token. `POST /api/auth/logout` revokes the resolver's family without CSRF.

### 4. Store browser tokens in sessionStorage with explicit safeguards

The existing login→materials navigation loses JavaScript memory. To retain usability across that navigation and page reloads, store both token values only in `sessionStorage`, which is isolated per tab and cleared when the tab session ends. `localStorage`, IndexedDB, Cookies, query parameters, HTML, Jinja context, logs, telemetry, and service-worker caches are prohibited token stores.

This is a deliberate compromise: `sessionStorage` remains XSS-readable. Mitigations are a strict CSP, external same-origin JavaScript modules, no third-party script/analytics, no unsafe inline execution, output-safe DOM APIs, no token interpolation, HTTPS, short access TTL, refresh rotation, and clear-on-failure/logout. These reduce but do not eliminate XSS impact; the proposal documents this residual risk.

Implement one client auth module that owns storage, Authorization header construction, an in-flight refresh promise, logout clearing, and unauthenticated redirect. On access `401`, it refreshes once and retries only the interrupted idempotent request. It does not automatically replay unsafe uploads or mutations because outcome uncertainty could duplicate a side effect. On refresh failure it clears storage and redirects to `/login`.

### 5. Change server-rendered page guards into neutral shells

The frontend server cannot inspect sessionStorage during navigation, so `/login` and `/materials` become unauthenticated static shells and must not call backend identity using Cookies. The materials page bootstraps by asking `/api/auth/me` with its access header, then dynamically renders identity, role-specific navigation, and data only after validation. Missing or failed identity bootstrap redirects to login before protected data is added to the DOM.

Replace direct authenticated `<a href>` download navigation with `fetch` using Authorization, then create a short-lived object URL after a successful response. The proxy forwards Authorization and content headers but drops Cookie and CSRF forwarding. To support restrictive CSP, extract template inline scripts to static same-origin modules and use data attributes/DOM APIs rather than inline event handlers.

### 6. Apply non-credentialed CORS, CSP, headers, and secret redaction

Configure an exact trusted-origin allowlist. Direct API CORS replies enumerate permitted methods/headers, include Authorization only for trusted origins, never return `Access-Control-Allow-Credentials`, and never use `*` for token-bearing browser traffic. Same-origin proxy calls continue to work without CORS. Authentication and identity responses add `Cache-Control: no-store` and `Pragma: no-cache`.

Set a restrictive CSP for token-handling pages, at minimum `default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'`, adjusted only through reviewed deployment configuration. Add appropriate `Referrer-Policy`, `X-Content-Type-Options`, and frame protections. Redaction helpers ensure password fields, full Authorization values, access/refresh tokens, and legacy Cookies never enter logs, exception reports, redirects, or telemetry.

### 7. Cut over atomically and revoke legacy sessions

Add an idempotent schema migration for token rows/indexes and a deployment migration that marks every pre-cutover Cookie-backed session revoked. New code ignores all Cookies for auth. The deployment releases the Authorization-only API and frontend shell together; user-visible messaging sends all existing browser users to login once.

Rollback is code/config rollback, not credential restoration: revoked Cookie sessions stay invalid, so users must authenticate again after a rollback to old Cookie-capable code. Do not delete new token tables during rollback. This protects against accidentally resurrecting compromised or stale cookie sessions.

## Risks / Trade-offs

- [sessionStorage is accessible to XSS] → Strict external-script CSP, no third parties/inline scripts, safe DOM rendering, token redaction, short lifetimes, refresh rotation, and documented residual risk.
- [Multi-page navigation cannot carry in-memory token] → Use per-tab sessionStorage; no cross-tab persistence is offered.
- [Access refresh after a non-idempotent request can cause duplicate writes] → Refresh/retry only safe idempotent operations automatically; prompt the user to retry mutations.
- [Bearer token theft works until revocation/expiry] → Short access TTL, server-side family revocation, HTTPS, no cache/log/URL exposure, and no long-lived browser persistence.
- [Refresh replay signals token theft] → One-time rotation, transaction locking, whole-family revocation, and redacted security event.
- [Direct file links cannot attach Authorization] → Authorized fetch + object URL download and associated browser tests.
- [CSP migration breaks existing inline frontend behavior] → Externalize scripts before enabling the enforced policy; verify login/material flows in staging.
- [Cutover invalidates all active browser users] → Announce maintenance, show a clear login path, and schedule a low-usage release window.
- [Rollback cannot revive revoked Cookie sessions] → Treat re-login as expected rollback behavior and retain a tested runbook.

## Migration Plan

1. Add token configuration, schema models, indexes, migration marker, and redaction support while keeping the feature disabled in a pre-release build.
2. Implement Bearer resolver/token endpoints and update backend contracts, then remove Cookie/CSRF auth behavior under the cutover setting.
3. Refactor login/material pages into neutral CSP-safe shells, sessionStorage auth module, Authorization request helper, and authorized downloads; update proxy forwarding.
4. Test direct API, proxied browser, token rotation/replay, user deactivation, role/scope changes, and legacy Cookie rejection in a production-like HTTPS environment.
5. At cutover, apply migration, revoke legacy sessions, release frontend and backend together, enable Authorization-only behavior, and redirect users to login.
6. Monitor redacted errors and refresh-replay events. On rollback, disable the new release or restore the prior release; require re-login rather than restoring any revoked Cookie session.
