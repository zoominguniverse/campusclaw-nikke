import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.extensions import db
from app.models import MCPServer, MCPTool
from .test_postgres_integration import postgres_app, pytestmark
from .test_mcp_registry import remote, register, confirmed
from .test_mcp_tutor import model, setup_turn, turn
from .test_mcp_schema import check_schema, check_upgrade
from .conftest import BearerClient

@pytest.fixture
def app(postgres_app):
    postgres_app.test_client_class = BearerClient
    return postgres_app

def test_postgres_schema(app):
    check_schema(app)

def test_postgres_upgrade_twice(app):
    check_upgrade(app)

@pytest.mark.parametrize("action", ["disconnect", "update", "delete"])
def test_connect_cannot_publish_after_newer_operation(app, remote, monkeypatch, action):
    import app.mcp as registry
    origin, _ = remote
    client = app.test_client(); base = register(client, origin)
    confirmed(client, base)
    started, release = threading.Event(), threading.Event()
    original = registry.discover
    def delayed(*args):
        tools = original(*args)
        started.set()
        assert release.wait(10)
        return tools
    monkeypatch.setattr(registry, "discover", delayed)
    token = client.access_token
    def connect():
        other = app.test_client(); other.access_token = token
        return other.post(base + "/connect")
    with ThreadPoolExecutor(1) as executor:
        future = executor.submit(connect)
        try:
            assert started.wait(10)
            if action == "disconnect": assert client.post(base + "/disconnect").status_code == 200
            elif action == "update": assert client.put(base, json={"name": "changed"}).status_code == 200
            else: assert client.delete(base).status_code == 204
        finally:
            release.set()
        assert future.result(10).json == {"error": "connection_superseded"}
    with app.app_context():
        assert not MCPServer.query.filter_by(connected=True).first()
        assert MCPTool.query.count() == 0

def test_postgres_quota_persists_across_turns_and_model_multiple_calls(app, client, remote, model):
    from app.models import Conversation
    origin, state = remote
    _, _, _, conv = setup_turn(client, origin)
    with app.app_context():
        db.session.get(Conversation, conv).mcp_attempt_count = 29; db.session.commit()
    events = turn(client, conv)
    assert events[-1][0] == "done"
    with app.app_context():
        assert db.session.get(Conversation, conv).mcp_attempt_count == 30
    turn(client, conv)
    assert len([c for c in state["calls"] if c["method"] == "tools/call"]) == 1
