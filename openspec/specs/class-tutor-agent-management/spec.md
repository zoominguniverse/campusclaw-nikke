# class-tutor-agent-management Specification

## Purpose

让教师在自己的有效班级内维护解题智能体，把角色提示词、可用技能和可查材料组合成学生能够选择的助手。明确配置生效时机、启停含义及绑定的班级与学科权限，使新增助手不会扩大既有材料访问范围。

## Requirements

### Requirement: Teachers manage class tutor agents
The system SHALL allow an authenticated active class-member teacher to create, read, update and enable or disable tutor agents in the teacher's effective class. Agent names SHALL be nonempty, unique within that class and at most 64 Unicode code points; prompts SHALL be at most 2000 code points. Blank prompts SHALL use the default tutoring role. Students and administrative roles without teacher privilege SHALL receive HTTP 403 for writes.

#### Scenario: Valid agent with blank prompt
- **WHEN** a teacher creates an agent with a valid name and blank prompt
- **THEN** the agent is persisted and later answers use the default role without rejecting the request

#### Scenario: Invalid or duplicate agent name
- **WHEN** a teacher submits an empty, overlong or already used class-local name, or an overlong prompt
- **THEN** the system returns HTTP 400 with a readable error and performs no partial write

#### Scenario: Student or administrator invokes teacher writes
- **WHEN** a student, super administrator or class administrator without teacher privilege directly creates or modifies an agent
- **THEN** the system returns HTTP 403 and retains the prior configuration

### Requirement: Agent selection respects class and enabled status
The system SHALL list only enabled agents to students, while class-member teachers can inspect enabled and disabled agents. Student reads of disabled agents and all object reads outside the effective class SHALL return the same HTTP 404 body as nonexistent agents. Client-supplied class or role fields SHALL NOT expand visibility.

#### Scenario: Hidden disabled or foreign agent
- **WHEN** a student reads a disabled agent, or an authenticated user reads an agent in another class
- **THEN** the response is identical in status and body to reading a nonexistent agent

### Requirement: Agent bindings are authorized and atomic
An agent SHALL accept zero or more distinct class-local skill and material bindings. Teacher material bindings SHALL also be within current authorized subjects. Foreign, nonexistent or unauthorized material IDs SHALL return HTTP 404; no submitted configuration SHALL be partially applied. Students SHALL receive no bound material content outside their current authorization.

#### Scenario: Mixed valid and forbidden bindings
- **WHEN** a teacher submits a valid skill and a foreign or unauthorized material together
- **THEN** the system returns HTTP 404 and neither the bindings nor the agent fields are changed

#### Scenario: Empty bindings
- **WHEN** a teacher removes every skill and material binding
- **THEN** the configuration is valid and the next answer uses no skill and retrieves no material

### Requirement: Current configuration applies to the next turn
The system SHALL reread the selected agent's current prompt and bindings for every turn. Disabling an agent SHALL prevent new selection while retaining access through the owner's existing conversations. Unbinding, disabling or deleting a skill and deleting a bound material SHALL remove them from subsequent turns. Historical citations SHALL NOT grant access to deleted or currently unauthorized sources.

#### Scenario: Teacher edits an agent during a conversation
- **WHEN** a teacher changes the prompt or unbinds a material after a conversation was created
- **THEN** its next turn uses the updated configuration without changing the conversation's selected agent

#### Scenario: Existing conversation uses a disabled agent
- **WHEN** the owner continues a conversation whose selected agent was disabled
- **THEN** the conversation remains usable but that agent cannot be selected for a new conversation
