## Why

CampusClaw already provides secure account-password authentication and role authorization, but its pages are currently functional HTML forms without the cohesive visual hierarchy needed for a classroom product demonstration. The supplied reference establishes a clearer experience: a branded split-screen entry point and a persistent teaching workspace whose left navigation changes with the signed-in role.

## What Changes

- Replace the plain login page with a responsive, reference-aligned split layout: a branded value-proposition panel on the left and an account-password login card on the right. The existing preset-account picker will not be reproduced.
- Preserve the existing account-password API, session-cookie behavior, generic authentication error, `next` redirect, and server-side authorization; the redesign changes presentation and navigation, not credential or permission semantics.
- Introduce a shared authenticated application shell with a compact brand block, current class/organization context, logout affordance, responsive navigation, and an active-route indicator.
- Generate the left-side navigation from the authenticated user's role so that teachers, students, class administrators, and super administrators receive only entry points to functions their role may use. Hiding an entry is a usability aid and must not replace server-side API authorization.
- Restructure the current single materials page into clearly labelled role-aware content areas while retaining current material browsing, subject selection, upload/management, retrieval, question answering, preview, and administration behavior.
- Adopt the reference's visual language—light workspace canvas, restrained red brand accent, rounded white content cards, readable metrics/list/table patterns, and small semantic icons—with project-appropriate icon substitutions allowed.
- Add desktop and narrow-viewport requirements so the sidebar remains usable on larger screens and collapses into an accessible menu on smaller screens.

## Capabilities

### New Capabilities

- `reference-aligned-account-login-ui`: A branded, responsive account-password login experience that preserves the existing secure authentication contract.
- `role-aware-application-shell`: A persistent authenticated workspace layout with role-scoped navigation, active-route feedback, and responsive sidebar behavior.
- `role-oriented-teaching-workspace`: Role-appropriate information architecture and presentation for the existing teaching-material, knowledge, and administration functions.

### Modified Capabilities

- None. The repository has no main-spec inventory yet; the existing authentication and authorization behavior will be preserved and constrained by the new UI capability rather than altered.

## Impact

- Affects the Flask page routes, `frontend/templates/login.html`, `frontend/templates/materials.html`, new shared template/static style assets, and page-rendering tests.
- Uses the existing `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, materials, subject, knowledge, and administration endpoints without changing their request/response contracts.
- Requires no new runtime dependency and no client exposure of secrets; visual icons may come from inline-safe markup or a bundled icon approach chosen during implementation.
