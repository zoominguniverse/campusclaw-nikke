"""Evidence windows are original source substrings, never synthesized quotes."""
from bisect import bisect_right
import math

from sqlalchemy import and_

from .extensions import db
from .lexical import tokenize
from .models import Material, ClassSubject, KnowledgeEntry, KnowledgeIndexGeneration, KnowledgeChunkSentence, KnowledgeSentenceEmbedding
from .retrieval_schema import source_hash
from .sentences import sentence_ranges


def evidence_context(chunks, vector=None):
    context = {}
    for key, cls, attr in [("materials", Material, "material_id"), ("subjects", ClassSubject, "subject_id"), ("entries", KnowledgeEntry, "knowledge_entry_id"), ("generations", KnowledgeIndexGeneration, "generation_id")]:
        ids = {getattr(c, attr) for c in chunks}
        context[key] = {item.id: item for item in cls.query.filter(cls.id.in_(ids)).all()}
    context["sentences"], context["source_ranges"] = {}, {}
    ids = [c.id for c in chunks]
    query = db.session.query(KnowledgeChunkSentence).filter(KnowledgeChunkSentence.chunk_id.in_(ids))
    if vector is not None:
        query = query.outerjoin(KnowledgeSentenceEmbedding, and_(KnowledgeSentenceEmbedding.sentence_id == KnowledgeChunkSentence.id, KnowledgeSentenceEmbedding.is_active.is_(True), KnowledgeSentenceEmbedding.state == "ready")).add_entity(KnowledgeSentenceEmbedding)
        for sentence, embedding in query.all():
            generation = context["generations"].get(sentence.generation_id)
            if embedding and generation and embedding.profile_id != generation.profile_id:
                continue
            context["sentences"].setdefault(sentence.chunk_id, []).append((sentence, embedding.embedding if embedding else None))
    else:
        for sentence in query.all():
            context["sentences"].setdefault(sentence.chunk_id, []).append((sentence, None))
    for ident, entry in context["entries"].items():
        ranges = list(sentence_ranges(entry.body_text))
        context["source_ranges"][ident] = ([start for start, _ in ranges], ranges, source_hash(entry.body_text))
    return context


def _cosine(left, right):
    if not left or not right or len(left) != len(right):
        return 0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (math.hypot(*left) * math.hypot(*right))


def _term_anchor(text, spans, query, terms):
    best = None
    for span in spans:
        low, high = span["start"], span["end"]
        fragment = text[low:high].casefold()
        phrase = fragment.find(query.casefold())
        positions = [(fragment.find(term), term) for term in terms if term in fragment]
        score = (phrase >= 0, len(positions), -(high - low))
        anchor = low + (phrase if phrase >= 0 else min(pos for pos, _ in positions) if positions else 0)
        if best is None or score > best[0]:
            best = (score, anchor, low, high)
    return best[1:]


def hit_payload(chunk, score, query, vector, context):
    material = context["materials"].get(chunk.material_id)
    subject = context["subjects"].get(chunk.subject_id)
    entry = context["entries"].get(chunk.knowledge_entry_id)
    generation = context["generations"].get(chunk.generation_id)
    terms = tokenize(query, query=True)
    provenance = chunk.provenance_version
    mapped = provenance != "legacy" and entry and generation and generation.source_hash == context["source_ranges"][entry.id][2] and chunk.source_spans
    if mapped:
        previous = -1
        for span in chunk.source_spans:
            if not (previous <= span["start"] < span["end"] <= len(entry.body_text)):
                mapped = False
                break
            previous = span["end"]
    if mapped:
        candidates = context["sentences"].get(chunk.id, [])
        if candidates:
            def sentence_score(item):
                sentence, embedding = item
                text = sentence.text.casefold()
                return (query.casefold() in text, sum(term in text for term in terms), _cosine(vector, embedding), -sentence.sequence)
            best_sentence, _ = max(candidates, key=sentence_score)
            spans = best_sentence.source_spans
        else:
            spans = chunk.source_spans
        anchor, valid_start, valid_end = _term_anchor(entry.body_text, spans, query, terms)
        starts, ranges, _ = context["source_ranges"][entry.id]
        position = bisect_right(starts, anchor) - 1
        sentence_start, sentence_end = ranges[position] if position >= 0 and anchor < ranges[position][1] else (valid_start, valid_end)
        start, end = max(sentence_start, valid_start), min(sentence_end, valid_end)
        if end - start > 160:
            start = max(start, min(anchor - 40, end - 160))
            end = min(end, start + 160)
        excerpt = entry.body_text[start:end]
        # Trim preserves exact raw-source offsets, including non-BMP characters.
        start += len(excerpt) - len(excerpt.lstrip())
        end -= len(excerpt) - len(excerpt.rstrip())
        excerpt = entry.body_text[start:end]
        key = (chunk.material_id, chunk.generation_id, sentence_start, sentence_end)
    else:
        if provenance != "legacy":
            provenance = "source_changed"
        text = chunk.chunk_text
        anchor = text.casefold().find(query.casefold())
        if anchor < 0:
            anchor = next((text.casefold().find(term) for term in terms if term in text.casefold()), 0)
        low = max(0, min(anchor - 40, len(text) - 160))
        excerpt, start, end = text[low:low + 160], None, None
        key = (chunk.material_id, chunk.generation_id, "legacy", chunk.id)
    return {
        "material_id": chunk.material_id, "material_title": material.title if material else "",
        "subject_id": chunk.subject_id, "subject_name": subject.name if subject and subject.class_id == chunk.class_id else "",
        "chunk_id": chunk.id, "chunk_index": chunk.chunk_index, "generation_id": chunk.generation_id,
        "start_offset": chunk.start_offset, "end_offset": chunk.end_offset, "offset_basis": chunk.offset_basis,
        "source_hash": generation.source_hash if generation else None,
        "source_spans": chunk.source_spans if mapped else [], "provenance_version": provenance,
        "offset_unit": "unicode_code_point", "excerpt_start_offset": start, "excerpt_end_offset": end,
        "excerpt": excerpt, "excerpt_truncated": len(chunk.chunk_text) > len(excerpt), "chunk_text": chunk.chunk_text,
        "score": round(score, 6), "evidence_key": list(key),
    }
