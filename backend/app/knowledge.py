from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from .answers import AnswerValidationError, answer_question
from .auth import json_error, require_auth
from .providers import ProviderUnavailable
from .retrieval import RetrievalInputError, retrieve


knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/classes")


def _effective_class_id() -> int:
    return g.current_user.class_id


@knowledge_bp.post("/<int:class_id>/knowledge/retrieve")
@require_auth
def retrieve_knowledge(class_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        result = retrieve(
            class_id=_effective_class_id(),
            query=payload.get("query", ""),
            mode=payload.get("mode"),
            limit=payload.get("limit"),
        )
        return jsonify(result)
    except RetrievalInputError as error:
        return json_error(400, str(error))
    except ProviderUnavailable:
        return json_error(503, "vector retrieval is unavailable")
    except Exception:
        current_app.logger.exception("knowledge retrieval failed")
        return json_error(503, "vector retrieval is unavailable")


@knowledge_bp.post("/<int:class_id>/knowledge/ask")
@require_auth
def ask_knowledge(class_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        question = (payload.get("question") or "").strip()
        if not question:
            raise RetrievalInputError("question is required")
        return jsonify(answer_question(class_id=_effective_class_id(), question=question, history=payload.get("history")))
    except RetrievalInputError as error:
        return json_error(400, str(error))
    except ProviderUnavailable:
        return json_error(503, "answer generation is unavailable")
    except AnswerValidationError:
        return json_error(502, "answer citations could not be verified")
    except Exception:
        current_app.logger.exception("knowledge answer failed")
        return json_error(503, "answer generation is unavailable")
