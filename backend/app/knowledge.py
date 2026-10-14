from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from .answers import AnswerValidationError, answer_question
from .auth import json_error, require_auth
from .authorization import subject_is_allowed, subject_scope
from .providers import ProviderUnavailable
from .retrieval import ReindexRequired, RetrievalInputError, retrieve


knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/classes")


@knowledge_bp.get("/<int:class_id>/knowledge/capabilities")
@require_auth
def knowledge_capabilities(class_id):
    from .models import KnowledgeEntry
    from .indexing import _eligible_query
    scope = subject_scope(g.current_user)
    if not scope:
        return json_error(403, "class access denied")
    selected = request.args.get('subject_id')
    if selected is not None and (not selected.isdecimal() or int(selected) < 1):
        return json_error(400, 'subject_id must be a positive integer')
    subjects = scope.subject_ids if selected is None else frozenset({int(selected)}) & scope.subject_ids
    entries = KnowledgeEntry.query.filter(KnowledgeEntry.class_id == scope.class_id, KnowledgeEntry.subject_id.in_(subjects))
    total = entries.count()
    incompatible = _eligible_query(0, False).filter(KnowledgeEntry.class_id == scope.class_id, KnowledgeEntry.subject_id.in_(subjects)).count()
    compatible = bool(total) and incompatible == 0
    demo = current_app.config["EMBEDDING_PROVIDER"] == "deterministic"
    return jsonify(demo_mode=demo, chat_demo_mode=current_app.config["CHAT_PROVIDER"] == "deterministic",
                   semantic_ready=compatible and not demo and current_app.config["SEMANTIC_RELEASE"],
                   semantic_release=current_app.config["SEMANTIC_RELEASE"],
                   index_compatibility="compatible" if compatible else "reindex_required" if total else "empty",
                   embedding_model=current_app.config["EMBEDDING_MODEL"],
                   embedding_revision=current_app.config["EMBEDDING_REVISION"],
                   dimensions=current_app.config["EMBEDDING_DIMENSIONS"], offset_unit="unicode_code_point")


def _effective_class_id() -> int:
    return g.current_user.class_id


@knowledge_bp.post("/<int:class_id>/knowledge/retrieve")
@require_auth
def retrieve_knowledge(class_id: int):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error(400, "request must be a JSON object")
    scope = subject_scope(g.current_user)
    if not scope:
        return json_error(403, "class access denied")
    selected_subject = payload.get("subject_id")
    if selected_subject is not None and (type(selected_subject) is not int or selected_subject < 1):
        return json_error(400, "subject_id must be a positive integer")
    allowed_subjects = scope.subject_ids if selected_subject is None else (frozenset({selected_subject}) if isinstance(selected_subject, int) and subject_is_allowed(scope, selected_subject) else frozenset())
    try:
        result = retrieve(
            class_id=scope.class_id,
            query=payload.get("query", ""),
            mode=payload.get("mode"),
            limit=payload.get("limit"),
            subject_ids=allowed_subjects,
        )
        return jsonify(result)
    except RetrievalInputError as error:
        return json_error(400, str(error))
    except ReindexRequired:
        return jsonify(error="authorized materials require reindexing", code="reindex_required"), 503
    except ProviderUnavailable:
        return json_error(503, "vector retrieval is unavailable")
    except Exception:
        current_app.logger.exception("knowledge retrieval failed")
        return json_error(503, "vector retrieval is unavailable")


@knowledge_bp.get("/<int:class_id>/knowledge/chunks/<int:chunk_id>")
@require_auth
def evidence_detail(class_id, chunk_id):
    from .models import KnowledgeChunk, KnowledgeIndexGeneration, KnowledgeEntry
    from .materials import _allowed_material
    from .extensions import db
    from .evidence import evidence_context, hit_payload
    from .retrieval_schema import source_hash
    scope = subject_scope(g.current_user)
    chunk = db.session.get(KnowledgeChunk, chunk_id)
    generation = db.session.get(KnowledgeIndexGeneration, chunk.generation_id) if chunk else None
    material = _allowed_material(chunk.material_id, scope) if chunk else None
    entry = db.session.get(KnowledgeEntry, chunk.knowledge_entry_id) if chunk else None
    if not scope or not material or not entry or not generation or chunk.class_id != scope.class_id or chunk.subject_id != material.subject_id or entry.class_id != scope.class_id or entry.material_id != material.id or generation.knowledge_entry_id != entry.id or generation.status not in {"ready", "retired"} or chunk.index_status != "ready":
        return json_error(404, "evidence not found")
    actual_hash = source_hash(entry.body_text)
    expected_hash = request.args.get("source_hash")
    if generation.source_hash != actual_hash or (expected_hash is not None and expected_hash != actual_hash):
        return jsonify(error="source changed; retrieve again", code="source_changed"), 409
    query = request.args.get("query", chunk.chunk_text[:100])
    if len(query) > 2000:
        return json_error(400, "query is too long")
    hit = hit_payload(chunk, 0, query, None, evidence_context([chunk]))
    hit.update(heading_context=chunk.heading_context, source_mapping=chunk.source_mapping if hit["provenance_version"] == "source-map-v1" else [],
               chunking=generation.normalized_options, chunker_version=generation.chunker_version, tokenizer_version=generation.tokenizer_version)
    return jsonify(evidence=hit)


@knowledge_bp.post("/<int:class_id>/knowledge/ask")
@require_auth
def ask_knowledge(class_id: int):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error(400, "request must be a JSON object")
    scope = subject_scope(g.current_user)
    if not scope:
        return json_error(403, "class access denied")
    selected_subject = payload.get("subject_id")
    if selected_subject is not None and (type(selected_subject) is not int or selected_subject < 1):
        return json_error(400, "subject_id must be a positive integer")
    allowed_subjects = scope.subject_ids if selected_subject is None else (frozenset({selected_subject}) if isinstance(selected_subject, int) and subject_is_allowed(scope, selected_subject) else frozenset())
    try:
        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            raise RetrievalInputError("question is required")
        question = question.strip()
        return jsonify(answer_question(class_id=scope.class_id, question=question, history=payload.get("history"), subject_ids=allowed_subjects))
    except RetrievalInputError as error:
        return json_error(400, str(error))
    except ReindexRequired:
        return jsonify(error="authorized materials require reindexing", code="reindex_required"), 503
    except ProviderUnavailable:
        return json_error(503, "answer generation is unavailable")
    except AnswerValidationError:
        return json_error(502, "answer citations could not be verified")
    except PermissionError:
        return json_error(403, "evidence access was revoked")
    except Exception:
        current_app.logger.exception("knowledge answer failed")
        return json_error(503, "answer generation is unavailable")
