import threading
import os
import json
import subprocess
import sys
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import inspect, text

from .test_postgres_integration import postgres_app, pytestmark
from app.extensions import db
from app.models import Conversation, Message, TutorAgent, Material, TutorAgentMaterial, User
from app.tutor_stream import GenerationLock
import pytest


def test_cross_connection_advisory_lock_and_independent_conversations(postgres_app):
    with postgres_app.app_context():
        first = GenerationLock(10001)
        assert first.acquire()
        def contender(ident):
            with postgres_app.app_context():
                lock = GenerationLock(ident)
                try:
                    return lock.acquire()
                finally:
                    lock.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            assert not executor.submit(contender, 10001).result()
            assert executor.submit(contender, 10002).result()
        assert db.session.execute(text("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted")).scalar() == 1
        first.close()
        assert contender(10001)
        assert db.session.execute(text("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted")).scalar() == 0


def test_postgres_material_cascade_preserves_history(postgres_app):
    with postgres_app.app_context():
        agent = TutorAgent.query.filter_by(class_id=1).first()
        original = Material.query.filter_by(class_id=1).first()
        material = Material(class_id=original.class_id, subject_id=original.subject_id, uploader_id=original.uploader_id,
                            title="无索引绑定级联测试", original_filename="cascade.txt", storage_path="seeded", content_type="text/plain")
        db.session.add(material)
        db.session.flush()
        db.session.add(TutorAgentMaterial(agent_id=agent.id, material_id=material.id))
        user = User.query.filter_by(username="zhouchengxi").one()
        conversation = Conversation(class_id=1, user_id=user.id, agent_id=agent.id)
        db.session.add(conversation)
        db.session.flush()
        snapshot = [{"material_id": material.id, "material_title": material.title, "chunk_id": 1, "generation_id": 1}]
        message = Message(conversation_id=conversation.id, role="assistant", content="历史", citations_json=snapshot)
        db.session.add(message)
        db.session.commit()
        material_id, message_id = material.id, message.id
        # Direct DB deletion exercises the binding FK even outside the handler.
        db.session.execute(text("DELETE FROM materials WHERE id=:id"), {"id": material_id})
        db.session.commit()
        assert TutorAgentMaterial.query.filter_by(material_id=material_id).count() == 0
        assert db.session.get(Message, message_id).citations_json == snapshot


def test_postgres_old_skills_upgrade_twice_without_changing_other_data(postgres_app):
    from app.database import initialize_database
    from app.models import Skill, SchemaMigration
    with postgres_app.app_context():
        before = {table: db.session.execute(text(f"SELECT count(*) FROM {table}")).scalar() for table in ["users", "materials", "knowledge_chunks", "knowledge_sentence_embeddings"]}
        for table in ["mcp_tool_calls", "skill_mcp_bindings", "mcp_tools", "mcp_servers", "messages", "conversations", "tutor_agent_skills", "tutor_agent_materials", "tutor_agents", "skills"]:
            db.session.execute(text(f"DROP TABLE {table}"))
        db.session.execute(text("CREATE TABLE skills (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL)"))
        db.session.execute(text("INSERT INTO skills (id,name) VALUES (900,'旧占位技能')"))
        db.session.execute(text("SELECT setval('skills_id_seq', 900)"))
        db.session.commit()
        initialize_database()
        initialize_database()
        legacy = db.session.get(Skill, 900)
        assert legacy.name == "旧占位技能" and legacy.class_id is None and not legacy.enabled and legacy.legacy_placeholder
        assert {table: db.session.execute(text(f"SELECT count(*) FROM {table}")).scalar() for table in before} == before
        assert {row["name"] for row in inspect(db.engine).get_check_constraints("skills")} >= {"ck_skill_definition", "ck_skill_legacy_disabled"}
        assert db.session.get(SchemaMigration, "20261014_tutor_conversations")


@pytest.mark.skipif(not os.getenv("PREVIOUS_BACKEND_DIR"), reason="previous Git revision is required for rollback rehearsal")
def test_previous_service_runs_on_upgraded_database_and_preserves_new_history(postgres_app):
    client = postgres_app.test_client()
    token = client.post("/api/auth/login", json={"username": "zhouchengxi", "password": "student-a-password"}).json["access_token"]
    with postgres_app.app_context():
        agent = TutorAgent.query.filter_by(class_id=1).first()
        user = User.query.filter_by(username="zhouchengxi").one()
        conv = Conversation(class_id=1, user_id=user.id, agent_id=agent.id, title="回滚保留历史")
        db.session.add(conv)
        db.session.flush()
        db.session.add(Message(conversation_id=conv.id, role="assistant", content="新版本历史应保留", citations_json=[]))
        db.session.commit()
        tables = ["materials", "knowledge_entries", "knowledge_chunks", "knowledge_embeddings", "knowledge_sentence_embeddings", "embedding_profiles", "auth_tokens", "sessions", "conversations", "messages"]
        before = {table: db.session.execute(text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY 1")).scalars().all() for table in tables}
        material_id = Material.query.filter_by(class_id=1).first().id
    script = '''import json, os
from app import create_app
app = create_app({"INITIALIZE_DATABASE":False,"SEED_DEMO_DATA":False})
client=app.test_client()
headers={"Authorization":"Bearer "+os.environ["ROLLBACK_ACCESS_TOKEN"]}
results={}
results["identity"]=client.get("/api/auth/me",headers=headers).status_code
results["material"]=client.get("/api/classes/1/materials/"+os.environ["ROLLBACK_MATERIAL_ID"],headers=headers).status_code
r=client.post("/api/classes/1/knowledge/retrieve",headers=headers,json={"query":"数学","mode":"hybrid"})
results["retrieval"]=r.status_code
results["retrieval_error"]=r.json.get("error")
r=client.post("/api/classes/1/knowledge/ask",headers=headers,json={"question":"数学"})
results["answer"]=r.status_code
results["answer_error"]=r.json.get("error")
print(json.dumps(results))
'''
    environment = dict(os.environ, PYTHONPATH=os.environ["PREVIOUS_BACKEND_DIR"], ROLLBACK_ACCESS_TOKEN=token,
        ROLLBACK_MATERIAL_ID=material_id, DATABASE_URL=postgres_app.config["SQLALCHEMY_DATABASE_URI"],
        SECRET_KEY=postgres_app.config["SECRET_KEY"], AUTH_TOKEN_SECRET=postgres_app.config["AUTH_TOKEN_SECRET"],
        INITIALIZE_DATABASE="false", SEED_DEMO_DATA="false", UPLOAD_DIR="/tmp/previous-tutor-uploads")
    # The archived source mount is read-only; the old tokenizer writes its
    # cache next to its source. Run an unchanged copy in a disposable directory.
    with tempfile.TemporaryDirectory(prefix="tutor-rollback-") as directory:
        previous = os.path.join(directory, "backend")
        shutil.copytree(os.environ["PREVIOUS_BACKEND_DIR"], previous)
        environment["PYTHONPATH"] = previous
        result = subprocess.run([sys.executable, "-c", script], cwd=previous, env=environment, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"identity": 200, "material": 200, "retrieval": 200, "answer": 200, "retrieval_error": None, "answer_error": None}, result.stderr
    with postgres_app.app_context():
        db.session.remove()
        after = {table: db.session.execute(text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY 1")).scalars().all() for table in tables}
        assert after == before
