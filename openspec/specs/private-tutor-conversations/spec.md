# private-tutor-conversations Specification

## Purpose

为师生保存按用户私有的连续解题会话，让每个会话始终关联一个智能体，并可恢复正文、技能和出处记录。限制送给模型的历史长度，明确生成失败和并发处理，避免跨用户泄露或把半途失败误显示为成功回答。

## Requirements

### Requirement: Conversations belong to their creator and effective class
Authenticated students and class-member teachers SHALL create, list and read only conversations belonging to themselves in their current effective class. Class and owner SHALL be derived from authentication, never client claims. Foreign-user, foreign-class and nonexistent IDs SHALL return identical HTTP 404 status and body. Unauthenticated requests SHALL return HTTP 401 without modifying stored data.

#### Scenario: Same class does not imply shared conversations
- **WHEN** a classmate or teacher attempts to read another user's conversation
- **THEN** the response is the same as for a nonexistent conversation

### Requirement: Conversation creation fixes the selected agent
Creation SHALL require one enabled agent in the user's effective class. Missing selection SHALL return HTTP 400; a specified nonexistent, disabled or foreign agent SHALL return HTTP 404. A class with no enabled agents SHALL return HTTP 400 when no agent is specified. The selected agent SHALL remain immutable; later message fields SHALL NOT replace it. Existing conversations SHALL remain usable after the agent is disabled.

#### Scenario: Message attempts to switch agents
- **WHEN** the owner sends a question to a conversation for A while including agent B's ID
- **THEN** the turn continues with A and the persisted association remains A

#### Scenario: No available agent
- **WHEN** a user attempts creation without a selection and their class has no enabled agents
- **THEN** the system returns HTTP 400 with a readable message that no agent is available

### Requirement: Server derives titles and conversation ordering
A new conversation SHALL start with title `新的提问`. The first accepted question SHALL replace it with the question's first 24 Unicode code points. Every accepted question SHALL update the last-activity time; listing SHALL order by that time descending with a stable tie breaker. Later questions SHALL NOT overwrite the title.

#### Scenario: First question and later follow-up
- **WHEN** a user submits an initial question and then a follow-up
- **THEN** the list displays the initial question's prefix and moves that conversation to its latest-activity position

### Requirement: Messages preserve successful and interrupted turns
The system SHALL accept trimmed questions of 2–500 code points and persist each accepted user question before generation. Message roles SHALL be limited to user and assistant and ordered by write sequence. Assistant messages SHALL store final visible content, citation snapshot, selected skill name and completion state. Partial failed output SHALL be marked interrupted; an empty failed generation SHALL NOT create a successful assistant message.

#### Scenario: Question boundary validation
- **WHEN** a question is shorter than 2 or longer than 500 characters after trimming
- **THEN** the system returns HTTP 400 and creates no message

#### Scenario: Partial answer followed by provider failure
- **WHEN** generation fails after some visible text was delivered
- **THEN** history restores exactly that delivered text and metadata as interrupted, never as a completed answer

### Requirement: Model context is bounded and sourced from stored history
Each turn SHALL use at most the latest six eligible stored messages, in write order, each truncated to 500 code points. Only nonempty user and completed assistant messages SHALL enter history. The accepted current question SHALL appear exactly once. Client-supplied history or system messages SHALL NOT enter trusted context. Full message history SHALL remain available for authorized reading.

#### Scenario: Conversation exceeds three rounds
- **WHEN** the next question arrives after more than six stored messages
- **THEN** the provider sees only the latest bounded eligible window and the conversation reader can still access earlier stored messages

### Requirement: Concurrent turns do not interleave one conversation
The system SHALL permit only one active answer generation per conversation across server workers. A simultaneous second submission SHALL return HTTP 409 without creating another question. Failure or disconnect SHALL release the active turn so the owner can later continue; a broken connection SHALL NOT silently resend a POST.

#### Scenario: Two tabs send at once
- **WHEN** the same owner submits from two tabs while one conversation is generating
- **THEN** one turn is accepted and the other returns HTTP 409 with no duplicate message
