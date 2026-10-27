from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

from sqlalchemy.types import UserDefinedType

from .extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Vector(UserDefinedType):
    """A small pgvector-compatible type that also keeps SQLite tests runnable."""

    cache_ok = True
    hashable = False

    def __init__(self, dimensions: int | None = None):
        self.dimensions = dimensions

    def get_col_spec(self, **kw):
        return f"VECTOR({self.dimensions})" if self.dimensions else "VECTOR"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            return "[" + ",".join(str(float(item)) for item in value) + "]"

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None or isinstance(value, list):
                return value
            try:
                return [float(item) for item in json.loads(value)]
            except (TypeError, ValueError, json.JSONDecodeError):
                return value

        return process


class Role(db.Model):
    __tablename__ = "roles"
    name = db.Column(db.String(32), primary_key=True)


class SchoolClass(db.Model):
    __tablename__ = "classes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), db.ForeignKey("roles.name"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class ClassMembership(db.Model):
    __tablename__ = "class_memberships"
    __table_args__ = (db.UniqueConstraint("user_id", "class_id", name="uq_membership_user_class"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    is_teacher = db.Column(db.Boolean, nullable=False, default=False)


class ClassAdminGrant(db.Model):
    __tablename__ = "class_admin_grants"
    __table_args__ = (db.UniqueConstraint("admin_user_id", "class_id", name="uq_class_admin_grant"),)

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class ClassSubject(db.Model):
    __tablename__ = "class_subjects"
    __table_args__ = (
        db.UniqueConstraint("class_id", "normalized_name", name="uq_class_subject_name"),
        db.UniqueConstraint("class_id", "subject_key", name="uq_class_subject_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    subject_key = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    normalized_name = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="active", index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)


class TeacherSubjectAssignment(db.Model):
    __tablename__ = "teacher_subject_assignments"
    __table_args__ = (db.UniqueConstraint("teacher_id", "subject_id", name="uq_teacher_subject_assignment"),)

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("class_subjects.id"), nullable=False, index=True)
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)


class LoginSession(db.Model):
    __tablename__ = "sessions"
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class AuthToken(db.Model):
    """A server-revocable opaque credential; plaintext values never reach this table."""

    __tablename__ = "auth_tokens"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id = db.Column(db.String(64), db.ForeignKey("sessions.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(16), nullable=False, index=True)  # access or refresh
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    replaced_by_id = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"
    subject_key = db.Column(db.String(64), primary_key=True)
    failure_count = db.Column(db.Integer, nullable=False, default=0)
    window_started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    blocked_until = db.Column(db.DateTime(timezone=True), nullable=True)


class Material(db.Model):
    __tablename__ = "materials"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("class_subjects.id"), nullable=True, index=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(512), nullable=False)
    content_type = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeEntry(db.Model):
    __tablename__ = "knowledge_entries"
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String(36), db.ForeignKey("materials.id"), nullable=False, unique=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("class_subjects.id"), nullable=True, index=True)
    body_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeIndexGeneration(db.Model):
    __tablename__ = "knowledge_index_generations"
    __table_args__ = (
        db.UniqueConstraint("knowledge_entry_id", "generation", name="uq_entry_generation"),
        db.Index("uq_entry_current_generation", "knowledge_entry_id", unique=True,
                 postgresql_where=db.text("is_current"), sqlite_where=db.text("is_current = 1")),
    )

    id = db.Column(db.Integer, primary_key=True)
    knowledge_entry_id = db.Column(db.Integer, db.ForeignKey("knowledge_entries.id"), nullable=False, index=True)
    generation = db.Column(db.Integer, nullable=False)
    strategy = db.Column(db.String(32), nullable=False)
    preprocessing = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(16), nullable=False, default="building", index=True)
    is_current = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("embedding_profiles.id"), nullable=True)
    chunker_version = db.Column(db.String(64), nullable=False, default="legacy", server_default="legacy")
    tokenizer_version = db.Column(db.String(64), nullable=False, default="legacy", server_default="legacy")
    normalized_options = db.Column(db.JSON, nullable=False, default=dict, server_default="{}")
    source_hash = db.Column(db.String(64), nullable=True)
    base_current_id = db.Column(db.Integer, nullable=True)
    error_code = db.Column(db.String(64), nullable=True)


class KnowledgeChunk(db.Model):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        db.UniqueConstraint("generation_id", "chunk_index", name="uq_generation_chunk_index"),
        db.UniqueConstraint("id", "generation_id", name="uq_chunk_id_generation"),
        db.Index("ix_chunks_class_status", "class_id", "index_status"),
        db.Index("ix_chunks_class_subject_status", "class_id", "subject_id", "index_status"),
        db.Index("ix_chunks_entry_current", "knowledge_entry_id", "generation_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    generation_id = db.Column(db.Integer, db.ForeignKey("knowledge_index_generations.id"), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("class_subjects.id"), nullable=True, index=True)
    material_id = db.Column(db.String(36), db.ForeignKey("materials.id"), nullable=False, index=True)
    knowledge_entry_id = db.Column(db.Integer, db.ForeignKey("knowledge_entries.id"), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    start_offset = db.Column(db.Integer, nullable=False)
    end_offset = db.Column(db.Integer, nullable=False)
    offset_basis = db.Column(db.String(32), nullable=False, default="source")
    index_status = db.Column(db.String(16), nullable=False, default="building", index=True)
    embedding = db.Column(Vector(64), nullable=True)
    heading_context = db.Column(db.Text, nullable=False, default="", server_default="")
    source_spans = db.Column(db.JSON, nullable=False, default=list, server_default="[]")
    source_mapping = db.Column(db.JSON, nullable=False, default=list, server_default="[]")
    lexical_terms = db.Column(db.Text, nullable=False, default="", server_default="")
    searchable_active = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    provenance_version = db.Column(db.String(32), nullable=False, default="legacy", server_default="legacy")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class EmbeddingProfile(db.Model):
    __tablename__ = "embedding_profiles"
    __table_args__ = (
        db.UniqueConstraint("id", "dimensions", name="uq_profile_dimensions"),
        db.CheckConstraint("dimensions > 0 AND dimensions <= 16000", name="ck_profile_dimensions"),
    )
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(64), nullable=False)
    model = db.Column(db.String(255), nullable=False)
    revision = db.Column(db.String(128), nullable=False)
    dimensions = db.Column(db.Integer, nullable=False)
    processing_version = db.Column(db.String(255), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeEmbedding(db.Model):
    __tablename__ = "knowledge_embeddings"
    __table_args__ = (
        db.UniqueConstraint("chunk_id", "profile_id", name="uq_chunk_profile"),
        db.ForeignKeyConstraint(["profile_id", "dimensions"], ["embedding_profiles.id", "embedding_profiles.dimensions"], name="fk_chunk_embedding_profile_dimensions"),
        db.CheckConstraint("vector_dims(embedding) = dimensions", name="ck_chunk_embedding_dimensions").ddl_if(dialect="postgresql"),
        db.Index("ix_embeddings_profile_active", "profile_id", "is_active", "state", "chunk_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    chunk_id = db.Column(db.Integer, db.ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False)
    profile_id = db.Column(db.Integer, nullable=False)
    dimensions = db.Column(db.Integer, nullable=False)
    embedding = db.Column(Vector(), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    state = db.Column(db.String(16), nullable=False, default="building")


class KnowledgeChunkSentence(db.Model):
    __tablename__ = "knowledge_chunk_sentences"
    __table_args__ = (
        db.UniqueConstraint("chunk_id", "sequence", name="uq_chunk_sentence_sequence"),
        db.ForeignKeyConstraint(["chunk_id", "generation_id"], ["knowledge_chunks.id", "knowledge_chunks.generation_id"], ondelete="CASCADE", name="fk_sentence_chunk_generation"),
        db.CheckConstraint("working_start >= 0 AND working_end > working_start", name="ck_sentence_working_range"),
    )
    id = db.Column(db.Integer, primary_key=True)
    chunk_id = db.Column(db.Integer, nullable=False, index=True)
    generation_id = db.Column(db.Integer, nullable=False, index=True)
    sequence = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    working_start = db.Column(db.Integer, nullable=False)
    working_end = db.Column(db.Integer, nullable=False)
    source_spans = db.Column(db.JSON, nullable=False)


class KnowledgeSentenceEmbedding(db.Model):
    __tablename__ = "knowledge_sentence_embeddings"
    __table_args__ = (
        db.UniqueConstraint("sentence_id", "profile_id", name="uq_sentence_profile"),
        db.ForeignKeyConstraint(["profile_id", "dimensions"], ["embedding_profiles.id", "embedding_profiles.dimensions"], name="fk_sentence_embedding_profile_dimensions"),
        db.CheckConstraint("vector_dims(embedding) = dimensions", name="ck_sentence_embedding_dimensions").ddl_if(dialect="postgresql"),
        db.Index("ix_sentence_embeddings_profile_active", "profile_id", "is_active", "state", "sentence_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    sentence_id = db.Column(db.Integer, db.ForeignKey("knowledge_chunk_sentences.id", ondelete="CASCADE"), nullable=False)
    profile_id = db.Column(db.Integer, nullable=False)
    dimensions = db.Column(db.Integer, nullable=False)
    embedding = db.Column(Vector(), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    state = db.Column(db.String(16), nullable=False, default="building")


class SchemaMigration(db.Model):
    __tablename__ = "schema_migrations"
    version = db.Column(db.String(64), primary_key=True)
    applied_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)


class Assistant(db.Model):
    __tablename__ = "assistants"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)


class Skill(db.Model):
    __tablename__ = "skills"
    __table_args__ = (
        db.UniqueConstraint("class_id", "name", name="uq_skill_class_name"),
        db.UniqueConstraint("class_id", "seed_key", name="uq_skill_class_seed"),
        db.CheckConstraint("legacy_placeholder OR (class_id IS NOT NULL AND length(name) BETWEEN 1 AND 32 AND length(trigger_text) BETWEEN 1 AND 120 AND length(description) BETWEEN 1 AND 2000 AND length(source_text) <= 8000 AND length(subject_text) <= 32)", name="ck_skill_definition"),
        db.CheckConstraint("NOT legacy_placeholder OR NOT enabled", name="ck_skill_legacy_disabled"),
    )
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=True, index=True)
    trigger_text = db.Column(db.String(120), nullable=False, default="", server_default="")
    description = db.Column(db.Text, nullable=False, default="", server_default="")
    tools_json = db.Column(db.JSON, nullable=False, default=list, server_default="[]")
    source_text = db.Column(db.Text, nullable=False, default="", server_default="")
    subject_text = db.Column(db.String(32), nullable=False, default="", server_default="")
    enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    legacy_placeholder = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    seed_key = db.Column(db.String(64), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class TutorAgent(db.Model):
    __tablename__ = "tutor_agents"
    __table_args__ = (
        db.UniqueConstraint("class_id", "name", name="uq_agent_class_name"),
        db.UniqueConstraint("class_id", "seed_key", name="uq_agent_class_seed"),
        db.CheckConstraint("length(name) BETWEEN 1 AND 64 AND length(prompt) <= 2000", name="ck_agent_text_bounds"),
    )
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    prompt = db.Column(db.Text, nullable=False, default="", server_default="")
    enabled = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    seed_key = db.Column(db.String(64), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class TutorAgentSkill(db.Model):
    __tablename__ = "tutor_agent_skills"
    agent_id = db.Column(db.Integer, db.ForeignKey("tutor_agents.id", ondelete="CASCADE"), primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)


class TutorAgentMaterial(db.Model):
    __tablename__ = "tutor_agent_materials"
    agent_id = db.Column(db.Integer, db.ForeignKey("tutor_agents.id", ondelete="CASCADE"), primary_key=True)
    material_id = db.Column(db.String(36), db.ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True)


class Conversation(db.Model):
    __tablename__ = "conversations"
    __table_args__ = (db.Index("ix_conversation_owner_activity", "user_id", "class_id", "updated_at", "id"), db.CheckConstraint("mcp_attempt_count >= 0", name="ck_conversation_mcp_attempts"))
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey("tutor_agents.id"), nullable=False)
    title = db.Column(db.String(24), nullable=False, default="新的提问")
    mcp_attempt_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class Message(db.Model):
    __tablename__ = "messages"
    __table_args__ = (
        db.CheckConstraint("role IN ('user', 'assistant')", name="ck_message_role"),
        db.CheckConstraint("completion_state IN ('complete', 'interrupted')", name="ck_message_state"),
        db.Index("ix_message_conversation_order", "conversation_id", "id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    citations_json = db.Column(db.JSON, nullable=False, default=list)
    tool_calls_json = db.Column(db.JSON, nullable=False, default=list, server_default="[]")
    skill_name = db.Column(db.String(32), nullable=True)
    completion_state = db.Column(db.String(16), nullable=False, default="complete")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class MCPServer(db.Model):
    __tablename__ = "mcp_servers"
    __table_args__ = (db.UniqueConstraint("class_id", "name", name="uq_mcp_server_class_name"),)
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    base_url = db.Column(db.String(512), nullable=False)
    token_ciphertext = db.Column(db.Text, nullable=False)
    connected = db.Column(db.Boolean, nullable=False, default=False)
    operation_revision = db.Column(db.Integer, nullable=False, default=0)
    configuration_revision = db.Column(db.Integer, nullable=False, default=1)
    last_error_code = db.Column(db.String(64), nullable=True)
    connected_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class MCPTool(db.Model):
    __tablename__ = "mcp_tools"
    __table_args__ = (db.UniqueConstraint("server_id", "name", name="uq_mcp_tool_server_name"),)
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=False)
    input_schema = db.Column(db.JSON, nullable=False)
    declaration_hash = db.Column(db.String(64), nullable=False)


class SkillMCPBinding(db.Model):
    __tablename__ = "skill_mcp_bindings"
    __table_args__ = (db.UniqueConstraint("skill_id", "tool_ref", name="uq_skill_mcp_ref"),)
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_ref = db.Column(db.String(130), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True, index=True)
    configuration_revision = db.Column(db.Integer, nullable=False)
    declaration_hash = db.Column(db.String(64), nullable=False)


class MCPToolCall(db.Model):
    __tablename__ = "mcp_tool_calls"
    __table_args__ = (db.Index("ix_mcp_calls_class_order", "class_id", "id"),)
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True)
    server_name = db.Column(db.String(64), nullable=False)
    tool_ref = db.Column(db.String(130), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    user_message_id = db.Column(db.Integer, db.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    call_id = db.Column(db.String(64), nullable=False, unique=True)
    round = db.Column(db.Integer, nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False)
    reason_code = db.Column(db.String(64), nullable=True)
    summary = db.Column(db.String(200), nullable=False, default="")
    duration_ms = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
