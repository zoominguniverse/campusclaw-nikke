import io
from pathlib import Path
from unittest.mock import patch

from app.database import db, initialize_database
from app.models import ClassSubject, KnowledgeChunk, KnowledgeEntry, Material, TeacherSubjectAssignment, User
from app.retrieval import NO_EVIDENCE_MESSAGE

from .conftest import LEGACY_TEST_USERNAMES, login


def subject_id(app, class_id, key):
    with app.app_context():
        return ClassSubject.query.filter_by(class_id=class_id, subject_key=key).one().id


def test_seeded_roles_subjects_and_backfill_are_idempotent(app):
    with app.app_context():
        assert User.query.filter_by(role="super_admin").one().username == LEGACY_TEST_USERNAMES["super_admin"]
        assert User.query.filter_by(username=LEGACY_TEST_USERNAMES["class_admin_a"], role="class_admin").one()
        math = ClassSubject.query.filter_by(class_id=1, subject_key="mathematics").one()
        language = ClassSubject.query.filter_by(class_id=1, subject_key="language").one()
        teacher_a = User.query.filter_by(username=LEGACY_TEST_USERNAMES["teacher_a"]).one()
        teacher_a2 = User.query.filter_by(username=LEGACY_TEST_USERNAMES["teacher_a2"]).one()
        assert TeacherSubjectAssignment.query.filter_by(teacher_id=teacher_a.id, subject_id=math.id, is_active=True).one()
        assert TeacherSubjectAssignment.query.filter_by(teacher_id=teacher_a2.id, subject_id=language.id, is_active=True).one()
        before = (ClassSubject.query.count(), Material.query.count(), KnowledgeEntry.query.count(), KnowledgeChunk.query.count())
        initialize_database()
        assert (ClassSubject.query.count(), Material.query.count(), KnowledgeEntry.query.count(), KnowledgeChunk.query.count()) == before
        assert all(item.subject_id is not None for item in Material.query.all())
        assert all(item.subject_id is not None for item in KnowledgeEntry.query.all())
        assert all(item.subject_id is not None for item in KnowledgeChunk.query.all())


def test_super_admin_and_class_admin_management_boundaries(app, client):
    super_token = login(client, "super_admin", "super-admin-password")
    created = client.post(
        "/api/admin/class-admins",
        json={"username": "head_b", "password": "head-b-password", "class_id": 2},
        headers={"X-CSRF-Token": super_token},
    )
    assert created.status_code == 201
    head_client = app.test_client()
    head_token = login(head_client, "class_admin_a", "class-admin-a-password")
    denied = head_client.post("/api/admin/class-admins", json={"username": "bad", "password": "bad", "class_id": 2}, headers={"X-CSRF-Token": head_token})
    assert denied.status_code == 403
    subject = head_client.post("/api/classes/1/subjects", json={"name": "地理", "key": "geography"}, headers={"X-CSRF-Token": head_token})
    assert subject.status_code == 201
    cross = head_client.post("/api/classes/2/subjects", json={"name": "化学"}, headers={"X-CSRF-Token": head_token})
    assert cross.status_code == 403


def test_teacher_subject_material_boundary_and_student_read_access(app, client):
    language = subject_id(app, 1, "language")
    math = subject_id(app, 1, "mathematics")
    teacher_math = login(client, "teacher_a", "teacher-password")
    forbidden = client.post(
        "/api/classes/1/materials",
        data={"subject_id": str(language), "file": (io.BytesIO("语文独有证据".encode()), "language.txt")},
        headers={"X-CSRF-Token": teacher_math},
    )
    assert forbidden.status_code == 400
    assert client.post("/api/classes/1/materials", data={"file": (io.BytesIO(b"missing subject"), "missing.txt")}, headers={"X-CSRF-Token": teacher_math}).status_code == 400
    language_teacher = app.test_client()
    language_token = login(language_teacher, "teacher_a2", "teacher-a2-password")
    created = language_teacher.post(
        "/api/classes/2/materials",
        data={"subject_id": str(language), "file": (io.BytesIO("语文独有证据".encode()), "language.txt")},
        headers={"X-CSRF-Token": language_token},
    )
    assert created.status_code == 201
    material = created.get_json()["material"]
    assert material["subject_id"] == language
    with app.app_context():
        stored = db.session.get(Material, material["id"])
        assert Path(stored.storage_path).parts[-3:-1] == ("1", str(language))
        entry = KnowledgeEntry.query.filter_by(material_id=stored.id).one()
        assert entry.subject_id == language
        assert all(chunk.subject_id == language for chunk in KnowledgeChunk.query.filter_by(knowledge_entry_id=entry.id).all())
    denied_preview = client.get(f"/api/classes/1/materials/{material['id']}")
    assert denied_preview.status_code == 404
    student = app.test_client()
    login(student, "student_a1", "student-a-password")
    listing = student.get("/api/classes/1/materials").get_json()["items"]
    assert {item["subject_id"] for item in listing} >= {math, language}
    assert student.get(f"/api/classes/1/materials/{material['id']}").status_code == 200
    assert student.delete(f"/api/classes/1/materials/{material['id']}", headers={"X-CSRF-Token": "not-valid"}).status_code == 403


def test_subject_scoped_retrieval_and_answer_citations(app, client):
    language = subject_id(app, 1, "language")
    teacher = app.test_client()
    token = login(teacher, "teacher_a2", "teacher-a2-password")
    uploaded = teacher.post(
        "/api/classes/1/materials",
        data={"subject_id": str(language), "file": (io.BytesIO("语言学专属关键词".encode()), "evidence.txt")},
        headers={"X-CSRF-Token": token},
    )
    assert uploaded.status_code == 201
    math_teacher = app.test_client()
    login(math_teacher, "teacher_a", "teacher-password")
    hidden = math_teacher.post("/api/classes/1/knowledge/retrieve", json={"query": "语言学专属关键词", "mode": "keyword"})
    assert hidden.status_code == 200
    assert hidden.get_json() == {"hits": [], "message": NO_EVIDENCE_MESSAGE, "mode": "keyword"}
    student = app.test_client()
    login(student, "student_a1", "student-a-password")
    found = student.post("/api/classes/1/knowledge/retrieve", json={"query": "语言学专属关键词", "mode": "keyword"})
    assert found.status_code == 200
    assert found.get_json()["hits"][0]["subject_id"] == language
    assert found.get_json()["hits"][0]["subject_name"] == "语文"
    with patch("app.answers.chat_client") as chat:
        chat.return_value.answer.return_value = "答案依据 [1]"
        answer = student.post("/api/classes/1/knowledge/ask", json={"question": "语言学专属关键词"})
    assert answer.status_code == 200
    assert answer.get_json()["citations"][0]["subject_id"] == language
    restricted = math_teacher.post("/api/classes/1/knowledge/ask", json={"question": "语言学专属关键词"})
    assert restricted.get_json() == {"answer": NO_EVIDENCE_MESSAGE, "citations": []}


def test_subject_deletion_conflict_and_revocation_take_effect_immediately(app, client):
    language = subject_id(app, 1, "language")
    language_teacher = app.test_client()
    token = login(language_teacher, "teacher_a2", "teacher-a2-password")
    created = language_teacher.post(
        "/api/classes/1/materials",
        data={"subject_id": str(language), "file": (io.BytesIO("撤销后不应泄露".encode()), "revoke.txt")},
        headers={"X-CSRF-Token": token},
    )
    assert created.status_code == 201
    head = app.test_client()
    head_token = login(head, "class_admin_a", "class-admin-a-password")
    assert head.delete(f"/api/classes/1/subjects/{language}", headers={"X-CSRF-Token": head_token}).status_code == 409
    with app.app_context():
        teacher_id = User.query.filter_by(username=LEGACY_TEST_USERNAMES["teacher_a2"]).one().id
    assert head.delete(f"/api/classes/1/subjects/{language}/teachers/{teacher_id}", headers={"X-CSRF-Token": head_token}).status_code == 204
    assert language_teacher.get(f"/api/classes/1/materials/{created.get_json()['material']['id']}").status_code == 404
    assert language_teacher.post("/api/classes/1/knowledge/retrieve", json={"query": "撤销后不应泄露", "mode": "keyword"}).get_json()["hits"] == []
    student = app.test_client()
    login(student, "student_a1", "student-a-password")
    assert student.get(f"/api/classes/1/materials/{created.get_json()['material']['id']}").status_code == 200
