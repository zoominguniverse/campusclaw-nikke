from __future__ import annotations

from sqlalchemy import func
from flask import current_app

from .chunking import chunk_text
from .database import db
from .models import KnowledgeChunk, KnowledgeEntry, KnowledgeIndexGeneration, utc_now
from .providers import ProviderUnavailable, embedding_client


class IndexingFailed(RuntimeError):
    pass


def index_entry(entry: KnowledgeEntry, options: dict | None = None, *, replace: bool = False) -> dict:
    """Create a full generation before making it current, preserving prior ready data."""
    chunks, normalized = chunk_text(entry.body_text, options)
    if not chunks:
        raise IndexingFailed("material does not contain indexable text")
    next_generation = (db.session.query(func.max(KnowledgeIndexGeneration.generation)).filter_by(knowledge_entry_id=entry.id).scalar() or 0) + 1
    generation = KnowledgeIndexGeneration(
        knowledge_entry_id=entry.id,
        generation=next_generation,
        strategy=normalized["strategy"],
        preprocessing=normalized.get("preprocess", {}),
        status="building",
        is_current=False,
    )
    db.session.add(generation)
    db.session.flush()
    client = embedding_client()
    ready_chunks = 0
    failed_chunks = 0
    for index, item in enumerate(chunks, 1):
        record = KnowledgeChunk(
            generation_id=generation.id,
            class_id=entry.class_id,
            subject_id=entry.subject_id,
            material_id=entry.material_id,
            knowledge_entry_id=entry.id,
            chunk_index=index,
            chunk_text=item.text,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            offset_basis=item.offset_basis,
            index_status="building",
        )
        db.session.add(record)
        try:
            vector = client.embed(item.text)
            if len(vector) != current_app.config["EMBEDDING_DIMENSIONS"]:
                raise IndexingFailed("embedding dimension does not match configuration")
            record.embedding = vector
            record.index_status = "ready"
            ready_chunks += 1
        except (ProviderUnavailable, IndexingFailed):
            record.index_status = "failed"
            failed_chunks += 1
    if failed_chunks:
        generation.status = "failed"
        generation.completed_at = utc_now()
        db.session.flush()
        # Keep records for diagnostic state but do not make this generation visible to retrieval.
        return {"status": "failed", "ready_chunks": ready_chunks, "failed_chunks": failed_chunks, "generation_id": generation.id}

    KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).update(
        {KnowledgeIndexGeneration.is_current: False, KnowledgeIndexGeneration.status: "retired"}, synchronize_session=False
    )
    generation.status = "ready"
    generation.is_current = True
    generation.completed_at = utc_now()
    db.session.flush()
    return {"status": "ready", "ready_chunks": ready_chunks, "failed_chunks": 0, "generation_id": generation.id}


def reindex_entry(entry: KnowledgeEntry, options: dict | None = None) -> dict:
    return index_entry(entry, options, replace=True)


def backfill_entries(limit: int = 100) -> dict:
    entries = KnowledgeEntry.query.limit(limit).all()
    completed = failed = 0
    for entry in entries:
        if KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).first():
            continue
        try:
            index_entry(entry)
            completed += 1
        except (IndexingFailed, ProviderUnavailable):
            failed += 1
            db.session.rollback()
    db.session.commit()
    return {"completed": completed, "failed": failed}
