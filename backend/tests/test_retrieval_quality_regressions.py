"""Failures established against the original implementation; never xfail release checks."""
from unittest.mock import patch

from app.chunking import chunk_text
from app.database import db
from app.indexing import backfill_entries, index_entry
from app.models import KnowledgeEntry, Material
from app.providers import DeterministicEmbeddingClient
from app.retrieval import retrieve


def add_entry(text):
    original = KnowledgeEntry.query.filter_by(class_id=1).first()
    material = Material(class_id=1, subject_id=original.subject_id, uploader_id=1,
                        title="检索回归", original_filename="regression.md", storage_path="seeded", content_type="text/plain")
    db.session.add(material)
    db.session.flush()
    entry = KnowledgeEntry(material_id=material.id, class_id=1, subject_id=original.subject_id, body_text=text)
    db.session.add(entry)
    db.session.flush()
    return entry


def test_excerpt_is_short_and_points_to_tail_hit(app):
    with app.app_context():
        source = "无关背景。" * 90 + "细胞是生物体结构和功能的基本单位。"
        entry = add_entry(source)
        index_entry(entry)
        db.session.commit()
        hit = retrieve(class_id=1, query="结构和功能", mode="keyword")["hits"][0]
        assert len(hit["excerpt"]) <= 160
        assert "结构和功能" in hit["excerpt"]
        assert source[hit["excerpt_start_offset"]:hit["excerpt_end_offset"]] == hit["excerpt"]


def test_distributed_keywords_recall_without_embedding(app):
    with app.app_context():
        entry = add_entry("细胞是生物体结构和功能的基本单位。")
        index_entry(entry)
        db.session.commit()
        with patch("app.retrieval.embedding_client") as provider:
            hits = retrieve(class_id=1, query="结构 功能 基本单位", mode="keyword")["hits"]
        assert hits and hits[0]["material_id"] == entry.material_id
        provider.assert_not_called()


def test_demo_hash_is_not_a_semantic_acceptance_provider():
    # An accurately recorded counterexample, NOT an expectation that hashing can
    # learn relations. Real-provider evaluations must refuse this provider.
    provider = DeterministicEmbeddingClient(64)
    assert provider.embed("老师帮助学生") == provider.embed("学生帮助老师")


def test_hierarchy_keeps_preamble():
    source = "前言必须索引。\n\n# 第一节\n正文。"
    chunks, _ = chunk_text(source, {"strategy": "hierarchy"})
    covered = {i for item in chunks for i in range(item.start_offset, item.end_offset)}
    assert all(i in covered for i, character in enumerate(source) if not character.isspace())


def test_trim_and_hierarchy_offsets_equal_source():
    for source, strategy in [("  😀正文。  \r\n", "auto"), ("# 标题\n" + "内容。" * 600, "hierarchy")]:
        chunks, _ = chunk_text(source, {"strategy": strategy})
        assert all(source[item.start_offset:item.end_offset] == item.text for item in chunks)


def test_backfill_does_not_count_failed_as_completed(app):
    with app.app_context():
        entry = add_entry("索引失败仍须保留原文。")
        db.session.commit()
        with patch("app.indexing.index_entry", return_value={"status": "failed"}):
            result = backfill_entries()
        assert result["completed"] == 0
        assert result["failed"] == 1
        assert db.session.get(KnowledgeEntry, entry.id).body_text == "索引失败仍须保留原文。"
