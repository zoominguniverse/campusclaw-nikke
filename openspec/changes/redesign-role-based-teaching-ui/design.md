## Context

The current Flask frontend has only two rendered pages: a minimal `login.html` and a single `materials.html` that mixes all role-specific controls and its client-side API integration. Server-side authentication, session handling, CSRF use for protected mutations, and per-role/per-class API authorization already exist and are verified by frontend tests. The target reference shows a split entry page and a light, card-based teaching dashboard with a persistent left rail; this change adopts that hierarchy without copying its mock-account switcher or its unimplemented business areas. See `proposal.md` and the three UI capability specs for the behavioral contract.

## Goals / Non-Goals

**Goals:**

- Make the current authenticated experience look and behave like one coherent teaching platform rather than a collection of raw forms.
- Preserve all current API contracts, server-derived user scope, CSRF flow, safe text rendering, and protected-page redirects while making allowed functions discoverable by role.
- Keep the frontend dependency-free and usable without a JavaScript build pipeline.
- Give desktop users a persistent left rail and narrow-screen users an accessible compact navigation control.

**Non-Goals:**

- Creating preset-login buttons, client-side role switching, a new identity provider, or new account-management semantics.
- Implementing the reference product's mock lectures, assistants, homework, audits, analytics, or data model.
- Changing material/knowledge/admin endpoints, their authorization rules, or the existing protected-operation confirmations.
- Delivering a byte-for-byte copy of the reference's images or icons.

## Decisions

### 1. Compose presentation from shared Flask templates and local static assets

Introduce a shared document/layout template for common metadata, design tokens, styles, and the authenticated shell. Keep `login.html` as a dedicated template and refactor `materials.html` to extend the shared layout or include a workspace-shell partial. Put reusable styling in project-owned static CSS and keep the interaction code as local JavaScript, using the current same-origin API proxy.

This removes duplicated layout concerns and makes the branded treatment consistent without adding a frontend framework or external CDN dependency. The alternative—continuing to apply all styles inline in two pages—would make responsive behavior and shared shell changes fragile; introducing React/Vue would expand deployment and testing scope beyond a visual redesign.

### 2. Retain `/materials` as the protected workspace entry and use deterministic workspace views

Keep `/materials` as the default authenticated URL and retain its protected redirect contract. The left navigation will target named, role-eligible workspace views within the authenticated page (for example, material management, retrieval, grounded Q&A, class governance, or institution governance), using a stable fragment or safe same-page view identifier to set the active item and focus the corresponding heading. Browser-controlled values will be allowlisted before they select a view, and the role-derived navigation is the only source of offered destinations.

This achieves reference-like navigation and active-state feedback while avoiding a parallel set of HTML routes that duplicate the same data bootstrap. The alternative—one Flask route per visual section—would be useful if the application later becomes a multipage UI, but it would add redirects, test permutations, and content-loading duplication without changing an API or user requirement in this change.

### 3. Derive one navigation map from server-resolved role and existing capabilities

The template receives only the current user object already obtained from `/api/auth/me`. It will select a declarative navigation map:

| Server role | Visible views |
| --- | --- |
| `teacher` | Material management, knowledge retrieval, grounded Q&A |
| `student` | Material browser, knowledge retrieval, grounded Q&A |
| `class_admin` | Class subjects and teacher assignments |
| `super_admin` | Class-administrator management |

The main content uses the same server-resolved role flags to render the matching panels. No frontend role field, hidden form input, hash fragment, or URL parameter grants a capability; the API continues to enforce the actual authorization.

The reference's top-row user account switcher is deliberately excluded because it conflicts with the requested account-password workflow and could imply that a visitor can adopt another account's privileges.

### 4. Use semantic, accessible UI primitives with the reference's visual hierarchy

Define CSS custom properties for CampusClaw brand red, pale workspace gray, surface/border colors, text hierarchy, spacing, radii, focus outline, and responsive breakpoints. Use semantic `aside`, `nav`, `main`, `section`, headings, labels, buttons, tables/lists, and `role=status`/`role=alert` regions. Icons are small decorative inline symbols or locally bundled assets with text labels; they are never the sole accessible name. The desktop shell has a fixed-width left rail and a compact top context row; mobile replaces the persistent rail with an explicit menu button and close-on-navigation behavior.

This provides a similar visual rhythm while permitting different icons and avoiding unneeded icon packages. The alternative of image-only navigation weakens accessibility and makes text labels less resilient at narrow widths.

### 5. Preserve existing client-side safety and mutation behavior while reorganizing DOM targets

Refactor the current `materials.html` script only as necessary to address the new panels and view containers. Preserve `credentials: include`, CSRF headers, response-status handling, safe `textContent` insertion for material/knowledge data, API error rendering, and the `window.confirm` deletion/reassignment decisions. Initial data loading remains bounded by existing role flags; hidden or non-current panels must not cause teacher/admin mutation controls to render for unauthorized users.

The alternative of replacing the API layer as part of the redesign creates avoidable regression risk and is excluded from this change.

### 6. Validate layout behavior with deterministic rendered-page and browser checks

Extend Flask template tests to assert role-specific navigation, absence of prohibited controls, CSRF-protected logout, existing safe rendering hooks, and protected redirects. Add a lightweight browser-level visual/responsive check if the repository test tooling can execute it without new runtime services; otherwise preserve that verification as a manual acceptance checklist using seeded accounts and standard/narrow viewport widths.

## Risks / Trade-offs

- [Large template refactor can disconnect existing JavaScript selectors] → Preserve stable IDs where practical, migrate selector changes together, and run current page tests plus role-by-role smoke checks.
- [Navigation visibility can be mistaken for authorization] → Keep the existing API checks unchanged; write tests that assert both the absent UI controls and current server denial path.
- [Visual similarity can harm narrow-screen usability] → Treat the supplied dashboard as a hierarchy reference, not a fixed desktop canvas; test the form and navigation keyboard flow at a narrow viewport.
- [Hash/view state can refer to a forbidden or obsolete view] → Allowlist view identifiers, fall back to the role's default view, and never use client state to choose data scope.
- [External icon libraries add network/privacy and failure modes] → Use simple local/inline semantic icons and visible textual labels.

## Migration Plan

1. Add the shared style/template assets and refactor login and workspace markup behind the existing routes.
2. Keep all existing API URLs and request shapes, then migrate client selectors and role panels without modifying backend authorization.
3. Run frontend page tests and backend authorization tests; manually sign in with one account from each seeded role at desktop and narrow widths.
4. Deploy as a frontend template/static-asset update. No database migration, session invalidation, or API consumer migration is required.
5. If rollback is needed, restore the previous frontend template/static-asset revision; the API, database schema, and session contract remain compatible.
