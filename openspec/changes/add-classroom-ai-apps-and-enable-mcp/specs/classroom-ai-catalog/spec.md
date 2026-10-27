## Purpose

为在线课堂提供能直接选用的备课、测验、讨论与复习应用，并通过可预览和编辑的提示词模板降低教师配置成本，保留既有权限和用户修改。

## ADDED Requirements

### Requirement: Teachers can render reusable classroom prompts
The system SHALL expose six built-in templates covering mathematics guidance, language guidance, lesson planning, classroom quizzes, discussion and revision. Teachers SHALL preview prompts using bounded subject, grade, topic and duration variables. Unknown templates, variables or invalid values SHALL be rejected; rendering SHALL not write configuration or call a model.

#### Scenario: Teacher applies a template
- **WHEN** a teacher selects a template and supplies valid classroom variables
- **THEN** the rendered prompt fills the editable agent form and is persisted only after explicit agent save

#### Scenario: Non-teacher or invalid input
- **WHEN** a student attempts template rendering or a teacher supplies an unknown or overlong variable
- **THEN** the operation is denied without changing any agent

### Requirement: Classes receive additional classroom applications idempotently
Explicit demo seeding SHALL add lesson-planning, quiz, discussion and revision agents to each class with a usable role prompt. Existing agent names, prompts, bindings and enable states SHALL not be overwritten by repeated seeding. New agents SHALL start without implicit class-wide material or tool access.

#### Scenario: Restart after teacher edits
- **WHEN** a teacher edits a seeded classroom agent and seeding runs again
- **THEN** the teacher's changes remain intact and no duplicate agent is created

### Requirement: Template application preserves authorization
Applying a template SHALL retain the existing class, role and subject checks for saved agents. Templates SHALL not grant material access or MCP tool permission. Variable rendering SHALL use literal substitution without executing expressions or treating substituted text as code.

#### Scenario: Variable contains template-like syntax
- **WHEN** a variable contains braces or markup
- **THEN** it remains literal data in the editable prompt and grants no execution or permission
