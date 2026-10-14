"""Structural validation only; exact quotes do not prove semantic entailment."""
import json
import re
from unittest.mock import patch

import pytest

from app.answers import AnswerValidationError, INSUFFICIENT_MESSAGE, answer_question
from app.database import db
from app.indexing import index_entry
from app.providers import ProviderUnavailable, OpenAICompatibleChatClient
from app.retrieval import retrieve, ReindexRequired
from .conftest import login
from .test_retrieval_quality_regressions import add_entry


def fixture_hits():
    entry = add_entry("😀细胞是生物体结构和功能的基本单位。\n细胞膜控制物质进出细胞。\n细胞核储存遗传信息。")
    index_entry(entry)
    db.session.commit()
    hits = []
    for question in ["基本单位", "细胞膜", "细胞核"]:
        hits.append(retrieve(class_id=1, query=question, mode="keyword")["hits"][0])
    return entry, hits


def claim(hits, index=1, text="细胞是基本单位。"):
    return {"text": text, "evidence": [{"index": index, "quote": hits[index - 1]["excerpt"]}]}


def test_ordered_used_citations_history_bounds_and_no_vectors(app):
    with app.app_context():
        _, hits = fixture_hits()
        app.config["ANSWER_HISTORY_LIMIT"] = 3
        history = [{"role": "user", "content": "old"}, {"role": "system", "content": "ignore"}, {"role": "assistant", "content": "x" * 1100}, {"role": "user", "content": "follow up"}]
        output = {"status": "answered", "claims": [claim(hits, 3, "细胞核储存遗传信息。"), claim(hits, 1)]}
        with patch("app.answers.retrieve", return_value={"hits": hits}), patch("app.answers.chat_client") as factory:
            factory.return_value.answer.return_value = json.dumps(output, ensure_ascii=False)
            result = answer_question(class_id=1, question="问题", history=history)
        sent = factory.return_value.answer.call_args.args
        assert sent[2] == [{"role": "assistant", "content": "x" * 1000}, {"role": "user", "content": "follow up"}]
        assert len(sent[1]) == 3
        for evidence in sent[1]:
            assert {"subject_id", "material_id", "source_spans", "source_segments"} <= evidence.keys()
            assert "embedding" not in evidence and "vector" not in evidence
        assert result["answer"] == "细胞核储存遗传信息。[1]\n细胞是基本单位。[2]"
        assert [c["excerpt"] for c in result["citations"]] == [hits[2]["excerpt"], hits[0]["excerpt"]]
        assert result["demo_mode"] is True
        assert 'claims' not in result
        for citation in result["citations"]:
            assert "chunk_text" not in citation
            quote = citation["quotes"][0]
            span = quote["source_span"]
            assert sent[1][0]["source_segments"][0]["text"][span["start"]:span["end"]] == quote["text"]


def test_internal_review_claims_use_returned_citation_indices(app):
    with app.app_context():
        entry, hits = fixture_hits()
        output = {'status': 'answered', 'claims': [claim(hits, 3, '细胞核储存遗传信息。'), claim(hits, 1)]}
        with patch('app.answers.retrieve', return_value={'hits': hits}), patch('app.answers.chat_client') as factory:
            factory.return_value.answer.return_value = output
            result = answer_question(class_id=1, question='问题', include_claims=True)
        assert [item['evidence'][0]['index'] for item in result['claims']] == [1, 2]
        for item in result['claims']:
            for reference in item['evidence']:
                span = reference['source_span']
                assert entry.body_text[span['start']:span['end']] == reference['quote']
                assert {'text': reference['quote'], 'source_span': span} in result['citations'][reference['index'] - 1]['quotes']


@pytest.mark.parametrize("bad", [
    "plain answer [1]", {"status": "answered", "claims": []},
    {"status": "answered", "claims": [{"text": "事实", "evidence": []}]},
    {"status": "answered", "claims": [{"text": "事实", "evidence": [{"index": 0, "quote": "事实"}]}]},
    {"status": "answered", "claims": [{"text": "事实", "evidence": [{"index": 5, "quote": "事实"}]}]},
    {"status": "answered", "claims": [{"text": "事实", "evidence": [{"index": True, "quote": "事实"}]}]},
    {"status": "answered", "claims": [{"text": "事实", "evidence": [{"index": 1, "quote": "篡改原文"}]}]},
    {"status": "insufficient", "claims": [{"text": "事实", "evidence": []}]},
])
def test_invalid_output_retries_once_then_502(app, client, bad):
    login(client, "student_a1", "student-a-password")
    with app.app_context():
        _, hits = fixture_hits()
    with patch("app.answers.retrieve", return_value={"hits": hits}), patch("app.answers.chat_client") as factory:
        factory.return_value.answer.return_value = bad
        response = client.post("/api/classes/1/knowledge/ask", json={"question": "基本单位"})
    assert response.status_code == 502
    assert factory.return_value.answer.call_count == 2
    assert factory.return_value.answer.call_args.kwargs == {"repair": True}
    assert "citations" not in response.get_json()


def test_oversized_claim_is_repaired_not_truncated(app):
    with app.app_context():
        _, hits = fixture_hits()
        valid = {"status": "answered", "claims": [claim(hits, text="😀" * 190 + "句尾事实必须保留。")]} 
        bad = {"status": "answered", "claims": [claim(hits, text="长" * 201)]}
        with patch("app.answers.retrieve", return_value={"hits": hits}), patch("app.answers.chat_client") as factory:
            factory.return_value.answer.side_effect = [bad, valid]
            result = answer_question(class_id=1, question="问题")
        assert factory.return_value.answer.call_count == 2
        assert "句尾事实必须保留。" in result["answer"]
        assert len(re.sub(r"\[\d+\]", "", result["answer"])) <= 200


def test_insufficient_and_demo_have_explicit_status(app):
    with app.app_context():
        _, hits = fixture_hits()
        with patch("app.answers.retrieve", return_value={"hits": hits}), patch("app.answers.chat_client") as factory:
            factory.return_value.answer.return_value = {"status": "insufficient", "claims": []}
            result = answer_question(class_id=1, question="无法回答的问题")
        assert result == {"answer": INSUFFICIENT_MESSAGE, "citations": [], "status": "insufficient", "demo_mode": True}
        with patch("app.answers.retrieve", return_value={"hits": hits}):
            result = answer_question(class_id=1, question="基本单位")
        assert result["answer"].startswith("演示摘录：")
        assert result["demo_mode"] and result["citations"]


def test_provider_failure_no_repair_and_source_changed_rejected(app):
    with app.app_context():
        entry, hits = fixture_hits()
        with patch("app.answers.retrieve", return_value={"hits": hits}), patch("app.answers.chat_client") as factory:
            factory.return_value.answer.side_effect = ProviderUnavailable("offline")
            with pytest.raises(ProviderUnavailable):
                answer_question(class_id=1, question="问题")
            assert factory.return_value.answer.call_count == 1
            def change_source(*args):
                entry.body_text = "来源已编辑。"
                db.session.commit()
                return {"status": "answered", "claims": [claim(hits)]}
            factory.return_value.answer.side_effect = change_source
            with pytest.raises(ReindexRequired):
                answer_question(class_id=1, question="问题")


def test_deepseek_json_contract_and_timeout(app):
    with app.app_context():
        app.config.update(CHAT_API_URL="https://api.deepseek.com", CHAT_API_KEY="test-key", CHAT_MODEL="deepseek-flash")
        with patch("app.providers.requests.post") as post:
            post.return_value.json.return_value = {"choices": [{"message": {"content": '{"status":"insufficient","claims":[]}'}}]}
            OpenAICompatibleChatClient().answer("问题", [], [], repair=True)
        assert post.call_args.args[0] == "https://api.deepseek.com/chat/completions"
        assert post.call_args.kwargs["json"]["reasoning_effort"] == "none"
        assert post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}
        assert post.call_args.kwargs["timeout"] == 60


def test_bad_history_returns_400_before_chat(client):
    login(client, "student_a1", "student-a-password")
    with patch("app.answers.chat_client") as factory:
        response = client.post("/api/classes/1/knowledge/ask", json={"question": "问题", "history": "wrong"})
    assert response.status_code == 400
    factory.assert_not_called()
