import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("teaching_mcp", Path(__file__).parents[1] / "app.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)

@pytest.fixture
def client():
    return service.create_app("test-mcp-secret").test_client()

def send(client, method, params=None, identifier=7):
    return client.post("/mcp", json={"jsonrpc": "2.0", "id": identifier, "method": method, "params": params or {}}, headers={"Authorization": "Bearer test-mcp-secret"})

def test_auth_and_health(client):
    assert client.get("/health").status_code == 200
    for header in ({}, {"Authorization": "Bearer wrong"}):
        assert client.post("/mcp", json={}, headers=header).status_code == 401

def test_initialize_and_id(client):
    response = send(client, "initialize", {"protocolVersion": service.PROTOCOL_VERSION}, "request-1").json
    assert response["id"] == "request-1"
    assert response["result"]["protocolVersion"] == service.PROTOCOL_VERSION
    assert send(client, "initialize", {"protocolVersion": "bad"}).json["error"]["code"] == -32602

def test_rpc_errors_and_notifications(client):
    headers = {"Authorization": "Bearer test-mcp-secret"}
    assert client.post("/mcp", data="{", headers=headers).json["error"]["code"] == -32700
    for data in ([], {}, {"jsonrpc": "2.0", "method": "x", "id": True}):
        assert client.post("/mcp", json=data, headers=headers).json["error"]["code"] == -32600
    assert send(client, "unknown").json["error"]["code"] == -32601
    assert client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers).status_code == 204

def test_tools_are_hints(client):
    tools = send(client, "tools/list").json["result"]["tools"]
    assert {t["name"] for t in tools} == {"formula_hint", "unit_convert"}
    for name, query, forbidden in (("formula_hint", "化简 2-(3+x)", "-1-x"), ("unit_convert", "3米等于多少厘米", "300")):
        result = send(client, "tools/call", {"name": name, "arguments": {"query": query}}).json["result"]
        assert result["isError"] is False
        assert forbidden not in result["content"][0]["text"]
    assert send(client, "tools/call", {"name": "formula_hint", "arguments": {"query": "宇宙起源"}}).json["result"]["isError"] is True

@pytest.mark.parametrize("arguments", [{}, {"query": 42}, {"query": "a"}, {"query": "x" * 501}, {"query": "厘米", "extra": 1}])
def test_bad_arguments(client, arguments):
    assert send(client, "tools/call", {"name": "unit_convert", "arguments": arguments}).json["error"]["code"] == -32602
    assert send(client, "tools/call", {"name": "unknown", "arguments": {"query": "厘米"}}).json["error"]["code"] == -32602
