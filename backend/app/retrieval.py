from __future__ import annotations

import math
from collections import defaultdict

from flask import current_app
from sqlalchemy import func, case, or_, and_, select

from .extensions import db
from .models import KnowledgeChunk, KnowledgeIndexGeneration, KnowledgeEntry, Material, KnowledgeEmbedding, KnowledgeChunkSentence, KnowledgeSentenceEmbedding
from .providers import ProviderUnavailable, embedding_client, embed_validated
from .lexical import tokenize, query_groups
from .profiles import current_profile
from .evidence import evidence_context, hit_payload

NO_EVIDENCE_MESSAGE = "资料中未找到相关内容"
VECTOR_THRESHOLD = 0.35
RRF_K = 60
CANDIDATE_LIMIT = 100
RETRIEVAL_VERSION = 'sentence-gated-v1'


class RetrievalInputError(ValueError):
    pass


class ReindexRequired(ProviderUnavailable):
    pass


def retrieve(*, class_id, query, mode=None, limit=None, subject_ids=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise RetrievalInputError("query must be a nonempty string of at most 2000 code points")
    query = query.strip()
    if mode is None:
        mode = "hybrid"
    if not isinstance(mode, str) or mode not in {"keyword", "vector", "hybrid"}:
        raise RetrievalInputError("unsupported retrieval mode")
    if limit is None:
        limit = current_app.config["RETRIEVAL_MAX_HITS"]
    if type(limit) is not int or not 1 <= limit <= 20:
        raise RetrievalInputError("limit must be an integer between 1 and 20")
    if subject_ids is not None and any(type(ident) is not int or ident < 1 for ident in subject_ids):
        raise RetrievalInputError("subject IDs must be positive integers")
    effective = set(subject_ids) if subject_ids is not None else None
    terms = tokenize(query, query=True)
    if len(terms) > 64:
        raise RetrievalInputError("query contains too many effective terms (maximum 64)")
    empty = {"mode": mode, "hits": [], "message": NO_EVIDENCE_MESSAGE}
    if effective == set() or not terms:
        return empty
    vector = None
    if mode != "keyword":
        _ensure_compatible(class_id, effective)
        # An empty authorized source scope needs no provider or diagnostic.
        scope = KnowledgeEntry.query.join(Material).filter(KnowledgeEntry.class_id == class_id, Material.class_id == class_id)
        if effective is not None:
            scope = scope.filter(KnowledgeEntry.subject_id.in_(effective), Material.subject_id.in_(effective))
        if scope.first() is None:
            return empty
        vector = embed_validated(embedding_client(), [query])[0]
    if mode == "keyword":
        ranked = _keyword_ranked(class_id, query, CANDIDATE_LIMIT, effective)
    elif mode == "vector":
        ranked = _vector_ranked(class_id, query, CANDIDATE_LIMIT, effective, vector)
    else:
        ranked = _rrf(_keyword_ranked(class_id, query, CANDIDATE_LIMIT, effective), _vector_ranked(class_id, query, CANDIDATE_LIMIT, effective, vector), CANDIDATE_LIMIT)
    context = evidence_context([chunk for chunk, _ in ranked], vector)
    hits, seen = [], set()
    for chunk, score in ranked:
        hit = hit_payload(chunk, score, query, vector, context)
        key = tuple(hit["evidence_key"])
        if key in seen:
            continue
        seen.add(key)
        hits.append(hit)
        if len(hits) == limit:
            break
    return {"mode": mode, "hits": hits, "message": None if hits else NO_EVIDENCE_MESSAGE}


def _ensure_compatible(class_id, subject_ids):
    from .indexing import _eligible_query
    query = _eligible_query(0, False).join(Material).filter(KnowledgeEntry.class_id == class_id, Material.class_id == class_id, KnowledgeEntry.subject_id == Material.subject_id)
    if subject_ids is not None:
        query = query.filter(KnowledgeEntry.subject_id.in_(subject_ids), Material.subject_id.in_(subject_ids))
    if query.first():
        raise ReindexRequired("authorized sources require rebuilding for the configured profile")


def _base_query(class_id, subject_ids=None):
    query = db.session.query(KnowledgeChunk, Material).join(KnowledgeIndexGeneration, KnowledgeChunk.generation_id == KnowledgeIndexGeneration.id).join(KnowledgeEntry, KnowledgeChunk.knowledge_entry_id == KnowledgeEntry.id).join(Material, KnowledgeChunk.material_id == Material.id).filter(
        KnowledgeChunk.class_id == class_id, Material.class_id == class_id, KnowledgeEntry.class_id == class_id,
        KnowledgeEntry.material_id == Material.id, KnowledgeIndexGeneration.knowledge_entry_id == KnowledgeEntry.id,
        KnowledgeChunk.subject_id == Material.subject_id, KnowledgeEntry.subject_id == Material.subject_id,
        KnowledgeChunk.index_status == "ready", KnowledgeIndexGeneration.is_current.is_(True), KnowledgeIndexGeneration.status == "ready",
        or_(KnowledgeChunk.searchable_active.is_(True), KnowledgeChunk.provenance_version == "legacy"))
    if subject_ids is not None:
        query = query.filter(KnowledgeChunk.subject_id.in_(subject_ids), Material.subject_id.in_(subject_ids))
    return query


def _escape_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _keyword_ranked(class_id, query, limit, subject_ids=None):
    terms = tokenize(query, query=True)
    if not terms:
        return []
    groups = query_groups(query)
    required = 1 if len(groups) == 1 else max(2, math.ceil(.6 * len(groups)))
    base = _base_query(class_id, subject_ids)
    if db.engine.dialect.name == "postgresql":
        phrase = KnowledgeChunk.chunk_text.ilike(f"%{_escape_like(query)}%", escape="\\")
        document = func.to_tsvector("simple", KnowledgeChunk.lexical_terms)
        search = func.to_tsquery("simple", " | ".join(terms))
        legacy = KnowledgeChunk.provenance_version == "legacy"
        coverage = sum(case((and_(*(or_(document.bool_op("@@")(func.plainto_tsquery("simple", term)), legacy & KnowledgeChunk.chunk_text.ilike(f"%{_escape_like(term)}%", escape="\\")) for term in group)), 1), else_=0) for group in groups)
        rank = func.ts_rank_cd(document, search)
        candidates = document.bool_op("@@")(search) | (legacy & or_(*(KnowledgeChunk.chunk_text.ilike(f"%{_escape_like(term)}%", escape="\\") for term in terms)))
        rows = base.filter(phrase | candidates, phrase | (coverage >= required)).add_columns(phrase, coverage, rank).order_by(phrase.desc(), coverage.desc(), rank.desc(), KnowledgeChunk.id).limit(min(limit, CANDIDATE_LIMIT)).all()
        return [(chunk, (1000 if exact else 0) + count + float(value)) for chunk, _, exact, count, value in rows]
    ranked = []
    for chunk, _ in base.all():
        phrase = query.casefold() in chunk.chunk_text.casefold()
        words = set(chunk.lexical_terms.split()) if chunk.lexical_terms else set(tokenize(chunk.chunk_text))
        coverage = sum(all(term in words or (chunk.provenance_version == "legacy" and term in chunk.chunk_text.casefold()) for term in group) for group in groups)
        if phrase or coverage >= required:
            ranked.append((chunk, (1000 if phrase else 0) + coverage))
    return sorted(ranked, key=lambda item: (-item[1], item[0].id))[:min(limit, CANDIDATE_LIMIT)]


def _vector_ranked(class_id, query, limit, subject_ids=None, vector=None):
    if vector is None:
        _ensure_compatible(class_id, subject_ids)
        vector = embed_validated(embedding_client(), [query])[0]
    profile = current_profile()
    if not profile:
        return []
    base = _base_query(class_id, subject_ids).join(KnowledgeEmbedding, KnowledgeEmbedding.chunk_id == KnowledgeChunk.id).filter(KnowledgeEmbedding.profile_id == profile.id, KnowledgeIndexGeneration.profile_id == profile.id, KnowledgeEmbedding.dimensions == profile.dimensions, KnowledgeEmbedding.state == "ready", KnowledgeEmbedding.is_active.is_(True))
    threshold = max(VECTOR_THRESHOLD, current_app.config["VECTOR_THRESHOLD"])
    if db.engine.dialect.name == "postgresql":
        distance = KnowledgeEmbedding.embedding.op("<=>", return_type=db.Float)(vector)
        sentence_distance = KnowledgeSentenceEmbedding.embedding.op("<=>", return_type=db.Float)(vector)
        supported_sentence = select(KnowledgeChunkSentence.id).join(KnowledgeSentenceEmbedding, KnowledgeSentenceEmbedding.sentence_id == KnowledgeChunkSentence.id).where(
            KnowledgeChunkSentence.chunk_id == KnowledgeChunk.id, KnowledgeChunkSentence.generation_id == KnowledgeChunk.generation_id,
            KnowledgeSentenceEmbedding.profile_id == profile.id, KnowledgeSentenceEmbedding.dimensions == profile.dimensions,
            KnowledgeSentenceEmbedding.state == 'ready', KnowledgeSentenceEmbedding.is_active.is_(True),
            sentence_distance <= 1 - threshold).correlate(KnowledgeChunk).exists()
        rows = base.filter(distance <= 1 - threshold, supported_sentence).add_columns(distance).order_by(distance, KnowledgeChunk.id).limit(min(limit, CANDIDATE_LIMIT)).all()
        return [(chunk, 1 - float(value)) for chunk, _, value in rows]
    ranked = [(chunk, _cosine(vector, embedding)) for chunk, _, embedding in base.add_columns(KnowledgeEmbedding.embedding).all()]
    context = evidence_context([chunk for chunk, score in ranked if score >= threshold], vector)
    relevant = lambda chunk: any(embedding and _cosine(vector, embedding) >= threshold for sentence, embedding in context['sentences'].get(chunk.id, []))
    return sorted((item for item in ranked if item[1] >= threshold and relevant(item[0])), key=lambda item: (-item[1], item[0].id))[:min(limit, CANDIDATE_LIMIT)]


def _cosine(left, right):
    return sum(a * b for a, b in zip(left, right, strict=True)) / (math.hypot(*left) * math.hypot(*right))


def _rrf(keyword, vector, limit):
    scores, chunks = defaultdict(float), {}
    for results in (keyword, vector):
        for rank, (chunk, _) in enumerate(results, 1):
            chunks[chunk.id] = chunk
            scores[chunk.id] += 1 / (RRF_K + rank)
    return sorted(((chunks[ident], score) for ident, score in scores.items()), key=lambda item: (-item[1], item[0].id))[:limit]


def _hit_payload(chunk, score):
    """Compatibility helper; public retrieval always passes a query context."""
    return hit_payload(chunk, score, chunk.chunk_text, None, evidence_context([chunk]))
