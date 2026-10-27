# Spec Delta

## Purpose

在现有 CampusClaw 角色工作区中提供可配置、可持续追问的解题助手，参考课程原型的智能体选择与最近会话交互。让用户能辨别技能、依据、生成状态和保存结果，保持现有材料、检索和管理入口的功能。

## ADDED Requirements

### Requirement: Teachers configure agents and skills in their workspace
Teacher navigation SHALL expose agent and skill management, including a text prompt, enable state, skill source editor or UTF-8 upload, and accessible material and skill binding selections. It SHALL display server validation errors and reflect saved configurations. Student navigation SHALL omit write controls. Existing material and administrative functions SHALL remain available to their authorized roles.

#### Scenario: Teacher maintains an agent
- **WHEN** a teacher saves a prompt, skill definition or binding change
- **THEN** the UI displays the persisted state and any validation error without presenting unsaved changes as saved

### Requirement: Users select an agent and resume private conversations
The tutor UI SHALL show enabled agent choices, a new-conversation action and the user's recent conversations ordered by server activity. New conversations SHALL explicitly select an agent. Opening history SHALL restore its messages, skill labels, citations and selected agent. Changing the selected agent SHALL create a new conversation rather than mutate the current one.

#### Scenario: No enabled agent
- **WHEN** the user's agent list is empty
- **THEN** the UI shows a readable empty state and prevents a question from being submitted without an agent

#### Scenario: Resume a disabled agent's old conversation
- **WHEN** the user opens an existing conversation for a now-disabled agent
- **THEN** its selected agent and history remain visible and the user can continue that conversation

### Requirement: Streaming UI reflects metadata and incremental content
The UI SHALL display citations and skill from meta before appending delta text in order. During generation it SHALL show progress and prevent duplicate sends. It SHALL distinguish completed, interrupted and unsaved output; reload SHALL recover persisted history. No-citation answers SHALL show no source cards. Switching views SHALL cancel the abandoned stream without mixing its events into another conversation.

#### Scenario: Failure after visible text
- **WHEN** the UI receives error or EOF without done
- **THEN** it keeps any visible text marked interrupted or unsaved and enables deliberate continuation without silently resending the question

### Requirement: Citation sources open under current authorization
Each displayed source SHALL provide its material title and chunk location and an action to inspect currently authorized evidence or original text using existing APIs. Deleted, unavailable or revoked sources SHALL show a readable unavailable state. Uploaded and generated content SHALL render as text or sanitized content and SHALL NOT execute scripts.

#### Scenario: Source contains HTML or script syntax
- **WHEN** a citation title, evidence or model output contains executable markup
- **THEN** it is displayed safely as content and cannot read stored credentials

#### Scenario: Material was removed after the answer
- **WHEN** a user opens a citation whose material has since been deleted
- **THEN** history retains its prior source label while the opener reports that the source is unavailable

### Requirement: Tutor interactions support small screens and keyboard use
The tutor workspace SHALL keep agent selection, history, question input, answer status and citations usable on desktop and narrow mobile viewports. Form controls SHALL have accessible labels and validation messages; stream status SHALL be announced without announcing every token. Focus SHALL remain usable after sending, switching conversations or closing a source preview.

#### Scenario: Narrow viewport and keyboard navigation
- **WHEN** a user opens the tutor on a mobile-sized viewport or navigates with a keyboard
- **THEN** the user can select an agent, submit a question, inspect its answer and open a citation without clipped essential controls
