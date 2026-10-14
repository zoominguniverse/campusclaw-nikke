from __future__ import annotations

import math
from flask import current_app
from sqlalchemy import func, select

from .chunking import chunk_text, slice_mapping, source_spans
from .extensions import db
from .lexical import lexical_text
from .models import KnowledgeChunk, KnowledgeEntry, KnowledgeIndexGeneration, KnowledgeEmbedding, KnowledgeChunkSentence, KnowledgeSentenceEmbedding, EmbeddingProfile, utc_now
from .profiles import CHUNKER_VERSION, TOKENIZER_VERSION, PROVENANCE_VERSION, current_profile, profile_identity, generation_compatible
from .providers import ProviderUnavailable, embedding_client, embed_validated
from .retrieval_schema import source_hash
from .sentences import evidence_ranges as sentence_ranges


class IndexingFailed(RuntimeError):
    pass


class IndexingConflict(RuntimeError):
    pass


def _reserve(entry_id, normalized, digest):
    profile = current_profile(create=True)
    entry = KnowledgeEntry.query.filter_by(id=entry_id).populate_existing().with_for_update().one()
    if source_hash(entry.body_text) != digest:
        raise IndexingConflict("source changed before indexing")
    base = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry_id, is_current=True).one_or_none()
    sequence = (db.session.query(func.max(KnowledgeIndexGeneration.generation)).filter_by(knowledge_entry_id=entry_id).scalar() or 0) + 1
    generation = KnowledgeIndexGeneration(knowledge_entry_id=entry_id, generation=sequence, strategy=normalized["strategy"], preprocessing=normalized["preprocess"], normalized_options=normalized,
        profile_id=profile.id, chunker_version=CHUNKER_VERSION, tokenizer_version=TOKENIZER_VERSION, source_hash=digest,
        base_current_id=base.id if base else None, status="building", is_current=False)
    db.session.add(generation)
    db.session.flush()
    generation_id, profile_id = generation.id, profile.id
    db.session.commit()  # release the entry lock before any provider request
    return generation_id, profile_id


def _publish(entry_id, generation_id):
    entry = KnowledgeEntry.query.filter_by(id=entry_id).populate_existing().with_for_update().one()
    generation = KnowledgeIndexGeneration.query.filter_by(id=generation_id).populate_existing().one()
    old = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry_id, is_current=True).populate_existing().one_or_none()
    if (old.id if old else None) != generation.base_current_id or source_hash(entry.body_text) != generation.source_hash:
        generation.status, generation.error_code, generation.completed_at = "conflict", "index_conflict", utc_now()
        db.session.commit()
        return False
    # Touch only the prior current generation. Updating concurrent building
    # chunks while holding the entry lock would invert the builder's lock order.
    ids = [c.id for c in KnowledgeChunk.query.filter_by(generation_id=old.id).all()] if old else []
    sentence_ids = [s.id for s in KnowledgeChunkSentence.query.filter(KnowledgeChunkSentence.chunk_id.in_(ids)).all()]
    KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry_id, is_current=True).update({"is_current": False, "status": "retired"}, synchronize_session="fetch")
    KnowledgeChunk.query.filter(KnowledgeChunk.id.in_(ids)).update({"searchable_active": False}, synchronize_session="fetch")
    KnowledgeEmbedding.query.filter(KnowledgeEmbedding.chunk_id.in_(ids)).update({"is_active": False}, synchronize_session="fetch")
    KnowledgeSentenceEmbedding.query.filter(KnowledgeSentenceEmbedding.sentence_id.in_(sentence_ids)).update({"is_active": False}, synchronize_session="fetch")
    db.session.flush()
    generation.status, generation.is_current, generation.completed_at = "ready", True, utc_now()
    target_chunks = [c.id for c in KnowledgeChunk.query.filter_by(generation_id=generation_id).all()]
    target_sentences = [s.id for s in KnowledgeChunkSentence.query.filter_by(generation_id=generation_id).all()]
    KnowledgeChunk.query.filter(KnowledgeChunk.id.in_(target_chunks)).update({"searchable_active": True}, synchronize_session="fetch")
    KnowledgeEmbedding.query.filter(KnowledgeEmbedding.chunk_id.in_(target_chunks), KnowledgeEmbedding.profile_id == generation.profile_id).update({"is_active": True}, synchronize_session="fetch")
    KnowledgeSentenceEmbedding.query.filter(KnowledgeSentenceEmbedding.sentence_id.in_(target_sentences), KnowledgeSentenceEmbedding.profile_id == generation.profile_id).update({"is_active": True}, synchronize_session="fetch")
    db.session.commit()
    return True


def index_entry(entry: KnowledgeEntry, options: dict | None = None, *, replace: bool = False) -> dict:
    chunks, normalized = chunk_text(entry.body_text, options)
    db.session.flush()
    entry_id, class_id, subject_id, material_id = entry.id, entry.class_id, entry.subject_id, entry.material_id
    generation_id, profile_id = _reserve(entry_id, normalized, source_hash(entry.body_text))
    if not chunks:
        generation = db.session.get(KnowledgeIndexGeneration, generation_id)
        generation.status, generation.error_code, generation.completed_at = "failed", "empty_index", utc_now()
        db.session.commit()
        return {"status": "failed", "ready_chunks": 0, "failed_chunks": 0, "generation_id": generation_id, "error_code": "empty_index"}
    records, sentences, inputs = [], [], []
    for index, item in enumerate(chunks, 1):
        record = KnowledgeChunk(generation_id=generation_id, class_id=class_id, subject_id=subject_id, material_id=material_id, knowledge_entry_id=entry_id,
            chunk_index=index, chunk_text=item.text, start_offset=item.start_offset, end_offset=item.end_offset, offset_basis=item.offset_basis,
            heading_context=item.heading_context, source_spans=item.source_spans, source_mapping=item.source_mapping,
            provenance_version=PROVENANCE_VERSION, lexical_terms=lexical_text(item.text), index_status="building", searchable_active=False)
        db.session.add(record)
        db.session.flush()
        records.append(record)
        inputs.append(("chunk", record.id, (item.heading_context + "\n" if item.heading_context else "") + item.text))
        for sequence, (start, end) in enumerate(sentence_ranges(item.text), 1):
            low, high = start + item.start_offset, end + item.start_offset
            sentence = KnowledgeChunkSentence(chunk_id=record.id, generation_id=generation_id, sequence=sequence, text=item.text[start:end], working_start=low, working_end=high,
                source_spans=source_spans(slice_mapping(item.source_mapping, low, high)))
            db.session.add(sentence)
            db.session.flush()
            sentences.append(sentence)
            inputs.append(("sentence", sentence.id, sentence.text))
    db.session.commit()  # persist diagnostic building state, hold no entry lock
    try:
        texts = list(dict.fromkeys(text for _, _, text in inputs))
        vectors = dict(zip(texts, embed_validated(embedding_client(), texts), strict=True))
        for kind, ident, text in inputs:
            cls = KnowledgeEmbedding if kind == "chunk" else KnowledgeSentenceEmbedding
            kwargs = {"chunk_id" if kind == "chunk" else "sentence_id": ident}
            db.session.add(cls(**kwargs, profile_id=profile_id, dimensions=current_app.config["EMBEDDING_DIMENSIONS"], embedding=vectors[text], state="ready", is_active=False))
            if kind == "chunk":
                record = db.session.get(KnowledgeChunk, ident)
                record.index_status = "ready"
                # New demo64 rows remain readable by the old app during staged
                # rollout. Existing legacy columns are never modified.
                if current_app.config["EMBEDDING_PROVIDER"] == "deterministic" and current_app.config["EMBEDDING_DIMENSIONS"] == 64:
                    record.embedding = vectors[text]
        db.session.flush()
        published = _publish(entry_id, generation_id)
        return {"status": "ready" if published else "conflict", "ready_chunks": len(chunks), "failed_chunks": 0, "generation_id": generation_id,
                "error_code": None if published else "index_conflict"}
    except ProviderUnavailable:
        db.session.rollback()
        generation = db.session.get(KnowledgeIndexGeneration, generation_id)
        generation.status, generation.error_code, generation.completed_at = "failed", "provider_unavailable", utc_now()
        KnowledgeChunk.query.filter_by(generation_id=generation_id).update({"index_status": "failed", "searchable_active": False}, synchronize_session="fetch")
        db.session.commit()
        return {"status": "failed", "ready_chunks": 0, "failed_chunks": len(chunks), "generation_id": generation_id, "error_code": "provider_unavailable"}


def reindex_entry(entry: KnowledgeEntry, options: dict | None = None) -> dict:
    if options is None:
        latest = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id).order_by(KnowledgeIndexGeneration.generation.desc()).first()
        if latest:
            if latest.normalized_options:
                options = latest.normalized_options
            elif latest.strategy == "custom":
                raise ValueError("legacy custom parameters are unknown; choose explicit chunking options")
            else:
                options = {"strategy": latest.strategy, "preprocess": latest.preprocessing}
    return index_entry(entry, options, replace=True)


def _eligible_query(after, force):
    query = KnowledgeEntry.query.filter(KnowledgeEntry.id > after)
    if force:
        return query
    g, c, s, e, se = KnowledgeIndexGeneration, KnowledgeChunk, KnowledgeChunkSentence, KnowledgeEmbedding, KnowledgeSentenceEmbedding
    vector_exists = select(e.id).where(e.chunk_id == c.id, e.profile_id == g.profile_id, e.is_active.is_(True), e.state == "ready").correlate(c, g).exists()
    sentence_exists = select(s.id).where(s.chunk_id == c.id, s.generation_id == g.id).correlate(c, g).exists()
    bad_chunk = select(c.id).where(c.generation_id == g.id, (c.index_status != "ready") | c.searchable_active.is_(False) | (c.provenance_version != PROVENANCE_VERSION) | ~vector_exists | ~sentence_exists).correlate(g).exists()
    sentence_vector = select(se.id).where(se.sentence_id == s.id, se.profile_id == g.profile_id, se.is_active.is_(True), se.state == "ready").correlate(s, g).exists()
    bad_sentence = select(s.id).where(s.generation_id == g.id, ~sentence_vector).correlate(g).exists()
    any_chunk = select(c.id).where(c.generation_id == g.id).correlate(g).exists()
    if db.engine.dialect.name == "sqlite":
        db.session.connection().connection.driver_connection.create_function("quality_source_hash", 1, source_hash)
        digest = func.quality_source_hash(KnowledgeEntry.body_text)
    else:
        digest = func.encode(func.sha256(func.convert_to(KnowledgeEntry.body_text, "UTF8")), "hex")
    compatible = select(g.id).join(EmbeddingProfile, EmbeddingProfile.id == g.profile_id).where(g.knowledge_entry_id == KnowledgeEntry.id, g.is_current.is_(True), g.status == "ready",
        EmbeddingProfile.fingerprint == profile_identity()["fingerprint"], g.chunker_version == CHUNKER_VERSION, g.tokenizer_version == TOKENIZER_VERSION,
        g.source_hash == digest, any_chunk, ~bad_chunk, ~bad_sentence).correlate(KnowledgeEntry).exists()
    return query.filter(~compatible)


def backfill_entries(limit: int = 100, *, after: int = 0, dry_run: bool = False, force: bool = False, profile_id: int | None = None) -> dict:
    if type(limit) is not int or not 1 <= limit <= 1000 or type(after) is not int or after < 0:
        raise ValueError("batch limit must be 1–1000 and cursor nonnegative")
    if profile_id is not None:
        if type(profile_id) is not int or profile_id < 1:
            raise ValueError("profile_id must be a positive integer")
        profile = db.session.get(EmbeddingProfile, profile_id)
        if not profile or profile.fingerprint != profile_identity()["fingerprint"]:
            raise ValueError("target profile must match the configured embedding service")
    ids = [entry.id for entry in _eligible_query(after, force).order_by(KnowledgeEntry.id).limit(limit).all()]
    db.session.commit()
    result = {"completed": 0, "failed": 0, "skipped": 0, "cursor": after, "entries": [], "dry_run": dry_run, "estimated_vectors": 0, "estimated_requests": 0}
    for ident in ids:
        entry = db.session.get(KnowledgeEntry, ident)
        result["cursor"] = ident
        if not force and _eligible_query(ident - 1, False).filter_by(id=ident).first() is None:
            result["skipped"] += 1
            result["entries"].append({"entry_id": ident, "status": "skipped"})
            continue
        if dry_run:
            latest = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=ident).order_by(KnowledgeIndexGeneration.generation.desc()).first()
            options = latest.normalized_options if latest and latest.normalized_options else None
            chunks, _ = chunk_text(entry.body_text, options)
            count = len(chunks) + sum(sum(1 for _ in sentence_ranges(chunk.text)) for chunk in chunks)
            result["estimated_vectors"] += count
            result["estimated_requests"] += math.ceil(count / current_app.config["EMBEDDING_BATCH_SIZE"])
            result["entries"].append({"entry_id": ident, "status": "eligible"})
            continue
        try:
            response = reindex_entry(entry) if KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=ident).first() else index_entry(entry)
            status = response["status"]
            result["completed" if status == "ready" else "failed"] += 1
            result["entries"].append({"entry_id": ident, "status": status, "error_code": response.get("error_code")})
        except Exception:
            db.session.rollback()
            result["failed"] += 1
            result["entries"].append({"entry_id": ident, "status": "failed", "error_code": "indexing_failed"})
        db.session.commit()
    result["has_more"] = _eligible_query(result["cursor"], force).first() is not None
    db.session.rollback()  # close the final read/dry-run transaction
    return result
