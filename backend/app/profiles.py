import hashlib
import json

from flask import current_app
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .extensions import db
from .models import EmbeddingProfile, KnowledgeEntry, KnowledgeChunk, KnowledgeChunkSentence, KnowledgeEmbedding, KnowledgeSentenceEmbedding

CHUNKER_VERSION = "chunker-v2"
TOKENIZER_VERSION = "jieba-0.42.1/default-dict+terms-v2"
PROVENANCE_VERSION = "source-map-v1"
PROCESSING_VERSION = f"{PROVENANCE_VERSION};{CHUNKER_VERSION};{TOKENIZER_VERSION}"


def profile_identity(config=None):
    config = config or current_app.config
    values = {"provider": config["EMBEDDING_PROVIDER"], "model": config["EMBEDDING_MODEL"], "revision": config["EMBEDDING_REVISION"], "dimensions": config["EMBEDDING_DIMENSIONS"], "processing_version": PROCESSING_VERSION}
    # Endpoint affects provider identity but is never exposed in a public DTO.
    fingerprint_input = {**values, "endpoint": config["EMBEDDING_API_URL"]}
    values["fingerprint"] = hashlib.sha256(json.dumps(fingerprint_input, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return values


def current_profile(*, create=False):
    values = profile_identity()
    profile = EmbeddingProfile.query.filter_by(fingerprint=values["fingerprint"]).first()
    if not profile and create:
        insert = pg_insert if db.engine.dialect.name == "postgresql" else sqlite_insert
        db.session.execute(insert(EmbeddingProfile).values(**values).on_conflict_do_nothing(index_elements=["fingerprint"]))
        profile = EmbeddingProfile.query.filter_by(fingerprint=values["fingerprint"]).one()
    return profile


def generation_compatible(generation, *, check_ready=True):
    profile = db.session.get(EmbeddingProfile, generation.profile_id) if generation.profile_id else None
    if not profile or profile.fingerprint != profile_identity()["fingerprint"] or generation.chunker_version != CHUNKER_VERSION or generation.tokenizer_version != TOKENIZER_VERSION or not generation.source_hash:
        return False
    if not check_ready:
        return True
    from .retrieval_schema import source_hash
    entry = db.session.get(KnowledgeEntry, generation.knowledge_entry_id)
    if not entry or generation.source_hash != source_hash(entry.body_text):
        return False
    chunks = KnowledgeChunk.query.filter_by(generation_id=generation.id).all()
    if not chunks:
        return False
    for chunk in chunks:
        if chunk.index_status != "ready" or not chunk.searchable_active or chunk.provenance_version != PROVENANCE_VERSION or not chunk.source_spans:
            return False
        if not KnowledgeEmbedding.query.filter_by(chunk_id=chunk.id, profile_id=profile.id, state="ready", is_active=True).first():
            return False
        sentences = KnowledgeChunkSentence.query.filter_by(chunk_id=chunk.id, generation_id=generation.id).all()
        if not sentences or any(not KnowledgeSentenceEmbedding.query.filter_by(sentence_id=s.id, profile_id=profile.id, state="ready", is_active=True).first() for s in sentences):
            return False
    return True
