"""Optional integration checks for a disposable PostgreSQL/pgvector database.

Run this suite inside the Compose API container (or against another disposable
PostgreSQL target) with ``POSTGRES_INTEGRATION_URL`` set.  The regular unit
suite remains SQLite-compatible and skips this module.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from .conftest import DEMO_ACCOUNT_PASSWORDS


POSTGRES_URL = os.getenv("POSTGRES_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="POSTGRES_INTEGRATION_URL is not configured")


@pytest.fixture()
def postgres_app(tmp_path):
    from app import create_app
    from app.database import db

    if os.getenv("QUALITY_DISPOSABLE_DATABASE") != "true" or not make_url(POSTGRES_URL).database.startswith("quality_"):
        pytest.fail("PostgreSQL checks require an explicitly disposable quality_* database")
    # A fresh schema makes the fixtures reproducible across repeated test runs.
    from sqlalchemy import create_engine
    engine = create_engine(POSTGRES_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": POSTGRES_URL,
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "INITIALIZE_DATABASE": True,
            "SEED_DEMO_DATA": True,
            "DEMO_ACCOUNT_PASSWORDS": DEMO_ACCOUNT_PASSWORDS,
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


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


def test_evaluation_fixture_repeatability_and_real_provider_guard(postgres_app):
    import json
    from pathlib import Path
    from evaluation.run import execute, load_fixture
    from evaluation.report import summarize
    from app.models import KnowledgeEntry

    corpus = json.loads((Path(__file__).parents[1] / "evaluation/corpus-v1.json").read_text(encoding="utf-8"))
    with postgres_app.app_context():
        first = load_fixture(corpus)
        count = KnowledgeEntry.query.count()
        second = load_fixture(corpus)
        assert first == second
        assert KnowledgeEntry.query.count() == count
        results = execute(corpus, postgres_app.config, "release", ["keyword", "vector", "hybrid"])
        assert all(r["status"] == "incomplete" for r in results if r["mode"] != "keyword")
        assert all(r["chat_calls"] == 0 for r in results if r["mode"] == "keyword")
        report = summarize(corpus, results, {"embedding_provider": "deterministic"})
        assert not report["semantic_release_passed"]


def test_additive_legacy_migration_twice_preserves_source_file_and_64_vectors(postgres_app, tmp_path):
    import hashlib
    from app.database import db
    from app.models import KnowledgeEntry, KnowledgeChunk, KnowledgeIndexGeneration
    from app.retrieval_schema import GENERATION_COLUMNS, CHUNK_COLUMNS, prepare_legacy_tables, finish_retrieval_upgrade
    from sqlalchemy import inspect

    with postgres_app.app_context():
        entry = KnowledgeEntry.query.filter_by(class_id=1).first()
        original = (entry.id, entry.body_text)
        vectors = {c.id: c.embedding for c in KnowledgeChunk.query.all()}
        raw_file = tmp_path / "original.md"
        raw_file.write_bytes("😀原文\r\nhttps://example.com".encode("utf-8"))
        digest = hashlib.sha256(raw_file.read_bytes()).hexdigest()
        # Restore the pre-change retrieval schema shape on a disposable copy.
        db.session.execute(text("DROP TABLE knowledge_sentence_embeddings, knowledge_chunk_sentences, knowledge_embeddings, embedding_profiles CASCADE"))
        db.session.execute(text("DROP INDEX uq_entry_current_generation"))
        db.session.execute(text("ALTER TABLE knowledge_chunks DROP CONSTRAINT uq_chunk_id_generation"))
        for table, columns in [("knowledge_index_generations", GENERATION_COLUMNS), ("knowledge_chunks", CHUNK_COLUMNS)]:
            for column in columns:
                db.session.execute(text(f"ALTER TABLE {table} DROP COLUMN {column} CASCADE"))
        db.session.commit()
        db.session.expire_all()
        for _ in range(2):
            prepare_legacy_tables()
            db.create_all()
            finish_retrieval_upgrade()
        assert db.session.get(KnowledgeEntry, original[0]).body_text == original[1]
        assert hashlib.sha256(raw_file.read_bytes()).hexdigest() == digest
        assert {c.id: c.embedding for c in KnowledgeChunk.query.all()} == vectors
        assert set(GENERATION_COLUMNS) <= {c["name"] for c in inspect(db.engine).get_columns("knowledge_index_generations")}
        assert set(CHUNK_COLUMNS) <= {c["name"] for c in inspect(db.engine).get_columns("knowledge_chunks")}
        assert all(g.profile_id is None and g.chunker_version == "legacy" for g in KnowledgeIndexGeneration.query.all())


def test_multidimensional_vector_constraints_sentence_scope_and_current_uniqueness(postgres_app):
    from app.database import db
    from app.models import EmbeddingProfile, KnowledgeEntry, KnowledgeChunk, KnowledgeIndexGeneration, KnowledgeEmbedding, KnowledgeChunkSentence, KnowledgeSentenceEmbedding
    from sqlalchemy.exc import IntegrityError

    with postgres_app.app_context():
        chunk = KnowledgeChunk.query.first()
        old_vector = list(chunk.embedding)
        profiles = []
        for dimensions in (64, 8):
            profile = EmbeddingProfile(provider="test", model=f"fixture-{dimensions}", revision="1", dimensions=dimensions, processing_version="test", fingerprint=str(dimensions).zfill(64))
            db.session.add(profile)
            db.session.flush()
            profiles.append(profile)
            db.session.add(KnowledgeEmbedding(chunk_id=chunk.id, profile_id=profile.id, dimensions=dimensions, embedding=[1.] + [0.] * (dimensions - 1), state="ready", is_active=False))
        db.session.flush()
        assert chunk.embedding == old_vector
        sentence = KnowledgeChunkSentence(chunk_id=chunk.id, generation_id=chunk.generation_id, sequence=100, text=chunk.chunk_text, working_start=chunk.start_offset, working_end=chunk.end_offset, source_spans=[{"start": 0, "end": 1}])
        db.session.add(sentence)
        db.session.flush()
        db.session.add(KnowledgeSentenceEmbedding(sentence_id=sentence.id, profile_id=profiles[1].id, dimensions=8, embedding=[1.] * 8, state="ready", is_active=False))
        db.session.flush()
        other_chunk = KnowledgeChunk.query.filter(KnowledgeChunk.id != chunk.id).first()
        invalid = [
            KnowledgeEmbedding(chunk_id=other_chunk.id, profile_id=profiles[1].id, dimensions=8, embedding=[1.] * 7),
            KnowledgeEmbedding(chunk_id=other_chunk.id, profile_id=profiles[0].id, dimensions=8, embedding=[1.] * 8),
            KnowledgeEmbedding(chunk_id=chunk.id, profile_id=profiles[0].id, dimensions=64, embedding=[1.] * 64),
            KnowledgeSentenceEmbedding(sentence_id=sentence.id, profile_id=profiles[0].id, dimensions=64, embedding=[1.] * 8),
            KnowledgeChunkSentence(chunk_id=chunk.id, generation_id=other_chunk.generation_id, sequence=2, text="wrong", working_start=0, working_end=1, source_spans=[]),
            KnowledgeIndexGeneration(knowledge_entry_id=chunk.knowledge_entry_id, generation=999, strategy="auto", preprocessing={}, status="ready", is_current=True),
        ]
        for row in invalid:
            with pytest.raises(IntegrityError):
                with db.session.begin_nested():
                    db.session.add(row)
                    db.session.flush()
        db.session.rollback()


def test_active_terms_gin_plan_and_hnsw_dimension_guard(postgres_app):
    from app.database import db
    from app.models import KnowledgeChunk, EmbeddingProfile
    from app.retrieval_schema import install_profile_hnsw
    with postgres_app.app_context():
        chunk = KnowledgeChunk.query.first()
        db.session.execute(text("""INSERT INTO knowledge_chunks (generation_id, class_id, subject_id, material_id, knowledge_entry_id, chunk_index, chunk_text, start_offset, end_offset, offset_basis, index_status, created_at, lexical_terms, searchable_active)
            SELECT generation_id, class_id, subject_id, material_id, knowledge_entry_id, 1000 + n, 'background', 0, 10, 'source', 'ready', NOW(), CASE WHEN n = 10000 THEN 'qualityneedle' ELSE 'common background' END, TRUE
            FROM knowledge_chunks CROSS JOIN generate_series(1,10000) n WHERE id = :chunk_id"""), {"chunk_id": chunk.id})
        db.session.execute(text("ANALYZE knowledge_chunks"))
        plan = "\n".join(row[0] for row in db.session.execute(text("EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM knowledge_chunks WHERE searchable_active AND index_status = 'ready' AND to_tsvector('simple', lexical_terms) @@ to_tsquery('simple', 'qualityneedle')")))
        assert "ix_chunks_active_terms" in plan, plan
        for bad in ("1; SELECT", True, -1, 999999):
            with pytest.raises(ValueError):
                install_profile_hnsw(bad)
        profile = EmbeddingProfile(provider="test", model="large", revision="1", dimensions=2001, processing_version="test", fingerprint="large".ljust(64, "0"))
        db.session.add(profile)
        db.session.flush()
        with pytest.raises(ValueError, match="2000"):
            install_profile_hnsw(profile.id)
        db.session.rollback()


def test_legacy_restore_dry_run_and_transaction(postgres_app):
    from app.database import db
    from app.models import KnowledgeEntry, KnowledgeIndexGeneration, KnowledgeChunk
    from app.indexing import reindex_entry
    from app.generation_restore import restore_generation
    from app.retrieval_schema import source_hash
    with postgres_app.app_context():
        entry = KnowledgeEntry.query.first()
        old = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).one()
        old.source_hash = source_hash(entry.body_text)
        old_id, entry_id = old.id, entry.id
        db.session.commit()
        result = reindex_entry(entry)
        db.session.commit()
        new_id = result["generation_id"]
        assert restore_generation(entry_id, old_id, legacy_only=True, dry_run=True)["status"] == "dry_run"
        assert KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry_id, is_current=True).one().id == new_id
        restore_generation(entry_id, old_id, legacy_only=True)
        assert KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry_id, is_current=True).one().id == old_id
        assert all(c.embedding is not None for c in KnowledgeChunk.query.filter_by(generation_id=old_id))
        assert all(c.searchable_active for c in KnowledgeChunk.query.filter_by(generation_id=old_id))
        from app.retrieval import retrieve
        assert retrieve(class_id=entry.class_id,subject_ids={entry.subject_id},query=entry.body_text,mode='keyword')['hits']


def test_concurrent_publish_short_entry_locks_and_mid_build_failure(postgres_app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from unittest.mock import patch
    from app.database import db
    from app.indexing import index_entry
    from app.models import KnowledgeEntry, KnowledgeIndexGeneration, KnowledgeChunk, KnowledgeEmbedding
    from app.providers import DeterministicEmbeddingClient, ProviderUnavailable
    with postgres_app.app_context():
        entry = KnowledgeEntry.query.first()
        ident = entry.id
        old = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=ident, is_current=True).one().id
        db.session.commit()
    barrier = Barrier(2, timeout=10)
    class ConcurrentClient:
        def embed_batch(self, texts):
            barrier.wait()  # both reservations must release entry locks first
            return DeterministicEmbeddingClient(64).embed_batch(texts)
    def rebuild():
        with postgres_app.app_context():
            return index_entry(db.session.get(KnowledgeEntry, ident))
    with patch("app.indexing.embedding_client", return_value=ConcurrentClient()), ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(rebuild), pool.submit(rebuild)]
        responses = [future.result(timeout=30) for future in futures]
    assert sorted(r["status"] for r in responses) == ["conflict", "ready"]
    with postgres_app.app_context():
        current = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=ident, is_current=True).one()
        assert current.id != old
        assert all(not c.searchable_active for c in KnowledgeChunk.query.filter_by(generation_id=old))
        current_id = current.id
        postgres_app.config["EMBEDDING_BATCH_SIZE"] = 1
        class FailingClient:
            calls = 0
            def embed_batch(self, texts):
                self.calls += 1
                if self.calls == 2:
                    raise ProviderUnavailable("mid batch")
                return DeterministicEmbeddingClient(64).embed_batch(texts)
        entry = db.session.get(KnowledgeEntry, ident)
        with patch("app.indexing.embedding_client", return_value=FailingClient()):
            failed = index_entry(entry, {"strategy": "hierarchy"})
        # headingless single input deduplicates to one request; use a changed
        # heading source on a separate material to force multiple inputs below.
        if failed["status"] == "ready":
            current_id = failed["generation_id"]
        source = entry.body_text
        entry.body_text = "# context\n" + source
        db.session.commit()
        setup = index_entry(entry, {"strategy": "hierarchy"})
        assert setup["status"] == "ready"
        current_id = setup["generation_id"]
        with patch("app.indexing.embedding_client", return_value=FailingClient()):
            failed = index_entry(entry, {"strategy": "hierarchy"})
        assert failed["status"] == "failed"
        assert KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=ident, is_current=True).one().id == current_id
        assert not KnowledgeChunk.query.filter_by(generation_id=failed["generation_id"], searchable_active=True).first()
        assert not KnowledgeEmbedding.query.join(KnowledgeChunk).filter(KnowledgeChunk.generation_id == failed["generation_id"], KnowledgeEmbedding.is_active.is_(True)).first()
        assert db.session.get(KnowledgeEntry, ident).body_text == "# context\n" + source


def test_backfill_205_entries_filter_before_limit_resumable_dry_run_force(postgres_app):
    from unittest.mock import patch
    from app.database import db
    from app.models import Material, KnowledgeEntry, KnowledgeIndexGeneration
    from app.indexing import index_entry, backfill_entries
    from app.providers import ProviderUnavailable
    with postgres_app.app_context():
        sample = Material.query.first()
        added = []
        for n in range(205):
            material = Material(class_id=sample.class_id, subject_id=sample.subject_id, uploader_id=sample.uploader_id, title=f"batch-{n}", original_filename="batch.md", storage_path="seeded", content_type="text/plain")
            db.session.add(material)
            db.session.flush()
            entry = KnowledgeEntry(material_id=material.id, class_id=sample.class_id, subject_id=sample.subject_id, body_text=f"批量测试资料{n}。")
            db.session.add(entry)
            db.session.flush()
            added.append(entry.id)
        db.session.commit()
        for ident in added[:100]:
            index_entry(db.session.get(KnowledgeEntry, ident))
        with patch("app.indexing.embedding_client", side_effect=ProviderUnavailable("offline")):
            index_entry(db.session.get(KnowledgeEntry, added[100]))
        before = KnowledgeIndexGeneration.query.count()
        with patch("app.indexing.embedding_client") as provider:
            preview = backfill_entries(100, dry_run=True)
        provider.assert_not_called()
        assert preview["entries"][0]["entry_id"] == added[100] and preview["has_more"]
        assert KnowledgeIndexGeneration.query.count() == before and preview["estimated_vectors"] > 0
        first = backfill_entries(100)
        assert first["completed"] == 100 and first["failed"] == 0 and first["has_more"]
        second = backfill_entries(100, after=first["cursor"])
        assert second["completed"] == 5 and not second["has_more"]
        again = backfill_entries(100, after=second["cursor"])
        assert again["completed"] == 0
        forced = backfill_entries(2, after=added[0] - 1, force=True, dry_run=True)
        assert [r["entry_id"] for r in forced["entries"]] == added[:2]
        with patch("app.indexing.index_entry", return_value={"status": "failed", "error_code": "provider_unavailable"}):
            counted = backfill_entries(1, after=added[0] - 1, force=True)
        assert counted["failed"] == 1 and counted["completed"] == 0
        original_index = index_entry
        def injected(entry, *args, **kwargs):
            if entry.id == added[1]:
                raise ProviderUnavailable("injected exception")
            return original_index(entry, *args, **kwargs)
        with patch("app.indexing.index_entry", side_effect=injected):
            isolated = backfill_entries(3, after=added[0] - 1, force=True)
        assert isolated["completed"] == 2 and isolated["failed"] == 1
        assert all(KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=ident, is_current=True).count() == 1 for ident in added)


def test_postgres_terms_phrase_priority_stability_and_mixed_dimension_safety(postgres_app):
    from unittest.mock import patch
    from app.database import db
    from app.models import KnowledgeEntry, KnowledgeChunk, EmbeddingProfile, KnowledgeEmbedding
    from app.indexing import index_entry
    from app.retrieval import retrieve
    from .test_retrieval_quality_regressions import add_entry
    with postgres_app.app_context():
        fact = "细胞是生物体结构和功能的基本单位。"
        first = add_entry("学习背景。" + fact)
        second = add_entry("结构功能是细胞重要的性质，但这里只介绍功能。")
        third = add_entry("细胞在结构中的功能决定基本单位作用。")
        results = [index_entry(entry) for entry in (first, second, third)]
        with patch("app.retrieval.embedding_client") as provider:
            keywords = retrieve(class_id=1, query="结构 功能 基本单位", mode="keyword")
            exact = retrieve(class_id=1, query=fact, mode="keyword")
            again = retrieve(class_id=1, query=fact, mode="keyword")
        provider.assert_not_called()
        assert any(h["material_id"] == first.material_id for h in keywords["hits"])
        assert exact["hits"][0]["material_id"] == first.material_id
        assert [h["chunk_id"] for h in exact["hits"]] == [h["chunk_id"] for h in again["hits"]]
        hit = exact["hits"][0]
        assert first.body_text[hit["excerpt_start_offset"]:hit["excerpt_end_offset"]] == hit["excerpt"]
        profile = EmbeddingProfile(provider="fixture", model="mixed8", revision="1", dimensions=8, processing_version="test", fingerprint="mixed8".ljust(64, "0"))
        db.session.add(profile)
        db.session.flush()
        chunk = KnowledgeChunk.query.filter_by(generation_id=results[0]["generation_id"]).first()
        db.session.add(KnowledgeEmbedding(chunk_id=chunk.id, profile_id=profile.id, dimensions=8, embedding=[1.] * 8, state="ready", is_active=True))
        db.session.commit()
        vector = retrieve(class_id=1, query=fact, mode="vector")
        assert any(h["material_id"] == first.material_id for h in vector["hits"])
