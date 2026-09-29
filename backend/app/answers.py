from __future__ import annotations

import re

from .providers import ProviderUnavailable, chat_client
from .retrieval import NO_EVIDENCE_MESSAGE, RetrievalInputError, retrieve


class AnswerValidationError(RuntimeError):
    pass


def answer_question(*, class_id: int, question: str, history: list | None = None, subject_ids: set[int] | frozenset[int] | None = None) -> dict:
    result = retrieve(class_id=class_id, query=question, mode="hybrid", limit=4, subject_ids=subject_ids)
    hits = result["hits"]
    if not hits:
        return {"answer": NO_EVIDENCE_MESSAGE, "citations": []}
    allowed_history = _validated_history(history or [])
    answer = chat_client().answer(question, hits, allowed_history)
    citations = [{key: hit[key] for key in ("subject_id", "subject_name", "material_id", "material_title", "chunk_id", "chunk_index", "start_offset", "end_offset", "offset_basis", "excerpt")} for hit in hits]
    _validate_citations(answer, len(citations))
    return {"answer": answer, "citations": citations}


def _validated_history(history: list) -> list[dict]:
    allowed: list[dict] = []
    for item in history[-6:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            allowed.append({"role": item["role"], "content": content.strip()[:4000]})
    return allowed


def _validate_citations(answer: str, count: int) -> None:
    markers = [int(value) for value in re.findall(r"\[(\d+)\]", answer)]
    if not markers or any(marker < 1 or marker > count for marker in markers):
        raise AnswerValidationError("chat response has invalid citations")
