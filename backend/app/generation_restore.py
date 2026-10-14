"""Transactional generation restore shared by teacher and operator endpoints."""
from .extensions import db
from .models import KnowledgeEntry, KnowledgeChunk, KnowledgeIndexGeneration, KnowledgeEmbedding, KnowledgeChunkSentence, KnowledgeSentenceEmbedding
from .retrieval_schema import source_hash


def restore_generation(entry_id, generation_id, *, legacy_only=False, dry_run=False):
    entry = KnowledgeEntry.query.filter_by(id=entry_id).populate_existing().with_for_update().one_or_none()
    generation = KnowledgeIndexGeneration.query.filter_by(id=generation_id, knowledge_entry_id=entry_id).one_or_none()
    if not entry or not generation or generation.status not in {"ready", "retired"}:
        raise ValueError("a complete ready or retired generation is required")
    chunks = KnowledgeChunk.query.filter_by(generation_id=generation.id).all()
    if not chunks or any(c.index_status != "ready" for c in chunks) or generation.source_hash != source_hash(entry.body_text):
        raise ValueError("generation is incomplete or its source changed")
    if legacy_only and any(c.embedding is None or len(c.embedding) != 64 for c in chunks):
        raise ValueError("legacy rollback requires complete original 64-dimensional vectors")
    if generation.profile_id:
        for chunk in chunks:
            if not KnowledgeEmbedding.query.filter_by(chunk_id=chunk.id, profile_id=generation.profile_id, state="ready").first():
                raise ValueError("generation has missing chunk vectors")
            sentences = KnowledgeChunkSentence.query.filter_by(chunk_id=chunk.id, generation_id=generation.id).all()
            if not sentences or any(not KnowledgeSentenceEmbedding.query.filter_by(sentence_id=s.id, profile_id=generation.profile_id, state="ready").first() for s in sentences):
                raise ValueError("generation has missing sentence vectors")
    result = {"status": "dry_run" if dry_run else "ready", "generation_id": generation.id, "legacy_only": legacy_only}
    if dry_run:
        db.session.rollback()
        return result
    generations = [g.id for g in KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id).all()]
    chunk_ids = [c.id for c in KnowledgeChunk.query.filter(KnowledgeChunk.generation_id.in_(generations), KnowledgeChunk.searchable_active.is_(True)).all()]
    sentences = [s.id for s in KnowledgeChunkSentence.query.filter(KnowledgeChunkSentence.generation_id.in_(generations)).all()]
    KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).update({"is_current": False, "status": "retired"}, synchronize_session="fetch")
    KnowledgeChunk.query.filter(KnowledgeChunk.id.in_(chunk_ids)).update({"searchable_active": False}, synchronize_session="fetch")
    KnowledgeEmbedding.query.filter(KnowledgeEmbedding.chunk_id.in_(chunk_ids)).update({"is_active": False}, synchronize_session="fetch")
    KnowledgeSentenceEmbedding.query.filter(KnowledgeSentenceEmbedding.sentence_id.in_(sentences)).update({"is_active": False}, synchronize_session="fetch")
    db.session.flush()
    generation.status, generation.is_current = "ready", True
    target_chunks = [c.id for c in chunks]
    KnowledgeChunk.query.filter(KnowledgeChunk.id.in_(target_chunks)).update({"searchable_active": True}, synchronize_session="fetch")
    if generation.profile_id:
        target_sentences = [s.id for s in KnowledgeChunkSentence.query.filter_by(generation_id=generation.id).all()]
        KnowledgeEmbedding.query.filter(KnowledgeEmbedding.chunk_id.in_(target_chunks), KnowledgeEmbedding.profile_id == generation.profile_id).update({"is_active": True}, synchronize_session="fetch")
        KnowledgeSentenceEmbedding.query.filter(KnowledgeSentenceEmbedding.sentence_id.in_(target_sentences), KnowledgeSentenceEmbedding.profile_id == generation.profile_id).update({"is_active": True}, synchronize_session="fetch")
    db.session.commit()
    return result
