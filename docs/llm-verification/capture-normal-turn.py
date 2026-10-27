"""Capture one real provider exchange without creating a conversation or message.

Run from the repository root by piping this file into the running API container:
Get-Content -Raw docs/llm-verification/capture-normal-turn.py | docker compose exec -T api python -

The process reads the existing mathematics agent and materials. It makes real
embedding/chat requests using the existing server configuration, but does not
change configuration, skills, bindings, conversations or messages. Standard
output is a JSON record with all configured secrets redacted.
"""
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

import requests
from sqlalchemy import text

from app import create_app
from app.authorization import subject_scope
from app.database import db
from app.models import KnowledgeEntry, Skill, TutorAgent, User
from app.tutor_context import prepare_turn
from app.tutor_stream import CitationFilter, stream_tutor


app = create_app()
question = "请依据“1 班数学示例材料内容”，引导我学习方程；先告诉我下一步该做什么。"
exchanges = []
post = requests.post


class CapturedResponse:
    def __init__(self, response, record):
        self.response, self.record = response, record

    def __getattr__(self, name):
        return getattr(self.response, name)

    def iter_lines(self, *args, **kwargs):
        for line in self.response.iter_lines(*args, **kwargs):
            self.record["response_sse_lines"].append(line.decode("utf-8"))
            yield line


def capture_post(url, **kwargs):
    record = {
        "method": "POST",
        "url": url,
        "headers": {"Authorization": "Bearer [REDACTED]"},
        "request_json": copy.deepcopy(kwargs.get("json")),
    }
    exchanges.append(record)
    response = post(url, **kwargs)
    record["http_status"] = response.status_code
    if kwargs.get("stream"):
        record["response_sse_lines"] = []
        return CapturedResponse(response, record)
    record["response_json"] = response.json()
    return response


with app.app_context():
    db.session.execute(text("SET TRANSACTION READ ONLY"))
    agent = TutorAgent.query.filter_by(name="数学解题助手", enabled=True).order_by(TutorAgent.id).first()
    if agent is None:
        raise RuntimeError("An existing enabled mathematics agent is required")
    user = User.query.filter_by(class_id=agent.class_id, role="student", is_active=True).first()
    if user is None:
        raise RuntimeError("An existing same-class student is required")
    before = {
        table: db.session.execute(text("SELECT count(*) FROM " + table)).scalar()
        for table in ("conversations", "messages", "skills", "tutor_agents")
    }
    with patch("requests.post", capture_post):
        # Negative IDs ensure no user's conversation history enters this audit.
        messages, citations, selected = prepare_turn(
            SimpleNamespace(id=-1), agent, subject_scope(user), question, -1
        )
        provider = stream_tutor(messages)
        try:
            raw_answer = "".join(provider)
        finally:
            provider.close()
    filter_ = CitationFilter(len(citations))
    visible_answer = filter_.feed(raw_answer) + filter_.finish()
    skill = db.session.get(Skill, selected["id"]) if selected else None
    material_evidence = []
    for citation in citations:
        entry = KnowledgeEntry.query.filter_by(material_id=citation["material_id"]).one()
        material_evidence.append({
            "material_title": citation["material_title"],
            "full_body_code_points": len(entry.body_text),
            "sent_source_code_points": sum(len(s["text"]) for s in citation["source_segments"]),
            "source_segments": citation["source_segments"],
        })
    after = {
        table: db.session.execute(text("SELECT count(*) FROM " + table)).scalar()
        for table in before
    }
    assert before == after
    record = {
        "verification_kind": "real-provider-read-only-normal-turn",
        "database_writes": False,
        "conversation_history_included": False,
        "agent": {"id": agent.id, "name": agent.name, "configured_prompt": agent.prompt},
        "runtime": {
            "testing": app.testing,
            "chat_model": app.config["CHAT_MODEL"],
            "embedding_model": app.config["EMBEDDING_MODEL"],
            "mcp_enabled": app.config["MCP_ENABLED"],
        },
        "question": question,
        "selected_skill": None if skill is None else {
            "name": skill.name,
            "source_text": skill.source_text,
            "description": skill.description,
            "complete_description_in_system": skill.description in messages[0]["content"],
            "complete_source_file_in_messages": any(skill.source_text in m["content"] for m in messages),
        },
        "material_evidence": material_evidence,
        "provider_exchanges": exchanges,
        "raw_model_answer": raw_answer,
        "citation_filtered_answer": visible_answer,
        "database_counts_before": before,
        "database_counts_after": after,
    }
    serialized = json.dumps(record, ensure_ascii=False, indent=2)
    for key in ("CHAT_API_KEY", "EMBEDDING_API_KEY", "AUTH_TOKEN_SECRET", "SECRET_KEY", "MCP_TOKEN_ENCRYPTION_KEY"):
        secret = app.config.get(key)
        if secret:
            serialized = serialized.replace(secret, "[REDACTED]")
    print(serialized)
    db.session.rollback()
