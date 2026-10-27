import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Conversation, Message, Skill, TutorAgent, TutorAgentMaterial, User


def test_tutor_schema_constraints_and_indexes(app):
    with app.app_context():
        user = User.query.filter_by(role="student").first()
        agent = TutorAgent(class_id=user.class_id, name="schema agent")
        db.session.add(agent)
        db.session.commit()
        db.session.add(TutorAgent(class_id=user.class_id, name=agent.name))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        conversation = Conversation(class_id=user.class_id, user_id=user.id, agent_id=agent.id)
        db.session.add(conversation)
        db.session.commit()
        for fields in [{"role": "system"}, {"role": "assistant", "completion_state": "saved-ish"}]:
            db.session.add(Message(conversation_id=conversation.id, content="text", **fields))
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()
        assert TutorAgentMaterial.__table__.c.material_id.type.length == 36
        assert "ix_message_conversation_order" in {i["name"] for i in inspect(db.engine).get_indexes("messages")}
        assert "ix_conversation_owner_activity" in {i["name"] for i in inspect(db.engine).get_indexes("conversations")}


def test_new_skill_must_have_class_and_valid_definition(app):
    with app.app_context():
        db.session.add(Skill(name="invalid", legacy_placeholder=False))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        legacy = Skill(name="legacy preserved")
        db.session.add(legacy)
        db.session.commit()
        assert legacy.legacy_placeholder and not legacy.enabled and legacy.class_id is None


def test_original_skill_upgrade_is_additive_and_repeatable(app):
    from app.tutor_schema import prepare_tutor_upgrade, finish_tutor_upgrade, VERSION
    from app.models import SchemaMigration
    with app.app_context():
        db.session.execute(text("DROP TABLE skills"))
        db.session.execute(text("CREATE TABLE skills (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"))
        db.session.execute(text("INSERT INTO skills VALUES (71, 'old teacher placeholder')"))
        db.session.commit()
        for _ in range(2):
            prepare_tutor_upgrade()
            finish_tutor_upgrade()
        db.session.expire_all()
        legacy = db.session.get(Skill, 71)
        assert legacy.name == "old teacher placeholder" and legacy.class_id is None
        assert legacy.legacy_placeholder and not legacy.enabled
        assert db.session.get(SchemaMigration, VERSION)
        db.session.add(Skill(name="invalid", legacy_placeholder=False))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_demo_tutor_seed_does_not_override_teacher_edits(app):
    from app.tutor_seed import seed_tutor_data
    with app.app_context():
        agent = TutorAgent.query.filter(TutorAgent.seed_key.is_not(None)).first()
        assert agent
        original_count = TutorAgent.query.count()
        agent.prompt = "teacher edited"
        agent.enabled = False
        db.session.commit()
        for _ in range(2):
            seed_tutor_data()
        assert TutorAgent.query.count() == original_count
        assert agent.prompt == "teacher edited" and not agent.enabled


def test_non_demo_app_creates_no_tutor_seed(app):
    from app import create_app
    other = create_app({**app.config, "SQLALCHEMY_DATABASE_URI": "sqlite://", "SEED_DEMO_DATA": False})
    with other.app_context():
        assert TutorAgent.query.count() == 0 and Skill.query.count() == 0
        db.drop_all()


def test_material_delete_removes_binding_but_retains_history(app, client):
    from app.models import Material
    from .conftest import login
    login(client, "teacher_a", "teacher-password")
    with app.app_context():
        material = Material.query.filter_by(title="1 班数学示例材料").one()
        ident = material.id
        binding = TutorAgentMaterial.query.filter_by(material_id=ident).one()
        user = User.query.filter_by(username="linzimo").one()
        conversation = Conversation(class_id=user.class_id, user_id=user.id, agent_id=binding.agent_id)
        db.session.add(conversation)
        db.session.flush()
        message = Message(conversation_id=conversation.id, role="assistant", content="prior answer", citations_json=[{"material_id": ident}])
        db.session.add(message)
        db.session.commit()
        message_id = message.id
    assert client.delete(f"/api/classes/1/materials/{ident}").status_code == 204
    with app.app_context():
        assert not TutorAgentMaterial.query.filter_by(material_id=ident).first()
        assert db.session.get(Message, message_id).citations_json == [{"material_id": ident}]
