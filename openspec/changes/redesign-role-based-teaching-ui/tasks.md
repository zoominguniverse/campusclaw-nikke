## 1. Shared visual foundation

- [x] 1.1 Add the project-owned shared template/static-asset structure for CampusClaw design tokens, typography, focus states, cards, forms, status messages, lists, and responsive breakpoints; verify both rendered pages load the local styles without an external CDN dependency.
- [x] 1.2 Refactor the protected-page layout into a reusable application shell with semantic `aside`, `nav`, top context, `main`, and logout regions; verify `/materials` still redirects unauthenticated requests to `/login?next=/materials`.

## 2. Account-password entry experience

- [x] 2.1 Redesign `login.html` as a desktop split screen with CampusClaw product/value content and a separate labelled account-password form, without preset-account or role-selection controls; verify the login page rendered HTML contains only the account/password authentication fields and login action.
- [x] 2.2 Preserve existing login fetch/session behavior, generic error handling, assistive-technology status feedback, and safe `next` return; verify valid and invalid login integration tests retain their existing outcomes.
- [x] 2.3 Implement narrow-viewport reflow and keyboard-visible focus behavior for the login page; verify manually at a narrow viewport that no horizontal scrolling hides the primary form and that keyboard submission works.

## 3. Role-aware application shell and navigation

- [x] 3.1 Define the server-role navigation map for `teacher`, `student`, `class_admin`, and `super_admin`, and render only the allowed navigation entries from the server-resolved user role; verify rendered-page tests assert each role's expected entries and prohibited entries are absent.
- [x] 3.2 Add allowlisted same-page workspace view selection, active navigation state, and focus transfer to the selected content heading; verify an invalid or role-ineligible view identifier falls back to the role's default view and cannot expose a prohibited control.
- [x] 3.3 Add the persistent desktop left rail and an accessible narrow-viewport navigation toggle that exposes the same role-eligible destinations; verify keyboard users can open the toggle, activate a destination, and return to the main-content heading.
- [x] 3.4 Move the existing logout control into the shell while retaining its CSRF-protected API call and `/login` redirect; verify the existing logout page test passes and a completed logout removes protected workspace content from view.

## 4. Role-oriented workspace presentation

- [x] 4.1 Reorganize teacher material browsing, subject selection, upload, preview, download, rename, reindex, and confirmed deletion into labelled material-management cards; verify teacher-only mutation controls appear only after selecting an active assigned subject and existing material tests pass.
- [x] 4.2 Present student material browsing, retrieval, evidence, and grounded Q&A in read-only learning views; verify student-rendered HTML contains no upload, rename, reindex, delete, or administration mutation controls while retaining download, retrieval, question, and citation behavior.
- [x] 4.3 Present class-administrator subject/teacher governance and super-administrator class-administrator governance in their respective workspace views; verify each role's rendered page contains only its existing administration panel and API feedback hook.
- [x] 4.4 Retain text-only rendering for material preview, retrieval excerpts, and citations while applying readable bounded content panels/tables; verify the safe `textContent` rendering assertions and current preview/retrieval tests pass.

## 5. Regression and acceptance validation

- [x] 5.1 Update `frontend/tests/test_pages.py` for the branded login, shared shell, role navigation matrix, responsive-navigation hooks, and preserved protected-page/logout behavior; verify `pytest frontend/tests` passes.
- [x] 5.2 Run the backend authorization and data-isolation regression suite without modifying API contracts; verify the project-supported backend test command passes.
- [x] 5.3 Perform seeded-account visual smoke tests for teacher, student, class administrator, and super administrator at desktop width, plus login and workspace at narrow width; use the new three-class fixture and verify each screen has the reference-like hierarchy, permitted left navigation, usable logout, and no visible out-of-role controls.

## 6. Three-class local demonstration fixture

- [x] 6.1 Add server-side parsing and complete-roster validation for a local ignored runtime credential mapping; document only its non-secret shape in `.env.example` and verify tracked files contain no usable fixture password.
- [x] 6.2 Define an idempotent fixture roster with 1 班、2 班、3 班; one 教务管理员; three class-specific 班主任; 17 teachers; and one student per class. Use unique lower-case Chinese personal-name pinyin account identifiers and existing password hashing.
- [x] 6.3 Seed 语文、数学、英语、物理、化学、生物 for every class and create the required memberships, class-administrator grants, and teacher-subject assignments; verify the same mathematics teacher is assigned to both 1 班 and 2 班 while every other class-subject assignment has its own teacher identity.
- [x] 6.4 Add fixture tests for the roster counts, scopes, shared mathematics assignment, invalid/incomplete credential-map atomicity, and repeat-run idempotency including preservation of existing password hashes.
- [x] 6.5 Create the generated easy-to-remember credentials only in the local ignored `.env`; explicitly purge the recognized prior A/B demonstration fixture; seed the exact three-class roster; and use those credentials to complete the four-role visual smoke tests at `http://127.0.0.1:5174`.
