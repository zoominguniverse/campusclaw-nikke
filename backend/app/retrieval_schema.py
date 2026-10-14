"""Additive retrieval migration. Legacy vectors/source are deliberately untouched."""
import hashlib

from sqlalchemy import inspect, text

from .extensions import db
from .models import EmbeddingProfile, KnowledgeEntry, KnowledgeIndexGeneration

GENERATION_COLUMNS = {
    "profile_id": "INTEGER REFERENCES embedding_profiles(id)",
    "chunker_version": "VARCHAR(64) NOT NULL DEFAULT 'legacy'",
    "tokenizer_version": "VARCHAR(64) NOT NULL DEFAULT 'legacy'",
    "normalized_options": "JSON NOT NULL DEFAULT '{}'",
    "source_hash": "VARCHAR(64)", "base_current_id": "INTEGER", "error_code": "VARCHAR(64)",
}
CHUNK_COLUMNS = {
    "heading_context": "TEXT NOT NULL DEFAULT ''", "source_spans": "JSON NOT NULL DEFAULT '[]'",
    "source_mapping": "JSON NOT NULL DEFAULT '[]'", "lexical_terms": "TEXT NOT NULL DEFAULT ''",
    "searchable_active": "BOOLEAN NOT NULL DEFAULT FALSE", "provenance_version": "VARCHAR(32) NOT NULL DEFAULT 'legacy'",
}


def source_hash(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def prepare_legacy_tables():
    # New tables' foreign keys require the additive legacy constraints first.
    tables = set(inspect(db.engine).get_table_names())
    EmbeddingProfile.__table__.create(db.engine, checkfirst=True)
    for table, columns in [("knowledge_index_generations", GENERATION_COLUMNS), ("knowledge_chunks", CHUNK_COLUMNS)]:
        if table not in tables:
            continue
        present = {c["name"] for c in inspect(db.engine).get_columns(table)}
        for name, ddl in columns.items():
            if name not in present:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        db.session.commit()
    if "knowledge_chunks" in tables and db.engine.dialect.name == "postgresql":
        constraints = {c["name"] for c in inspect(db.engine).get_unique_constraints("knowledge_chunks")}
        if "uq_chunk_id_generation" not in constraints:
            db.session.execute(text("ALTER TABLE knowledge_chunks ADD CONSTRAINT uq_chunk_id_generation UNIQUE (id, generation_id)"))
            db.session.commit()


def finish_retrieval_upgrade():
    duplicate = db.session.execute(text("SELECT knowledge_entry_id FROM knowledge_index_generations WHERE is_current GROUP BY knowledge_entry_id HAVING COUNT(*) > 1 LIMIT 1")).first()
    if duplicate:
        raise RuntimeError("retrieval migration requires resolving duplicate current generations; no automatic deletion is performed")
    predicate = "is_current" if db.engine.dialect.name == "postgresql" else "is_current = 1"
    db.session.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS uq_entry_current_generation ON knowledge_index_generations (knowledge_entry_id) WHERE {predicate}"))
    for generation, entry in db.session.query(KnowledgeIndexGeneration, KnowledgeEntry).join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeIndexGeneration.knowledge_entry_id).filter(KnowledgeIndexGeneration.source_hash.is_(None)):
        generation.source_hash = source_hash(entry.body_text)
        # Hash identity is safe to reconstruct; accurate old source mappings and
        # unknown model identities are NOT inferred from the old vector length.
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_active_terms ON knowledge_chunks USING gin (to_tsvector('simple', lexical_terms)) WHERE searchable_active AND index_status = 'ready'"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_active_scope ON knowledge_chunks (class_id, subject_id, generation_id) WHERE searchable_active AND index_status = 'ready'"))
    db.session.commit()


def install_profile_hnsw(profile_id):
    """Optional operator command. Production stays exact until ANN is measured."""
    if type(profile_id) is not int or profile_id < 1:
        raise ValueError("profile_id must be a positive integer")
    profile = db.session.get(EmbeddingProfile, profile_id)
    if not profile or not 1 <= profile.dimensions <= 2000:
        raise ValueError("HNSW supports only registered profiles with 1–2000 dimensions")
    if db.engine.dialect.name != "postgresql":
        raise ValueError("HNSW requires PostgreSQL")
    db.session.execute(text(f"CREATE INDEX IF NOT EXISTS ix_embeddings_profile_{profile.id}_cosine ON knowledge_embeddings USING hnsw ((embedding::vector({profile.dimensions})) vector_cosine_ops) WHERE profile_id = {profile.id} AND is_active AND state = 'ready'"))
    db.session.commit()
