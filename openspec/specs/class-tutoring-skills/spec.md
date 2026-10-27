# class-tutoring-skills Specification

## Purpose

让教师通过课程规定的中文文本文件维护可复现的解题技能，并让每轮提问只在智能体绑定的启用技能内选择一条。保存文件原文和解析结果，清楚区分匹配、未匹配及技能停用后的行为，支持课堂检查与错误定位。

## Requirements

### Requirement: Skill files have a validated text contract
The system SHALL accept a UTF-8 skill file or its equivalent source text, at most 8000 code points. Metadata before the body SHALL use the keys `名称`, `适用条件`, `资料`, `工具`, `启用`; name, trigger and enabled SHALL be required. Unknown or duplicate keys, missing body and invalid values SHALL return HTTP 400 with a readable error before any write. The submitted source text SHALL be retrievable unchanged.

#### Scenario: Valid Chinese skill definition
- **WHEN** a teacher submits a valid file using Chinese or ASCII colons and an empty line separating metadata from the body
- **THEN** the system stores both the parsed fields and original file text

#### Scenario: Invalid metadata or missing body
- **WHEN** a file repeats a key, includes an unknown key, omits required metadata, contains no body or exceeds 8000 characters
- **THEN** the system returns HTTP 400 naming the validation problem and inserts no skill

### Requirement: Skill fields have bounded supported values
The system SHALL require a name of 1–32 code points, trigger of 1–120, body of 1–2000 and optional material-title scope of at most 32. Tools SHALL accept `knowledge_search` and validated `tool@server` references under `mcp-skill-bindings`. Omitted tools SHALL mean an empty list without preventing required retrieval. Enabled SHALL accept `是` or `否`; invalid values SHALL return HTTP 400.

#### Scenario: Arbitrary tool is rejected
- **WHEN** a teacher submits a tool such as shell execution or an external URL
- **THEN** the system rejects it rather than executing it or granting a new capability

### Requirement: Skill management is class scoped and teacher only
Authenticated class members SHALL list skills in their effective class. Only active class-member teachers SHALL create, replace or delete them. Names SHALL be unique within a class with duplicate writes returning HTTP 400. Foreign or nonexistent skill IDs SHALL have identical HTTP 404 responses. Deletion SHALL remove associated agent bindings without deleting conversation history.

#### Scenario: Same skill name in different classes
- **WHEN** two teachers create identically named skills in their own classes
- **THEN** each class can retain its skill but a duplicate within either class is rejected

#### Scenario: Student attempts to modify a skill
- **WHEN** a student calls a skill write endpoint directly
- **THEN** it returns HTTP 403 and changes no skill or binding

### Requirement: Routing selects at most one bound enabled skill
Each turn SHALL score only the selected agent's currently bound enabled skills. Trigger words SHALL be split on Chinese or ASCII commas and semicolons, `、` and `|`, with whitespace and empty tokens removed and both sides case folded. Each keyword present as a question substring scores one point. The system SHALL select the highest positive score, break ties by lowest skill ID, and select no skill when all scores are zero.

#### Scenario: Tie, disabled and unbound candidates
- **WHEN** two bound enabled skills tie while an unbound or disabled skill has more matching words
- **THEN** only the tied skill with the smaller ID is selected

#### Scenario: English case and Chinese separators
- **WHEN** triggers include `Equation、去括号；通分|面积` and the question contains `equation`
- **THEN** the English word matches without case sensitivity and other separated words remain individual triggers

### Requirement: Guidance skills withhold final solutions
When the selected skill name contains `解题引导`, the answer SHALL identify the student's mistaken step or next useful check without revealing a final answer, choice, computed result, missing poem line or complete solution. With no matched skill, the system SHALL use the agent role with a direct-answer instruction and SHALL NOT retain a previous turn's guidance skill.

#### Scenario: Incorrect expansion
- **WHEN** `数学解题引导` is selected for `2(x+3)=16，我写成2x+3=16，对不对？先别告诉我x`
- **THEN** the response explains that the outside factor must multiply every term without giving x or completing the equation

#### Scenario: Skill disabled between identical questions
- **WHEN** a teacher disables or unbinds that skill and the student repeats the question
- **THEN** it is no longer selected and the next response can give a direct conclusion subject to the current agent prompt
