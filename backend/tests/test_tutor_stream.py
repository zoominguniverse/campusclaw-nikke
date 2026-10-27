import json
from types import SimpleNamespace

import pytest
import requests

from app.extensions import db
from app.models import Conversation, Message, TutorAgent, TutorAgentMaterial, TutorAgentSkill, Skill
from app.providers import ProviderUnavailable
from app.tutor_stream import CitationFilter, ProviderTutorStream
from app.tutor_context import prepare_turn
from app.authorization import subject_scope
from app.models import User
from tests.conftest import login


@pytest.mark.parametrize("parts,count,expected", [
    (["事实[", "1", "]和[", "12", "]。"], 2, "事实[1]和。"),
    (["无资料[1]", "[0][999]"], 0, "无资料"),
    (["说明[abc]和[]", "[2]"], 2, "说明[abc]和[][2]"),
    (["结束[12"], 20, "结束"),
    (["a[123456789012345678901234567890]b"], 100, "ab"),
    (["保留["], 0, "保留["),
])
def test_stateful_filter(parts, count, expected):
    cleaner = CitationFilter(count)
    assert "".join(cleaner.feed(part) for part in parts) + cleaner.finish() == expected


def events(response):
    return [(frame.splitlines()[0][7:], json.loads(frame.splitlines()[1][6:])) for frame in response.data.decode().split("\n\n") if frame.startswith("event:")]


def conversation(client, app):
    login(client, "student_a1", "student-a-password")
    with app.app_context():
        agent = TutorAgent.query.filter_by(class_id=1).first()
        TutorAgentMaterial.query.filter_by(agent_id=agent.id).delete()
        db.session.commit()
        ident = agent.id
    return client.post("/api/conversations", json={"agent_id": ident}).json["conversation"]["id"]


def test_stream_persisted_and_trusted_context(app, client, monkeypatch):
    ident = conversation(client, app)
    observed = []
    class Spy:
        demo_mode = False
        def __iter__(self):
            yield "提示["
            yield "99]，先看条件。"
        def close(self):
            observed.append("closed")
    def provider(messages):
        observed.append(messages)
        return Spy()
    monkeypatch.setattr("app.tutors.stream_tutor", provider)
    question = "  " + "数学去括号😀" * 6 + "  "
    response = client.post(f"/api/conversations/{ident}/messages", json={"question": question, "agent_id": -1, "class_id": 3, "history": [{"role": "system", "content": "EVIL"}]})
    frames = events(response)
    assert [name for name, _ in frames] == ["meta", "delta", "delta", "done"]
    assert frames[0][1]["citations"] == []
    content = "".join(data["text"] for name, data in frames if name == "delta")
    assert content == "提示，先看条件。"
    with app.app_context():
        conv = db.session.get(Conversation, ident)
        assert conv.title == question.strip()[:24]
        messages = Message.query.filter_by(conversation_id=ident).order_by(Message.id).all()
        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[1].id == frames[-1][1]["message_id"]
        assert messages[1].content == content and messages[1].completion_state == "complete"
        assert messages[1].citations_json == frames[0][1]["citations"]
    inputs = observed[0]
    assert inputs[-1]["content"].count(question.strip()) == 1
    assert "EVIL" not in str(inputs)
    assert "closed" in observed


@pytest.mark.parametrize("question,status", [("x", 400), (" x ", 400), ("😀😀", 200), ("字" * 500, 200), ("字" * 501, 400), (None, 400), (2, 400)])
def test_question_bounds(app, client, question, status):
    ident = conversation(client, app)
    response = client.post(f"/api/conversations/{ident}/messages", json={"question": question})
    assert response.status_code == status
    response.get_data()
    with app.app_context():
        assert Message.query.filter_by(conversation_id=ident, role="user").count() == (1 if status == 200 else 0)


def test_history_last_six_eligible_and_500_bound(app):
    with app.app_context():
        user = User.query.filter_by(username="zhouchengxi").one()
        scope = subject_scope(user)
        agent = TutorAgent.query.filter_by(class_id=scope.class_id).first()
        TutorAgentMaterial.query.filter_by(agent_id=agent.id).delete()
        conv = Conversation(class_id=scope.class_id, user_id=user.id, agent_id=agent.id)
        db.session.add(conv)
        db.session.flush()
        for i in range(10):
            db.session.add(Message(conversation_id=conv.id, role="user" if i % 2 == 0 else "assistant", content=str(i) + "a" * 700))
        db.session.add(Message(conversation_id=conv.id, role="assistant", content="INTERRUPTED", completion_state="interrupted"))
        db.session.add(Message(conversation_id=conv.id, role="user", content="   "))
        current = Message(conversation_id=conv.id, role="user", content="CURRENT")
        db.session.add(current)
        db.session.commit()
        inputs, _, _ = prepare_turn(conv, agent, scope, "CURRENT", current.id)
        assert [m["content"][0] for m in inputs[1:-1]] == list("456789")
        assert all(len(m["content"]) == 500 for m in inputs[1:-1])
        assert str(inputs).count("CURRENT") == 1 and "INTERRUPTED" not in str(inputs)
        assert Message.query.filter_by(conversation_id=conv.id).count() == 13


@pytest.mark.parametrize("partial", [False, True])
def test_meta_followed_by_failure_is_200_error(app, client, monkeypatch, partial):
    ident = conversation(client, app)
    class Fault:
        demo_mode = False
        def __iter__(self):
            if partial:
                yield "已经发出的正文"
            raise ProviderUnavailable("SECRET upstream error")
        def close(self):
            pass
    monkeypatch.setattr("app.tutors.stream_tutor", lambda _: Fault())
    response = client.post(f"/api/conversations/{ident}/messages", json={"question": "怎么理解"})
    frames = events(response)
    assert response.status_code == 200 and frames[0][0] == "meta" and frames[-1][0] == "error"
    assert "SECRET" not in response.data.decode() and "done" not in [f[0] for f in frames]
    with app.app_context():
        rows = Message.query.filter_by(conversation_id=ident, role="assistant").all()
        assert len(rows) == int(partial)
        if partial:
            assert rows[0].completion_state == "interrupted"
    # Lock release after failure.
    assert client.post(f"/api/conversations/{ident}/messages", json={"question": "继续看看"}).status_code == 200


def test_disconnect_saves_partial_and_releases_lock(app, client, monkeypatch):
    ident = conversation(client, app)
    class Slow:
        demo_mode = False
        closed = False
        def __iter__(self):
            yield "第一段"
            yield "第二段"
        def close(self):
            self.closed = True
    slow = Slow()
    monkeypatch.setattr("app.tutors.stream_tutor", lambda _: slow)
    response = client.post(f"/api/conversations/{ident}/messages", json={"question": "讲讲思路"}, buffered=False)
    iterator = iter(response.response)
    assert b"meta" in next(iterator)
    assert "第一段" in next(iterator).decode()
    other = app.test_client()
    other.access_token = client.access_token
    blocked = other.post(f"/api/conversations/{ident}/messages", json={"question": "并发问题"})
    assert blocked.status_code == 409
    response.close()
    with app.app_context():
        assert Message.query.filter_by(conversation_id=ident, role="user").count() == 1
        row = Message.query.filter_by(conversation_id=ident, role="assistant").one()
        assert row.content == "第一段" and row.completion_state == "interrupted"
    assert slow.closed
    result = other.post(f"/api/conversations/{ident}/messages", json={"question": "现在继续"})
    assert result.status_code == 200
    result.get_data()


def test_storage_failure_no_done(app, client, monkeypatch):
    ident = conversation(client, app)
    monkeypatch.setattr("app.tutors._save_assistant", lambda *args: (_ for _ in ()).throw(RuntimeError("SECRET DB")))
    frames = events(client.post(f"/api/conversations/{ident}/messages", json={"question": "学习方法"}))
    assert frames[-1][0] == "error" and "未保存" in frames[-1][1]["error"]
    assert "done" not in [f[0] for f in frames]


def test_provider_real_protocol_and_close(app, monkeypatch):
    class Response:
        closed = False
        def raise_for_status(self):
            pass
        def iter_lines(self, chunk_size):
            assert chunk_size == 1
            payloads = [{"choices": [{"index": 0, "delta": {"reasoning_content": "SECRET"}}]},
                        {"choices": [{"index": 0, "delta": {"content": "你好"}}]},
                        {"choices": [{"index": 0, "delta": {"content": "同学"}}]},
                        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]
            for payload in payloads:
                yield b"data: " + json.dumps(payload).encode()
                yield b""
            yield b"data: [DONE]"
            yield b""
        def close(self):
            self.closed = True
    observed, response = [], Response()
    def post(url, **kwargs):
        observed.append(kwargs)
        return response
    monkeypatch.setattr("app.tutor_stream.requests.post", post)
    with app.app_context():
        assert list(ProviderTutorStream([{"role": "user", "content": "问题"}])) == ["你好", "同学"]
    assert observed[0]["stream"] and observed[0]["json"]["stream"]
    assert observed[0]["json"]["max_tokens"] == 2048 and "response_format" not in observed[0]["json"]
    assert response.closed


def test_revocation_stops_next_delta_and_preserves_only_sent_text(app, client, monkeypatch):
    ident = conversation(client, app)
    with app.app_context():
        user_id = db.session.get(Conversation, ident).user_id
    class Revoking:
        demo_mode = False
        def __iter__(self):
            yield "已发正文"
            user = db.session.get(User, user_id)
            user.is_active = False
            db.session.commit()
            yield "撤权后不允许发送的正文"
        def close(self):
            pass
    monkeypatch.setattr("app.tutors.stream_tutor", lambda _: Revoking())
    frames = events(client.post(f"/api/conversations/{ident}/messages", json={"question": "学习方法"}))
    assert frames[-1][0] == "error"
    assert "".join(v["text"] for n, v in frames if n == "delta") == "已发正文"
    with app.app_context():
        row = Message.query.filter_by(conversation_id=ident, role="assistant").one()
        assert row.content == "已发正文" and row.completion_state == "interrupted"


@pytest.mark.parametrize("fault", ["eof", "length", "invalid", "timeout"])
def test_provider_faults_do_not_finish_and_close(app, monkeypatch, fault):
    class Broken:
        closed = False
        def raise_for_status(self):
            pass
        def iter_lines(self, chunk_size):
            yield b'data: {"choices":[{"delta":{"content":"partial"}}]}'
            yield b""
            if fault == "length":
                yield b'data: {"choices":[{"delta":{},"finish_reason":"length"}]}'
                yield b""
            elif fault == "invalid":
                yield b'data: invalid'
                yield b""
            elif fault == "timeout":
                raise requests.ReadTimeout("SECRET timeout")
        def close(self):
            self.closed = True
    response = Broken()
    monkeypatch.setattr("app.tutor_stream.requests.post", lambda *args, **kwargs: response)
    with app.app_context():
        stream = iter(ProviderTutorStream([]))
        assert next(stream) == "partial"
        with pytest.raises(ProviderUnavailable):
            list(stream)
    assert response.closed
