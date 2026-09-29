## Purpose

为已认证的 CampusClaw 用户提供参考教学平台风格的统一工作区外壳，使其能从持续可见、与自身角色匹配的导航中进入允许使用的功能。

## ADDED Requirements

### Requirement: Persistent authenticated teaching workspace shell
Every protected teaching workspace page SHALL render inside a common application shell containing a CampusClaw identity block, the server-resolved class or organization context, a left-side role-aware navigation area, a main content area, and a logout control. The visual treatment SHALL use a light application canvas, clear content hierarchy, rounded content surfaces, and a restrained brand-red accent comparable in hierarchy to the supplied reference; exact icons and illustration assets MAY differ.

#### Scenario: Authenticated teacher opens a protected workspace page
- **WHEN** a teacher with a valid session opens a protected workspace page
- **THEN** the page renders the shared CampusClaw shell with a left navigation area, the teacher's server-resolved class context, a main content region, and a logout action

#### Scenario: Unauthenticated visitor requests a workspace route
- **WHEN** a visitor without a valid session requests any workspace route
- **THEN** the system redirects the visitor to `/login` while retaining a safe return destination
- **AND** the response does not render role navigation or protected business content

### Requirement: Navigation exposes only role-eligible functions
The application shell SHALL derive visible navigation from the authenticated role, not from a role value supplied by the browser. Teacher navigation MUST include links to material management and knowledge workflows; student navigation MUST include links to material browsing and knowledge workflows but MUST NOT include material upload, rename, reindex, delete, or administration management entries; class-administrator navigation MUST include class subject and teacher-management entry points; super-administrator navigation MUST include class-administrator management entry points.

#### Scenario: Teacher sees teaching-management navigation
- **WHEN** an authenticated teacher opens the workspace
- **THEN** the left navigation includes entries for the teacher's material-management and knowledge functions
- **AND** no entry offers administration actions outside that teacher's existing server-side authority

#### Scenario: Student sees read-only learning navigation
- **WHEN** an authenticated student opens the workspace
- **THEN** the left navigation includes material browsing, retrieval, and question-answering entries
- **AND** it does not render teacher-only material-management actions or administrator-management entries

#### Scenario: Administrator sees its authorized administration navigation
- **WHEN** an authenticated class administrator or super administrator opens the workspace
- **THEN** the left navigation exposes only the respective existing class-management or institution-management functions allowed to that administrator role

### Requirement: Navigation state and logout are understandable and safe
The shell SHALL visibly distinguish the navigation entry corresponding to the current workspace view, and navigation entries SHALL have accessible names. Invoking logout MUST use the existing protected logout operation; after a successful logout, the client MUST remove the authenticated workspace from view and navigate to `/login`.

#### Scenario: User changes workspace view
- **WHEN** an authenticated user activates an eligible navigation entry
- **THEN** the associated workspace content becomes the current view and its navigation entry receives a non-color-only active indication

#### Scenario: User logs out from the shell
- **WHEN** an authenticated user activates the shell logout control and the existing logout operation succeeds
- **THEN** the user is returned to `/login` and subsequent protected workspace requests require authentication

### Requirement: Responsive navigation remains accessible
On narrow viewports, the workspace shell SHALL provide a keyboard-operable navigation toggle or equivalent compact control that exposes and hides the same role-eligible navigation without obscuring main content. On wider viewports, the role navigation SHALL remain persistently visible at the left side of the workspace.

#### Scenario: Narrow-viewport user opens navigation
- **WHEN** an authenticated user opens the workspace on a narrow viewport and activates the navigation control
- **THEN** the role-eligible navigation becomes available to keyboard and pointer users
- **AND** activating a navigation destination returns focus or reading context to the corresponding main content heading
