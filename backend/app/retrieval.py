from __future__ import annotations

import math
from collections import defaultdict

from sqlalchemy import func

from .database import db
from .models import ClassSubject, KnowledgeChunk, KnowledgeIndexGeneration, Material
from .providers import ProviderUnavailable, embedding_client


NO_EVIDENCE_MESSAGE = "资料中未找到相关内容"
VECTOR_THRESHOLD = 0.35
RRF_K = 60


class RetrievalInputError(ValueError):
    pass


def retrieve(*, class_id: int, query: str, mode: str | None = None, limit: int | None = None, subject_ids: set[int] | frozenset[int] | None = None) -> dict:
    query = (query or "").strip()
    if not query:
        raise RetrievalInputError("query is required")
    mode = mode or "hybrid"
    if mode not in {"keyword", "vector", "hybrid"}:
        raise RetrievalInputError("unsupported retrieval mode")
    limit = max(1, min(limit or 10, 20))
    effective_subject_ids = set(subject_ids) if subject_ids is not None else None
    if mode == "keyword":
        ranked = _keyword_ranked(class_id, query, limit, effective_subject_ids)
    elif mode == "vector":
        ranked = _vector_ranked(class_id, query, limit, effective_subject_ids)
    else:
        keyword = _keyword_ranked(class_id, query, limit * 3, effective_subject_ids)
        vector = _vector_ranked(class_id, query, limit * 3, effective_subject_ids)
        ranked = _rrf(keyword, vector, limit)
    hits = [_hit_payload(chunk, score) for chunk, score in ranked]
    return {"mode": mode, "hits": hits, "message": None if hits else NO_EVIDENCE_MESSAGE}


def _base_query(class_id: int, subject_ids: set[int] | None = None):
    query = (
        db.session.query(KnowledgeChunk, Material)
        .join(KnowledgeIndexGeneration, KnowledgeChunk.generation_id == KnowledgeIndexGeneration.id)
        .join(Material, KnowledgeChunk.material_id == Material.id)
        .filter(
            KnowledgeChunk.class_id == class_id,
            Material.class_id == class_id,
            KnowledgeChunk.index_status == "ready",
            KnowledgeIndexGeneration.is_current.is_(True),
            KnowledgeIndexGeneration.status == "ready",
        )
    )
    if subject_ids is not None:
        query = query.filter(KnowledgeChunk.subject_id.in_(subject_ids))
    return query


def _keyword_ranked(class_id: int, query: str, limit: int, subject_ids: set[int] | None = None) -> list[tuple[KnowledgeChunk, float]]:
    base = _base_query(class_id, subject_ids)
    if db.engine.dialect.name == "postgresql":
        score = func.similarity(KnowledgeChunk.chunk_text, query)
        # pg_trgm's similarity alone is deliberately fuzzy: two class-specific
        # phrases that differ by one character can still score highly.  Keep
        # keyword mode a literal word/phrase lookup and use similarity only to
        # rank those candidates.  The ready-only trigram GIN index supports the
        # ILIKE predicate on PostgreSQL.
        rows = (
            base.filter(KnowledgeChunk.chunk_text.ilike(f"%{query}%"))
            .order_by(score.desc(), KnowledgeChunk.id)
            .limit(limit)
            .add_columns(score)
            .all()
        )
        return [(chunk, float(value)) for chunk, _material, value in rows]
    rows = base.filter(KnowledgeChunk.chunk_text.ilike(f"%{query}%")).order_by(KnowledgeChunk.id).limit(limit).all()
    return [(chunk, 1.0) for chunk, _material in rows]


def _vector_ranked(class_id: int, query: str, limit: int, subject_ids: set[int] | None = None) -> list[tuple[KnowledgeChunk, float]]:
    vector = embedding_client().embed(query)
    if db.engine.dialect.name == "postgresql":
        distance = KnowledgeChunk.embedding.op("<=>")(vector)
        rows = _base_query(class_id, subject_ids).filter(KnowledgeChunk.embedding.is_not(None)).order_by(distance, KnowledgeChunk.id).add_columns(distance).limit(limit * 3).all()
        ranked = [(chunk, 1.0 - float(value)) for chunk, _material, value in rows]
    else:
        ranked = []
        for chunk, _material in _base_query(class_id, subject_ids).filter(KnowledgeChunk.embedding.is_not(None)).all():
            score = _cosine(vector, chunk.embedding)
            ranked.append((chunk, score))
        ranked.sort(key=lambda item: (-item[1], item[0].id))
    return [item for item in ranked if item[1] >= VECTOR_THRESHOLD][:limit]


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_size = math.sqrt(sum(a * a for a in left))
    right_size = math.sqrt(sum(b * b for b in right))
    return numerator / (left_size * right_size) if left_size and right_size else 0.0


def _rrf(keyword: list[tuple[KnowledgeChunk, float]], vector: list[tuple[KnowledgeChunk, float]], limit: int):
    scores: dict[int, float] = defaultdict(float)
    chunks: dict[int, KnowledgeChunk] = {}
    for results in (keyword, vector):
        for rank, (chunk, _score) in enumerate(results, 1):
            chunks[chunk.id] = chunk
            scores[chunk.id] += 1.0 / (RRF_K + rank)
    return sorted(((chunks[chunk_id], score) for chunk_id, score in scores.items()), key=lambda item: (-item[1], item[0].id))[:limit]


def _hit_payload(chunk: KnowledgeChunk, score: float) -> dict:
    material = db.session.get(Material, chunk.material_id)
    subject = db.session.get(ClassSubject, chunk.subject_id)
    return {
        "material_id": chunk.material_id,
        "material_title": material.title if material else "",
        "subject_id": chunk.subject_id,
        "subject_name": subject.name if subject and subject.class_id == chunk.class_id else "",
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "start_offset": chunk.start_offset,
        "end_offset": chunk.end_offset,
        "offset_basis": chunk.offset_basis,
        "excerpt": chunk.chunk_text,
        "chunk_text": chunk.chunk_text,
        "score": round(score, 6),
    }
