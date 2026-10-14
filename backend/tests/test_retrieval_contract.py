from copy import deepcopy
import json

import pytest

from app.config import validate_retrieval_config
from app.database import db
from app.models import KnowledgeChunk, KnowledgeEntry, KnowledgeIndexGeneration
from app.profiles import profile_identity
from app.retrieval import retrieve

from .conftest import login


def test_multidimensional_configuration_demo_release_and_secret_validation(app):
    config = deepcopy(app.config)
    config["EMBEDDING_DIMENSIONS"] = 1024
    validate_retrieval_config(config)
    for invalid in (0, True, 16001):
        config["EMBEDDING_DIMENSIONS"] = invalid
        with pytest.raises(RuntimeError):
            validate_retrieval_config(config)
    config = deepcopy(app.config)
    config["SEMANTIC_RELEASE"] = True
    with pytest.raises(RuntimeError, match="real embedding"):
        validate_retrieval_config(config)
    config = deepcopy(app.config)
    config.update(EMBEDDING_PROVIDER="openai-compatible", EMBEDDING_API_URL="https://key@model.example/v1", EMBEDDING_API_KEY="secret")
    with pytest.raises(RuntimeError, match="base URL") as error:
        validate_retrieval_config(config)
    assert "secret" not in str(error.value) and "key@" not in str(error.value)


def test_profile_identity_changes_model_revision_dimension_and_processing(app):
    config = deepcopy(app.config)
    original = profile_identity(config)["fingerprint"]
    for key, value in [("EMBEDDING_MODEL", "other-model"), ("EMBEDDING_REVISION", "other-revision"), ("EMBEDDING_DIMENSIONS", 8), ("EMBEDDING_API_URL", "https://other-provider.example/v1")]:
        modified = {**config, key: value}
        assert profile_identity(modified)["fingerprint"] != original
    assert "API_KEY" not in json.dumps(profile_identity(config))


def test_capabilities_authenticated_scoped_and_legacy_provenance_honest(app, client):
    assert client.get("/api/classes/1/knowledge/capabilities").status_code == 401
    login(client, "student_a1", "student-a-password")
    response = client.get("/api/classes/2/knowledge/capabilities")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["demo_mode"] and not payload["semantic_ready"]
    assert "API_KEY" not in json.dumps(payload) and "API_URL" not in json.dumps(payload)
    with app.app_context():
        entry = KnowledgeEntry.query.filter_by(class_id=1).first()
        chunk = KnowledgeChunk.query.filter_by(knowledge_entry_id=entry.id).first()
        chunk.provenance_version = "legacy"
        chunk.source_spans = [{"start": 1000, "end": 1001}]
        db.session.commit()
        hit = retrieve(class_id=1, query=entry.body_text, mode="keyword")["hits"][0]
        assert hit["provenance_version"] == "legacy" and hit["source_spans"] == []
        assert hit["excerpt_start_offset"] is None


def test_material_dto_keeps_old_searchable_and_exposes_failed_attempt(app, client):
    login(client, "student_a1", "student-a-password")
    with app.app_context():
        entry = KnowledgeEntry.query.filter_by(class_id=1).first()
        material_id = entry.material_id
        generation = KnowledgeIndexGeneration(knowledge_entry_id=entry.id, generation=100,
            strategy="auto", preprocessing={}, status="failed", is_current=False, error_code="provider_unavailable")
        db.session.add(generation)
        db.session.commit()
    response = client.get(f"/api/classes/1/materials/{material_id}")
    payload = response.get_json()["material"]
    assert payload["index_status"] == "ready"
    assert payload["source_saved"] and payload["searchable_status"] == "ready"
    assert payload["latest_attempt_status"] == "failed"
    assert payload["latest_attempt_error_code"] == "provider_unavailable"


def test_capabilities_include_missing_current_and_respect_selected_scope(app, client):
    from .test_retrieval_quality_regressions import add_entry
    login(client, "teacher_a", "teacher-password")
    with app.app_context():
        entry = add_entry("已保存但没有current的来源。")
        db.session.commit()
        subject_id = entry.subject_id
    response = client.get(f"/api/classes/1/knowledge/capabilities?subject_id={subject_id}")
    assert response.get_json()["index_compatibility"] == "reindex_required"
    response = client.get('/api/classes/1/knowledge/capabilities?subject_id=999999')
    assert response.get_json()["index_compatibility"] == "empty"
    assert client.get('/api/classes/1/knowledge/capabilities?subject_id=bad').status_code == 400
