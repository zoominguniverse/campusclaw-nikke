from __future__ import annotations

import json
import re

from flask import current_app, has_app_context, has_request_context, g

from .extensions import db
from .models import KnowledgeChunk, KnowledgeEntry, KnowledgeIndexGeneration
from .providers import chat_client
from .retrieval import NO_EVIDENCE_MESSAGE, RetrievalInputError, ReindexRequired, retrieve
from .retrieval_schema import source_hash

INSUFFICIENT_MESSAGE = "资料不足以回答该问题"
CITATION_FIELDS = ("subject_id", "subject_name", "material_id", "material_title", "chunk_id", "chunk_index", "generation_id", "source_hash", "source_spans", "start_offset", "end_offset", "offset_basis", "excerpt", "excerpt_start_offset", "excerpt_end_offset", "excerpt_truncated", "offset_unit", "provenance_version", "evidence_key")


class AnswerValidationError(RuntimeError):
    pass


def _validated_history(history):
    if history is None:
        return []
    if not isinstance(history, list):
        raise RetrievalInputError("history must be an array")
    limit = current_app.config["ANSWER_HISTORY_LIMIT"] if has_app_context() else 6
    allowed = []
    for item in history[-limit:] if limit else []:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            allowed.append({"role": item["role"], "content": content.strip()[:1000]})
    return allowed


def _prepare_evidence(hits, class_id, subject_ids):
    prepared = []
    for index, hit in enumerate(hits, 1):
        chunk = db.session.get(KnowledgeChunk, hit["chunk_id"])
        entry = db.session.get(KnowledgeEntry, chunk.knowledge_entry_id) if chunk else None
        generation = db.session.get(KnowledgeIndexGeneration, chunk.generation_id) if chunk else None
        if not entry or not generation or entry.class_id != class_id or entry.material_id != hit["material_id"] or (subject_ids is not None and entry.subject_id not in subject_ids) or generation.source_hash != source_hash(entry.body_text) or hit["provenance_version"] != "source-map-v1":
            raise ReindexRequired("evidence source changed or lacks exact provenance")
        segments = [{"start": span["start"], "end": span["end"], "text": entry.body_text[span["start"]:span["end"]]} for span in hit["source_spans"]]
        if sum(len(segment["text"]) for segment in segments) > 4000:
            segments = [{"start": hit["excerpt_start_offset"], "end": hit["excerpt_end_offset"], "text": hit["excerpt"]}]
        prepared.append({**hit, "evidence_index": index, "source_segments": segments})
    return prepared


def _quote_range(evidence, quote):
    for segment in evidence["source_segments"]:
        offset = segment["text"].find(quote)
        if offset >= 0:
            return {"start": segment["start"] + offset, "end": segment["start"] + offset + len(quote)}
    raise AnswerValidationError("quote is not an exact original source substring")


def _validate_output(output, evidence):
    try:
        value = json.loads(output) if isinstance(output, str) else output
    except (ValueError, TypeError):
        raise AnswerValidationError("chat output is not a JSON object") from None
    if not isinstance(value, dict) or set(value) != {"status", "claims"} or not isinstance(value["status"], str) or value["status"] not in {"answered", "insufficient"} or not isinstance(value["claims"], list):
        raise AnswerValidationError("invalid structured answer")
    if value["status"] == "insufficient":
        if value["claims"]:
            raise AnswerValidationError("insufficient answer must not contain claims")
        return value
    if not 1 <= len(value["claims"]) <= 20:
        raise AnswerValidationError("answered output needs nonempty bounded claims")
    claims = []
    for claim in value["claims"]:
        if not isinstance(claim, dict) or set(claim) != {"text", "evidence"} or not isinstance(claim["text"], str) or not claim["text"].strip() or re.search(r"\[\d+\]", claim["text"]) or not isinstance(claim["evidence"], list) or not 1 <= len(claim["evidence"]) <= 4:
            raise AnswerValidationError("claim needs text and valid evidence")
        references = []
        for ref in claim["evidence"]:
            if not isinstance(ref, dict) or set(ref) != {"index", "quote"} or type(ref["index"]) is not int or not 1 <= ref["index"] <= len(evidence) or not isinstance(ref["quote"], str) or not ref["quote"].strip() or len(ref["quote"]) > 2000:
                raise AnswerValidationError("invalid evidence reference")
            quote_range = _quote_range(evidence[ref["index"] - 1], ref["quote"])
            references.append({**ref, "source_span": quote_range})
        claims.append({"text": claim["text"].strip(), "evidence": references})
    if sum(len(claim["text"]) for claim in claims) + len(claims) - 1 > 200:
        raise AnswerValidationError("answer exceeds 200 code points")
    return {"status": "answered", "claims": claims}


def answer_question(*, class_id, question, history=None, subject_ids=None, include_claims=False):
    allowed_history = _validated_history(history)
    result = retrieve(class_id=class_id, query=question, mode="hybrid", limit=4, subject_ids=subject_ids)
    hits = result["hits"]
    demo = has_app_context() and current_app.config["CHAT_PROVIDER"] == "deterministic"
    if not hits:
        return {"answer": NO_EVIDENCE_MESSAGE, "citations": [], "status": "no_evidence", "demo_mode": bool(demo)}
    evidence = _prepare_evidence(hits, class_id, subject_ids)
    client = chat_client()
    for attempt in range(2):
        output = client.answer(question, evidence, allowed_history) if attempt == 0 else client.answer(question, evidence, allowed_history, repair=True)
        try:
            validated = _validate_output(output, evidence)
            break
        except AnswerValidationError:
            if attempt:
                raise
    # A source edit while a provider was answering cannot result in stale quotes.
    for item in evidence:
        chunk = db.session.get(KnowledgeChunk, item["chunk_id"])
        if not chunk:
            raise ReindexRequired("evidence was removed")
        entry = KnowledgeEntry.query.filter_by(id=chunk.knowledge_entry_id).populate_existing().one_or_none()
        if not entry or source_hash(entry.body_text) != item["source_hash"]:
            raise ReindexRequired("evidence source changed")
    if has_request_context():
        from .authorization import subject_scope
        from .models import User
        user = User.query.filter_by(id=g.current_user.id).populate_existing().one_or_none()
        scope = subject_scope(user) if user else None
        if not scope or scope.class_id != class_id or any(item["subject_id"] not in scope.subject_ids for item in evidence):
            raise PermissionError("evidence access was revoked")
    if validated["status"] == "insufficient":
        return {"answer": INSUFFICIENT_MESSAGE, "citations": [], "status": "insufficient", "demo_mode": bool(demo)}
    used, citations, lines = {}, [], []
    for claim in validated["claims"]:
        markers = []
        for ref in claim["evidence"]:
            original_index = ref["index"]
            if original_index not in used:
                used[original_index] = len(citations) + 1
                citation = {key: evidence[original_index - 1][key] for key in CITATION_FIELDS}
                citation["quotes"] = []
                citations.append(citation)
            ordinal = used[original_index]
            citation = citations[ordinal - 1]
            quoted = {"text": ref["quote"], "source_span": ref["source_span"]}
            if quoted not in citation["quotes"]:
                citation["quotes"].append(quoted)
            if ordinal not in markers:
                markers.append(ordinal)
        lines.append(claim["text"] + "".join(f"[{ordinal}]" for ordinal in markers))
    result = {"answer": "\n".join(lines), "citations": citations, "status": "answered", "demo_mode": bool(demo)}
    if include_claims:
        # Internal evaluation option; the HTTP endpoint retains its existing DTO.
        result['claims'] = [{'text': claim['text'], 'evidence': [{**ref, 'index': used[ref['index']]} for ref in claim['evidence']]} for claim in validated['claims']]
    return result
