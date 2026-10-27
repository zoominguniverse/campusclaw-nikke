import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import MCPServer, MCPTool, SkillMCPBinding, MCPToolCall, Conversation, Message, Skill, User, TutorAgent, SchemaMigration

def check_schema(app):
    with app.app_context():
        user = User.query.filter_by(username="linzimo").one()
        server = MCPServer(class_id=1, name="unique", base_url="http://mcp-demo:8090", token_ciphertext="cipher", created_by=user.id, updated_by=user.id)
        db.session.add(server); db.session.commit()
        db.session.add(MCPServer(class_id=1, name="unique", base_url=server.base_url, token_ciphertext="cipher", created_by=user.id, updated_by=user.id))
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()
        db.session.add(MCPServer(class_id=2, name="unique", base_url=server.base_url, token_ciphertext="cipher", created_by=user.id, updated_by=user.id)); db.session.commit()
        skill = Skill.query.filter_by(class_id=1, legacy_placeholder=False).first()
        agent = TutorAgent.query.filter_by(class_id=1).first()
        conversation = Conversation(class_id=1, user_id=user.id, agent_id=agent.id)
        db.session.add(conversation); db.session.flush()
        message = Message(conversation_id=conversation.id, role="user", content="old question")
        db.session.add(message); db.session.flush()
        binding = SkillMCPBinding(skill_id=skill.id, tool_ref="formula_hint@unique", server_id=server.id, configuration_revision=1, declaration_hash="a" * 64)
        audit = MCPToolCall(class_id=1, server_id=server.id, server_name="unique", tool_ref=binding.tool_ref, user_id=user.id, conversation_id=conversation.id, user_message_id=message.id, call_id="schema-call", round=1, sequence=1, status="ok", summary="safe hint")
        db.session.add_all([binding, audit]); db.session.commit()
        assert conversation.mcp_attempt_count == 0 and message.tool_calls_json == []
        if db.engine.dialect.name == "sqlite":
            # SQLite test fixture defaults FK off; enable it before direct deletion.
            db.session.execute(text("PRAGMA foreign_keys=ON")); db.session.commit()
        identifier = server.id
        db.session.execute(text("DELETE FROM mcp_servers WHERE id=:id"), {"id": identifier}); db.session.commit(); db.session.expire_all()
        assert binding.server_id is None and audit.server_id is None and audit.server_name == "unique" and audit.summary == "safe hint"
        conversation.mcp_attempt_count = -1
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()

def test_mcp_schema_constraints(app):
    check_schema(app)

def check_upgrade(app):
    from app.database import initialize_database
    with app.app_context():
        user = User.query.filter_by(username="zhouchengxi").one()
        agent = TutorAgent.query.filter_by(class_id=1).first()
        conversation = Conversation(class_id=1, user_id=user.id, agent_id=agent.id)
        db.session.add(conversation); db.session.flush()
        db.session.add(Message(conversation_id=conversation.id, role="assistant", content="旧辅导正文", citations_json=[])); db.session.commit()
        tables = ["materials", "knowledge_chunks", "auth_tokens", "sessions", "class_memberships", "teacher_subject_assignments"]
        before = {t: db.session.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tables}
        # Simulate the lesson-five columns while retaining actual rows and relations.
        if db.engine.dialect.name == "postgresql":
            db.session.execute(text("ALTER TABLE conversations DROP COLUMN mcp_attempt_count CASCADE"))
        else:
            # SQLite DROP COLUMN cannot remove a table-level CHECK. Rebuild only
            # this test's conversation table while foreign keys are disabled.
            db.session.execute(text("PRAGMA foreign_keys=OFF"))
            db.session.execute(text("CREATE TABLE old_conversations AS SELECT id,class_id,user_id,agent_id,title,created_at,updated_at FROM conversations"))
            db.session.execute(text("DROP TABLE conversations"))
            db.session.execute(text("ALTER TABLE old_conversations RENAME TO conversations"))
        db.session.execute(text("ALTER TABLE messages DROP COLUMN tool_calls_json")); db.session.commit()
        for _ in range(2): initialize_database()
        db.session.expire_all()
        assert db.session.get(Conversation, conversation.id).mcp_attempt_count == 0
        assert Message.query.filter_by(content="旧辅导正文").one().tool_calls_json == []
        assert {t: db.session.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tables} == before
        assert db.session.get(SchemaMigration, "20261021_mcp_tools")

def test_lesson_five_upgrade_twice(app):
    check_upgrade(app)
