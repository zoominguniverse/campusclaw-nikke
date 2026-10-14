import io
import json
from pathlib import Path
from unittest.mock import patch

from app.chunking import normalize_options
from app.database import db
from app.models import KnowledgeChunk, KnowledgeEntry, KnowledgeIndexGeneration, Material
from app.providers import ProviderUnavailable

from .conftest import login


OPTIONS = {"strategy": "custom", "max_length": 100, "overlap_percent": 25, "separators": ["sentence"], "preprocess": {"remove_urls": True, "remove_emails": True, "collapse_whitespace": True}}


def teacher_material(app, client):
    login(client, "teacher_a", "teacher-password")
    with app.app_context():
        material = Material.query.filter_by(class_id=1).first()
        return material.id, material.subject_id


def test_pure_preview_complete_options_max10_and_authorization(app, client):
    material_id, subject_id = teacher_material(app, client)
    with app.app_context():
        before = (Material.query.count(), KnowledgeIndexGeneration.query.count(), KnowledgeChunk.query.count())
    with patch("app.indexing.embedding_client") as model:
        response = client.post("/api/classes/2/materials/chunk-preview", json={"subject_id": subject_id, "text": "句子。" * 600, "chunking": OPTIONS})
        existing = client.post(f"/api/classes/1/materials/{material_id}/chunk-preview", json={"chunking": OPTIONS})
    assert response.status_code == existing.status_code == 200
    assert response.get_json()["total"] > 10 and len(response.get_json()["samples"]) == 10
    assert response.get_json()["chunking"] == normalize_options(OPTIONS)
    model.assert_not_called()
    with app.app_context():
        assert before == (Material.query.count(), KnowledgeIndexGeneration.query.count(), KnowledgeChunk.query.count())
    assert client.post("/api/classes/1/materials/chunk-preview", json={"subject_id": subject_id, "text": "内容", "chunking": {"strategy": "custom", "max_length": 99}}).status_code == 400
    assert client.post("/api/classes/1/materials/chunk-preview", json={"subject_id": 99999, "text": "内容"}).status_code == 404
    login(client, "student_a1", "student-a-password")
    assert client.post(f"/api/classes/1/materials/{material_id}/chunk-preview", json={}).status_code == 403


def test_upload_preserves_source_file_on_provider_failure_and_retry_saved_options(app, client):
    _, subject_id = teacher_material(app, client)
    text = "😀保留原始材料。\r\nhttps://example.com 内容。"
    raw = text.encode("utf-8")
    with patch("app.indexing.embedding_client", side_effect=ProviderUnavailable("private-provider-error")):
        response = client.post("/api/classes/1/materials", data={"subject_id": str(subject_id), "file": (io.BytesIO(raw), "source.md"), "chunking": json.dumps(OPTIONS)}, content_type="multipart/form-data")
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["indexing"]["status"] == "failed"
    material_id = payload["material"]["id"]
    assert payload["material"]["source_saved"]
    assert payload["material"]["latest_attempt_status"] == "failed"
    assert payload["material"]["searchable_status"] == "unavailable"
    assert "private-provider" not in json.dumps(payload)
    with app.app_context():
        material = db.session.get(Material, material_id)
        assert (Path(app.config["UPLOAD_DIR"]) / material.storage_path).read_bytes() == raw
        assert KnowledgeEntry.query.filter_by(material_id=material_id).one().body_text == text
        assert not KnowledgeChunk.query.filter_by(material_id=material_id, searchable_active=True).first()
    retry = client.post(f"/api/classes/1/materials/{material_id}/reindex", json={})
    assert retry.status_code == 200 and retry.get_json()["indexing"]["status"] == "ready"
    assert retry.get_json()["material"]["chunking"] == normalize_options(OPTIONS)


def test_rebuild_failed_preserves_current_and_invalid_options_do_not_mutate(app, client):
    material_id, _ = teacher_material(app, client)
    with app.app_context():
        entry = KnowledgeEntry.query.filter_by(material_id=material_id).one()
        old_id = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).one().id
        before = KnowledgeIndexGeneration.query.count()
    bad = client.post(f"/api/classes/1/materials/{material_id}/reindex", json={"chunking": {"strategy": "custom", "overlap_percent": 51}})
    assert bad.status_code == 400
    with app.app_context():
        assert KnowledgeIndexGeneration.query.count() == before
    with patch("app.indexing.embedding_client", side_effect=ProviderUnavailable("offline")):
        failed = client.post(f"/api/classes/1/materials/{material_id}/reindex", json={"chunking": OPTIONS})
    assert failed.status_code == 200 and failed.get_json()["indexing"]["status"] == "failed"
    assert failed.get_json()["material"]["searchable_status"] == "ready"
    assert failed.get_json()["material"]["latest_attempt_status"] == "failed"
    with app.app_context():
        assert KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).one().id == old_id


def test_teacher_restore_student_and_unassigned_teacher_denied(app, client):
    material_id, _ = teacher_material(app, client)
    with app.app_context():
        entry = KnowledgeEntry.query.filter_by(material_id=material_id).one()
        old = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).one().id
    client.post(f"/api/classes/1/materials/{material_id}/reindex", json={"chunking": OPTIONS})
    restored = client.post(f"/api/classes/1/materials/{material_id}/restore", json={"generation_id": old})
    assert restored.status_code == 200 and restored.get_json()["material"]["generation_id"] == old
    login(client, "student_a1", "student-a-password")
    assert client.post(f"/api/classes/1/materials/{material_id}/restore", json={"generation_id": old}).status_code == 403
    login(client, "teacher_a2", "teacher-a2-password")
    assert client.post(f"/api/classes/1/materials/{material_id}/restore", json={"generation_id": old}).status_code == 404


def test_conflicting_publish_maps_to_409(app, client):
    material_id, _ = teacher_material(app, client)
    with patch("app.materials.reindex_entry", return_value={"status": "conflict", "error_code": "index_conflict"}):
        response = client.post(f"/api/classes/1/materials/{material_id}/reindex", json={})
    assert response.status_code == 409
    assert response.get_json()["indexing"]["status"] == "conflict"
