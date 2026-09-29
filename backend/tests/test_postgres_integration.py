"""Optional integration checks for a disposable PostgreSQL/pgvector database.

Run this suite inside the Compose API container (or against another disposable
PostgreSQL target) with ``POSTGRES_INTEGRATION_URL`` set.  The regular unit
suite remains SQLite-compatible and skips this module.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text


POSTGRES_URL = os.getenv("POSTGRES_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="POSTGRES_INTEGRATION_URL is not configured")


@pytest.fixture()
def postgres_app(tmp_path):
    from app import create_app
    from app.database import db

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": POSTGRES_URL,
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "INITIALIZE_DATABASE": True,
            "SEED_DEMO_DATA": True,
            "DEMO_TEACHER_PASSWORD": "teacher-password",
            "DEMO_TEACHER_B_PASSWORD": "teacher-b-password",
            "DEMO_STUDENT_A_PASSWORD": "student-a-password",
            "DEMO_STUDENT_A2_PASSWORD": "student-a2-password",
            "DEMO_STUDENT_B_PASSWORD": "student-b-password",
            "DEMO_STUDENT_B2_PASSWORD": "student-b2-password",
        }
    )
    yield app
    with app.app_context():
        db.session.remove()


def test_postgresql_retrieval_extensions_indexes_scope_threshold_and_reindex(postgres_app):
    from app.database import db
    from app.indexing import reindex_entry
    from app.models import KnowledgeChunk, KnowledgeEntry, KnowledgeIndexGeneration
    from app.retrieval import retrieve

    with postgres_app.app_context():
        extensions = {
            row[0]
            for row in db.session.execute(
                text("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm')")
            )
        }
        assert extensions == {"vector", "pg_trgm"}
        indexes = {
            row[0]
            for row in db.session.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE tablename = 'knowledge_chunks' "
                    "AND indexname IN ('ix_chunks_text_trgm', 'ix_chunks_embedding_cosine', 'ix_chunks_class_subject_status_ready')"
                )
            )
        }
        assert indexes == {"ix_chunks_text_trgm", "ix_chunks_embedding_cosine", "ix_chunks_class_subject_status_ready"}

        entry = KnowledgeEntry.query.filter_by(class_id=1).first()
        assert entry is not None
        phrase = entry.body_text
        assert retrieve(class_id=1, query=phrase, mode="keyword")["hits"]
        assert retrieve(class_id=1, query=phrase, mode="vector")["hits"]
        assert retrieve(class_id=1, query=phrase, mode="hybrid")["hits"]
        assert retrieve(class_id=1, query="B 班示例材料内容", mode="keyword")["hits"] == []
        assert retrieve(class_id=1, query="量子色动力学", mode="vector")["hits"] == []
        assert entry.subject_id is not None
        assert retrieve(class_id=1, subject_ids={entry.subject_id}, query=phrase, mode="hybrid")["hits"]
        assert retrieve(class_id=1, subject_ids=set(), query=phrase, mode="keyword")["hits"] == []

        old = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).one()
        result = reindex_entry(entry, {"strategy": "custom", "max_length": 100, "overlap_percent": 0})
        db.session.commit()
        assert result["status"] == "ready"
        current = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).one()
        assert current.id != old.id
        assert not db.session.get(KnowledgeIndexGeneration, old.id).is_current
        assert KnowledgeChunk.query.filter_by(generation_id=current.id, index_status="ready").count() > 0
        assert KnowledgeChunk.query.filter_by(generation_id=current.id, embedding=None).count() == 0
