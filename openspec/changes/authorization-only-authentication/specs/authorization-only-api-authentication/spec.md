## Purpose

Define the secure, fully header-based authentication contract that replaces CampusClaw's Cookie session with revocable opaque Bearer credentials for browsers and non-browser API clients.

## ADDED Requirements

### Requirement: Protected APIs accept only a valid Bearer access credential
Every protected API endpoint SHALL require exactly one `Authorization: Bearer <access-token>` header. A request with a missing, repeated, malformed, unsupported, expired, revoked, unknown, refresh-token, or inactive-user credential SHALL return `401`, include `WWW-Authenticate: Bearer`, and use a generic error that does not disclose token validity details.

Protected endpoints SHALL ignore authentication Cookies and SHALL NOT authenticate a request from Cookie state. Authentication endpoints and protected responses SHALL NOT set, renew, clear, or depend on Cookies. A request containing a valid legacy Cookie but no valid Bearer access token SHALL be treated as unauthenticated.

#### Scenario: Bearer access token authenticates a protected request
- **WHEN** a client sends one valid access token in `Authorization: Bearer <access-token>` to a protected endpoint
- **THEN** the endpoint SHALL execute under that token's current user identity

#### Scenario: Cookie cannot authenticate after cutover
- **WHEN** a client sends a legacy session Cookie without a valid Bearer access token to a protected endpoint
- **THEN** the system SHALL return `401` and SHALL not use the Cookie identity

#### Scenario: Malformed credential is rejected
- **WHEN** a protected request has a missing, repeated, non-Bearer, malformed, refresh, expired, revoked, or unknown Authorization credential
- **THEN** the system SHALL return `401` with `WWW-Authenticate: Bearer` and SHALL make no state change

### Requirement: Password login issues opaque Bearer credential pair
`POST /api/auth/login` SHALL accept username and password and, after the same account validation and rate-limiting behavior currently applied to login, return HTTP `200` JSON containing public user identity, `token_type` equal to `Bearer`, `access_token`, positive `expires_in`, `refresh_token`, and positive `refresh_expires_in`. The response SHALL use `Cache-Control: no-store` and `Pragma: no-cache`.

Access and refresh values SHALL be opaque high-entropy secrets. The system SHALL persist or compare only one-way representations and SHALL retain server-side lifecycle data sufficient to reject individual expired or revoked credentials. Failed or throttled logins SHALL return the existing generic credential failure and SHALL not issue a token or response Cookie.

#### Scenario: Valid password returns token pair
- **WHEN** valid username and password are posted to `/api/auth/login`
- **THEN** the response SHALL return the documented access and refresh token fields, public user identity, and no-store cache headers without setting a Cookie

#### Scenario: Invalid password returns no token
- **WHEN** invalid credentials or a rate-limited account are posted to `/api/auth/login`
- **THEN** the system SHALL return the generic credential error and SHALL not return tokens or a Set-Cookie header

### Requirement: Refresh uses Authorization header and rotates credentials
The system SHALL provide `POST /api/auth/token/refresh`. The caller SHALL present its refresh token in exactly one `Authorization: Bearer <refresh-token>` header; refresh tokens SHALL NOT be accepted in Cookies, query parameters, or request bodies. A valid request SHALL invalidate the submitted refresh token and return a replacement access/refresh token pair in the same no-store JSON shape used by login.

Refresh credentials SHALL be single-use. Expired, revoked, unknown, access-token, or replayed refresh credentials SHALL return `401` with no new credentials. A replay of a previously rotated refresh token SHALL revoke its credential family as a potential theft signal, so associated access and replacement refresh tokens are unusable immediately.

#### Scenario: Valid refresh rotates token pair
- **WHEN** a client calls `/api/auth/token/refresh` with a valid refresh token in Authorization
- **THEN** the response SHALL invalidate that refresh token and return one replacement access token and one replacement refresh token with no Set-Cookie header

#### Scenario: Replayed refresh revokes family
- **WHEN** a refresh token is reused after it has produced a replacement
- **THEN** the system SHALL return `401`, issue no credentials, and revoke the associated access and refresh credentials

### Requirement: Authorization decisions use current account and scope data
For every successfully authenticated request, the system SHALL evaluate the user's current active status, role, class membership, class-admin grants, and subject assignments. Access tokens SHALL NOT embed or preserve authorization permissions that continue after those records change. A user's Bearer request SHALL receive the same role/class/subject decision and side-effect protections as the current authenticated-user rules provide.

#### Scenario: Scope change takes effect without token reissue
- **WHEN** a user's role, class membership, subject assignment, or active status changes after access-token issuance
- **THEN** the user's next protected request SHALL use the changed authorization state

#### Scenario: Student cannot use teacher operation
- **WHEN** a student presents a valid access token to a teacher- or administrator-only endpoint
- **THEN** the system SHALL deny the operation and SHALL make no unauthorized side effect

### Requirement: Login supersession, logout, expiry, and revocation terminate tokens
The system SHALL preserve the one-active-login policy: each successful password login SHALL revoke all active credential families for that user before issuing a replacement pair. `POST /api/auth/logout` SHALL require a valid access token, revoke its credential family including refresh credentials, return `204`, and include no Set-Cookie header.

Expired, revoked, disabled-user, and superseded access or refresh credentials SHALL be rejected immediately. The system SHALL emit non-secret operational events for issue, refresh, replay, rejection, logout, expiry, and revocation without recording passwords, tokens, Authorization values, or legacy Cookie values.

#### Scenario: New login invalidates old tokens
- **WHEN** a user successfully logs in after already receiving an access/refresh pair
- **THEN** subsequent use of the older access token or refresh token SHALL return `401`

#### Scenario: Logout invalidates current family
- **WHEN** a client calls `/api/auth/logout` with a valid access token
- **THEN** the endpoint SHALL return `204` and future use of that access token or family refresh token SHALL return `401`

### Requirement: Browser client stores and sends tokens safely within the current tab
The browser client SHALL store the token pair only in `sessionStorage`, never in Cookies, `localStorage`, IndexedDB, URLs, HTML attributes, logs, analytics, or server-rendered page data. It SHALL clear both values on logout, refresh failure, authentication failure, and explicit token invalidation. A fresh browser tab or closed-tab session SHALL require login; reloading within the same tab MAY restore the `sessionStorage` token pair.

The browser API request helper SHALL attach only the access token as `Authorization: Bearer <access-token>` to protected requests. It SHALL rotate the token pair once through the refresh endpoint after an access-token `401`, retry the interrupted idempotent request at most once, and redirect to login after a failed refresh. Browser downloads requiring authentication SHALL use an authorized fetch and generated download object rather than a navigation link that cannot attach Authorization.

#### Scenario: Browser bootstraps protected workspace through Bearer identity
- **WHEN** the `/materials` shell loads with an access token in sessionStorage
- **THEN** the client SHALL call the identity endpoint with Authorization and render protected user data only after that request succeeds

#### Scenario: Browser with no stored token sees no protected data
- **WHEN** the `/materials` shell loads without a usable access token
- **THEN** it SHALL redirect to login without rendering protected user identity or class data

#### Scenario: Protected download includes Authorization
- **WHEN** a signed-in browser user downloads a protected material
- **THEN** the client SHALL fetch it with the access token and initiate the download only after the authorized response succeeds

### Requirement: Cookie and CSRF mechanisms are removed from the authentication contract
The system SHALL remove Cookie session issuance, Cookie session validation, Cookie forwarding for authentication, CSRF-token issuance, and CSRF validation from the authentication and protected API contract. Unsafe Bearer-authenticated requests SHALL rely on possession of the Authorization secret and current authorization checks, not `X-CSRF-Token`.

The system SHALL invalidate existing Cookie sessions during deployment cutover. Any legacy Cookie supplied after cutover SHALL neither authenticate a request nor cause an error that reveals whether the Cookie was valid before cutover.

#### Scenario: Bearer mutation needs no CSRF header
- **WHEN** a client sends a valid access token to an unsafe protected endpoint without `X-CSRF-Token`
- **THEN** the system SHALL evaluate the request without a CSRF requirement

#### Scenario: Legacy Cookie is invalidated at cutover
- **WHEN** deployment enables Authorization-only authentication
- **THEN** all previously issued browser Cookie sessions SHALL require users to log in again with the new Bearer flow

### Requirement: CORS, CSP, proxy, and transport protect JavaScript-readable tokens
The API SHALL use exact configured origin allowlists for CORS and SHALL NOT return `Access-Control-Allow-Credentials`. It SHALL allow Authorization only to trusted origins and SHALL not authorize wildcard origins for token-bearing requests. The frontend proxy SHALL forward Authorization and SHALL not forward Cookie or CSRF headers for authentication.

The browser pages that handle tokens SHALL serve a restrictive Content Security Policy that disallows third-party scripts and uncontrolled inline scripts, and the deployment SHALL use HTTPS for login, protected APIs, and pages that access sessionStorage tokens. Authentication and user-specific responses SHALL prevent shared caching. Token values SHALL be redacted from logs, errors, redirects, telemetry, and diagnostic output.

#### Scenario: Untrusted origin cannot use browser token APIs
- **WHEN** an untrusted origin preflights or sends a browser request requesting Authorization access
- **THEN** the API SHALL not authorize that origin to read or send token-bearing cross-origin requests

#### Scenario: Proxy preserves Authorization without Cookie forwarding
- **WHEN** a client calls a proxied protected endpoint with Authorization and Cookie headers
- **THEN** the proxy SHALL forward Authorization, omit Cookie authentication state, and the API result SHALL depend only on Authorization
