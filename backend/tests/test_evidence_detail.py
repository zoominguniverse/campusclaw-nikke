from app.database import db
from app.indexing import index_entry
from app.models import KnowledgeChunk, KnowledgeEntry, Material, TeacherSubjectAssignment, User, ClassMembership
from app.retrieval import retrieve

from .conftest import login
from .test_retrieval_quality_regressions import add_entry


def test_evidence_detail_complete_scope_revocation_source_hash_and_delete(app, client):
    with app.app_context():
        entry = add_entry("😀原文。\n# 标题\n来源定位内容。")
        result = index_entry(entry, {"strategy": "hierarchy"})
        entry_id, material_id = entry.id, entry.material_id
        chunk = KnowledgeChunk.query.filter_by(generation_id=result["generation_id"]).order_by(KnowledgeChunk.chunk_index.desc()).first()
        chunk_id = chunk.id
        hit = next(h for h in retrieve(class_id=1, query="来源定位", mode="keyword")["hits"] if h["material_id"] == material_id)
        other = KnowledgeChunk.query.filter_by(class_id=2).first().id
    login(client, "teacher_a", "teacher-password")
    url = f"/api/classes/1/knowledge/chunks/{chunk_id}?source_hash={hit['source_hash']}"
    response = client.get(url)
    assert response.status_code == 200
    detail = response.get_json()["evidence"]
    assert detail["chunk_text"] and detail["heading_context"] == "# 标题"
    assert detail["source_mapping"] and detail["offset_unit"] == "unicode_code_point"
    assert "embedding" not in detail and "API_KEY" not in str(detail)
    assert client.get(f"/api/classes/2/knowledge/chunks/{other}").status_code == 404
    with app.app_context():
        teacher = User.query.filter_by(username="linzimo").one()
        assignment = TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id, subject_id=hit["subject_id"]).one()
        assignment.is_active = False
        db.session.commit()
    assert client.get(url).status_code == 404
    login(client, "student_a1", "student-a-password")
    with app.app_context():
        db.session.get(KnowledgeEntry, entry_id).body_text += "原文变更。"
        db.session.commit()
    changed = client.get(url)
    assert changed.status_code == 409 and changed.get_json()["code"] == "source_changed"
    with app.app_context():
        db.session.get(KnowledgeEntry, entry_id).body_text = "😀原文。\n# 标题\n来源定位内容。"
        db.session.commit()
    # Revoking student class membership also prevents retrieval/capability reads.
    with app.app_context():
        student = User.query.filter_by(username="zhouchengxi").one()
        ClassMembership.query.filter_by(user_id=student.id, class_id=1).delete()
        db.session.commit()
    assert client.get(url).status_code == 404
    assert client.post("/api/classes/1/knowledge/retrieve", json={"query": "来源定位", "mode": "keyword"}).status_code == 403


def test_deleted_evidence_and_legacy_source_do_not_fake_mapping(app, client):
    login(client, "student_a1", "student-a-password")
    with app.app_context():
        chunk = KnowledgeChunk.query.filter_by(class_id=1).first()
        ident = chunk.id
        chunk.provenance_version = "legacy"
        chunk.source_spans = [{"start": 1000000, "end": 1000001}]
        db.session.commit()
    response = client.get(f"/api/classes/1/knowledge/chunks/{ident}")
    assert response.status_code == 200
    assert response.get_json()["evidence"]["source_spans"] == []
    assert response.get_json()["evidence"]["source_mapping"] == []
    with app.app_context():
        KnowledgeChunk.query.filter_by(id=ident).delete()
        db.session.commit()
    assert client.get(f"/api/classes/1/knowledge/chunks/{ident}").status_code == 404
