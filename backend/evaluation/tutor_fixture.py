"""Disposable lesson-five fixture, never imported by the production entrypoint."""
import os
from sqlalchemy import text
from sqlalchemy.engine import make_url

MCP_FIXTURE = os.getenv("MCP_DISPOSABLE_DATABASE") == "true"
FIXTURE_DATABASE = "mcp_test" if MCP_FIXTURE else "tutor_test"
if os.getenv("TUTOR_DISPOSABLE_DATABASE") != "true" or make_url(os.environ["DATABASE_URL"]).database != FIXTURE_DATABASE:
    raise RuntimeError("tutor fixture requires its isolated tutor_test database")

from tests.conftest import DEMO_ACCOUNT_PASSWORDS
from app import create_app
from app.database import db
from app.indexing import reindex_entry
from app.models import User, ClassMembership, ClassSubject, KnowledgeEntry, Material, TutorAgent, TutorAgentMaterial

app = create_app({"INITIALIZE_DATABASE": False, "SEED_DEMO_DATA": False})


@app.get("/tutor-test-info")
def test_info():
    if MCP_FIXTURE:
        return {"environment": "disposable-mcp-test", "database": "mcp_test", "fixture": "lesson-six-v1"}
    return {"environment": "disposable-tutor-test", "database": "tutor_test", "fixture": "lesson-five-v1"}


def initialize():
    from app.database import initialize_database
    app.config.update(SEED_DEMO_DATA=True, DEMO_ACCOUNT_PASSWORDS=DEMO_ACCOUNT_PASSWORDS)
    real = os.getenv("TUTOR_REAL_PROVIDER") == "true"
    if real and any(app.config[key] != "openai-compatible" for key in ("CHAT_PROVIDER", "EMBEDDING_PROVIDER")):
        raise RuntimeError("real tutor review requires both real providers")
    with app.app_context():
        initialize_database()
        first = User.query.filter_by(username="zhouchengxi").one()
        if not User.query.filter_by(username="tutor_classmate").first():
            from app.security import hash_password
            peer = User(username="tutor_classmate", class_id=first.class_id, role="student", password_hash=hash_password("classmate-test-password"))
            db.session.add(peer)
            db.session.flush()
            db.session.add(ClassMembership(user_id=peer.id, class_id=first.class_id, is_teacher=False))
        entry = KnowledgeEntry.query.filter_by(class_id=1).first()
        material = db.session.get(Material, entry.material_id)
        material.title = "数学课堂参考"
        entry.body_text = ("# 数学课堂参考\n去括号时，括号前是负号，括号内每一项都要变号；括号前是正号，括号内符号不变。\n分数加减先通分，再保持分母不变，对分子作相应运算。不要把分母直接相加。\n解题时先说明条件，每一步都要说明理由。" if real else
            "# 数学学习\n😀数学去括号时，要观察括号前的符号。分数运算前先检查分母和运算顺序。\n<script>alert('不可执行')</script>\n" + "学习时先说明条件，再检查每一步的理由。\n" * 80)
        db.session.commit()
        math_index = reindex_entry(entry, {"strategy": "hierarchy"})
        agent = TutorAgent.query.filter_by(class_id=1, seed_key="tutor-mathematics-v1").one()
        if not db.session.get(TutorAgentMaterial, (agent.id, material.id)):
            db.session.add(TutorAgentMaterial(agent_id=agent.id, material_id=material.id))
        if real:
            language = ClassSubject.query.filter_by(class_id=1, subject_key="language").one()
            teacher = User.query.filter_by(username="wangyuxin").one()
            lang_material = Material.query.filter_by(class_id=1, title="语文课堂参考").first()
            if not lang_material:
                lang_material = Material(class_id=1, subject_id=language.id, uploader_id=teacher.id, title="语文课堂参考", original_filename="language.txt", storage_path="seeded", content_type="text/plain")
                db.session.add(lang_material)
                db.session.flush()
            lang_entry = KnowledgeEntry.query.filter_by(material_id=lang_material.id).first()
            if not lang_entry:
                lang_entry = KnowledgeEntry(material_id=lang_material.id, class_id=1, subject_id=language.id)
                db.session.add(lang_entry)
            lang_entry.body_text = "# 语文课堂参考\n《春晓》：春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。\n古诗默写可先回想意象、韵脚和上下文，不直接照抄提示。\n阅读片段：雨停了，小宁扶起被风吹倒的树苗，给它培土。第二天，同学们也来照料树苗。结尾写道：每一份细小的关爱，都能让生命重新挺立。\n概括阅读中心时，结合人物行为、关键句与结尾，不只复述情节。"
            db.session.commit()
            result = reindex_entry(lang_entry, {"strategy": "hierarchy"})
            if result["status"] != "ready":
                raise RuntimeError("real language fixture indexing failed")
            lang_agent = TutorAgent.query.filter_by(class_id=1, seed_key="tutor-language-v1").one()
            if not db.session.get(TutorAgentMaterial, (lang_agent.id, lang_material.id)):
                db.session.add(TutorAgentMaterial(agent_id=lang_agent.id, material_id=lang_material.id))
        if real and math_index["status"] != "ready":
            raise RuntimeError("real math fixture indexing failed")
        readonly = "mcp_readonly" if MCP_FIXTURE else "tutor_readonly"
        db.session.execute(text(f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{readonly}') THEN CREATE ROLE {readonly} LOGIN PASSWORD 'disposable-readonly-only'; END IF; END $$"))
        db.session.execute(text(f"GRANT CONNECT ON DATABASE {FIXTURE_DATABASE} TO {readonly}"))
        db.session.execute(text(f"GRANT USAGE ON SCHEMA public TO {readonly}"))
        db.session.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {readonly}"))
        db.session.commit()


if __name__ == "__main__":
    import subprocess
    initialize()
    subprocess.run(["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--worker-class", "gthread", "--threads", "8", "--timeout", "180", "evaluation.tutor_fixture:app"], check=True)
