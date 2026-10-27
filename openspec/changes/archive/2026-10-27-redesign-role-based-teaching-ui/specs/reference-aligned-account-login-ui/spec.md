## Purpose

为 CampusClaw 提供与教学平台演示风格一致、可在桌面和移动端使用的账号密码登录入口，同时不削弱既有的服务端认证与会话安全边界。

## ADDED Requirements

### Requirement: Branded account-password entry page
The system SHALL present `/login` as a two-region CampusClaw entry page on desktop viewports: a branded introduction region and a visually distinct account-password login region. The page MUST identify the product, state its teaching-material and role-isolation value, and show only account identifier and password as the authentication inputs; it MUST NOT require users to choose or reveal a role before authentication.

#### Scenario: Unauthenticated visitor opens the login page on a desktop viewport
- **WHEN** an unauthenticated visitor requests `/login` with a desktop-width viewport
- **THEN** the visitor sees a CampusClaw-branded introduction panel beside an account-password form with labelled account and password fields and a login action
- **AND** the page does not display a selectable list of preset users or role-entry buttons

#### Scenario: Authenticated visitor opens the login page
- **WHEN** a visitor with a valid authenticated session requests `/login`
- **THEN** the system redirects the visitor to the protected teaching workspace instead of presenting another login form

### Requirement: Login form behavior and error feedback are preserved
The login form SHALL authenticate through the existing account-password login contract, preserve a valid `next` destination after successful login, and display a generic, non-enumerating failure message when authentication fails. Submitting the form MUST make the status available to assistive technology and MUST NOT put account passwords, session identifiers, or server secrets into page markup, URL parameters, or client-side persistent storage.

#### Scenario: Valid account-password submission succeeds
- **WHEN** a visitor submits valid account identifier and password credentials from the branded login form
- **THEN** the system establishes the existing authenticated session and navigates to the validated requested destination or the default protected workspace

#### Scenario: Invalid account-password submission fails safely
- **WHEN** a visitor submits an unknown account identifier or an incorrect password
- **THEN** the login page remains available and communicates one generic authentication failure message
- **AND** the response does not disclose whether the account identifier exists

### Requirement: Responsive and accessible login presentation
The login page SHALL remain operable at narrow viewport widths by stacking or otherwise reflowing its presentation without hiding the account-password fields, login action, error status, or essential product identity. Form controls MUST have programmatic labels, visible focus indication, sufficient contrast against their immediate background, and keyboard-operable submission.

#### Scenario: Narrow-viewport visitor accesses login
- **WHEN** an unauthenticated visitor opens `/login` on a narrow viewport
- **THEN** the branded content and login form reflow without horizontal scrolling of the primary form
- **AND** the visitor can complete and submit the labelled account-password fields using only a keyboard
