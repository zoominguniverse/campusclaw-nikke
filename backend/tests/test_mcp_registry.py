import copy
import importlib.util
import json
import threading
import time
from io import BytesIO
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
from flask import Flask, jsonify, request, Response
from werkzeug.serving import make_server
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app.extensions import db
from app.models import MCPServer, MCPTool, SkillMCPBinding, Skill, Conversation, Message, MCPToolCall, User, TutorAgent
from app.mcp_client import discover, rpc
from app.mcp_policy import MCPError, validate_mcp_config, encrypt_token, decrypt_token, normalize_origin
from app.tutor_skills import parse_skill, SkillInputError
from .conftest import login

spec = importlib.util.spec_from_file_location("mcp_service_fixture", Path(__file__).parents[2] / "mcp-server" / "app.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)
SOURCE = "名称：工具解题引导\n适用条件：括号，单位\n资料：\n工具：knowledge_search，formula_hint@school，unit_convert@school\n启用：是\n\n引导学生检查步骤，不给最终答案。"

@pytest.fixture
def remote(app):
    remote_app = Flask("mcp-http-fixture")
    state = {"mode": "normal", "calls": [], "description": "给出下一步检查提示", "delay": 0}
    @remote_app.post("/mcp")
    def dispatch():
        body = request.json
        state["calls"].append(copy.deepcopy(body))
        assert request.headers.get("Authorization") == "Bearer disposable-mcp-token"
        if state["delay"]: time.sleep(state["delay"])
        mode = state["mode"]
        if mode == "401": return jsonify(error="disposable-mcp-token"), 401
        if mode == "redirect": return "", 302, {"Location": "http://127.0.0.1:1/"}
        if mode == "oversize": return " " * (256 * 1024 + 1)
        if mode == "slow":
            def slow():
                for _ in range(30):
                    yield " "
                    time.sleep(.03)
            return Response(slow(), mimetype="application/json")
        if body["method"] == "initialize":
            result = {"protocolVersion": "bad" if mode == "version" else service.PROTOCOL_VERSION}
        elif body["method"] == "tools/list":
            tools = copy.deepcopy(service.TOOLS)
            tools[0]["description"] = state["description"]
            if mode == "schema": tools[0]["inputSchema"] = {"type": "object", "$ref": "http://evil/schema"}
            if mode == "huge_schema": tools[0]["inputSchema"]["description"] = "x" * 17000
            if mode == "duplicate": tools += [tools[0]]
            if mode in {"pages", "cycle"}:
                result = {"tools": tools[:1] if not body["params"] else tools[1:]}
                if not body["params"] or mode == "cycle": result["nextCursor"] = "page-two"
            elif mode == "half_fail" and body["params"]: return jsonify(error="bad"), 503
            elif mode == "half_fail": result = {"tools": tools[:1], "nextCursor": "page-two"}
            else: result = {"tools": tools[:1] if mode == "removed" else tools}
        else:
            result = service.tool_result(body["params"]["name"], body["params"]["arguments"])
        return jsonify(jsonrpc="2.0", id="wrong" if mode == "id" else body["id"], result=result)
    server = make_server("127.0.0.1", 0, remote_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    app.config.update(MCP_ENABLED=True, MCP_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(), MCP_TOOL_POLICY_JSON=json.dumps({origin: {"formula_hint": "read", "unit_convert": "read"}}))
    validate_mcp_config(app.config)
    yield origin, state
    server.shutdown()
    thread.join(2)

def register(client, origin, name="school"):
    login(client, "teacher_a", "teacher-password")
    response = client.post("/api/classes/1/mcp/servers", json={"name": name, "base_url": origin + "/", "token": "disposable-mcp-token"})
    assert response.status_code == 201, response.json
    return f"/api/classes/1/mcp/servers/{response.json['server']['id']}"

def confirmed(client, base):
    assert client.post(base + "/connect").status_code == 200
    return {t["ref"]: t["declaration_hash"] for t in client.get(base + "/tools").json["items"]}

def test_config_and_encryption(app, remote):
    with app.app_context():
        ciphertext = encrypt_token("private-token")
        assert "private-token" not in ciphertext and decrypt_token(ciphertext) == "private-token"
        with pytest.raises(MCPError): decrypt_token("bad")
    for values in ({"MCP_TOKEN_ENCRYPTION_KEY": ""}, {"MCP_TOKEN_ENCRYPTION_KEY": "bad"}, {"MCP_TOOL_POLICY_JSON": '{"http://example.com/path":{}}'}, {"MCP_TOOL_POLICY_JSON": '{"http://example.com":{"write":"write"}}'}, {"MCP_MAX_ROUNDS": 4}):
        config = dict(app.config); config.update(values)
        with pytest.raises(RuntimeError): validate_mcp_config(config)
    config = dict(app.config); config.update(MCP_ENABLED=False, MCP_TOKEN_ENCRYPTION_KEY="", MCP_TOOL_POLICY_JSON="{}")
    validate_mcp_config(config)
    for bad in ("http://x/path", "http://a:b@x", "ftp://x", "http://x?y=1", "http://x#f", "http://x\\y", "http://x:bad"):
        with pytest.raises(MCPError): normalize_origin(bad)

def test_registry_scopes_crud_cache_and_token(app, client, remote):
    origin, state = remote
    assert client.get("/api/classes/1/mcp/servers").status_code == 401
    base = register(client, origin)
    registered = client.get(base).json["server"]
    assert registered["has_token"] and registered["base_url"] == origin
    assert "token" not in registered and "disposable-mcp-token" not in str(registered)
    assert client.post("/api/classes/1/mcp/servers", json={"name": "school", "base_url": origin, "token": "x"}).status_code == 400
    confirmations = confirmed(client, base)
    revision = client.get(base).json["server"]["configuration_revision"]
    assert len(confirmations) == 2
    assert len(confirmed(client, base)) == 2
    state["mode"] = "removed"
    assert len(confirmed(client, base)) == 1
    assert client.put(base, json={"token": ""}).json["server"]["connected"]
    assert client.put(base, json={"name": "renamed"}).json["server"]["configuration_revision"] == revision + 1
    assert client.get(base + "/tools").json["items"] == []
    login(client, "teacher_b", "teacher-b-password")
    missing = client.get("/api/classes/2/mcp/servers/999999")
    for method, suffix in (("get", ""), ("put", ""), ("delete", ""), ("post", "/connect"), ("post", "/disconnect"), ("get", "/tools")):
        result = getattr(client, method)(base + suffix, json={} if method in {"put", "post"} else None)
        assert result.status_code == 404 and result.data == missing.data
    # Same server name in a different effective class is allowed.
    assert client.post("/api/classes/1/mcp/servers", json={"name": "school", "base_url": origin, "token": "x"}).status_code == 201
    for username, password in (("student_a1", "student-a-password"), ("super_admin", "super-admin-password"), ("class_admin_a", "class-admin-a-password")):
        login(client, username, password)
        assert client.get(base).status_code == 403
        assert client.get("/api/classes/1/mcp/tool-calls").status_code == 403

@pytest.mark.parametrize("mode", ["401", "redirect", "oversize", "version", "id", "schema", "huge_schema", "duplicate", "cycle", "half_fail"])
def test_failed_discovery_leaves_no_active_cache(app, client, remote, mode):
    origin, state = remote
    base = register(client, origin)
    confirmed(client, base)
    state["mode"] = mode
    response = client.post(base + "/connect")
    assert response.status_code == 502
    assert "disposable-mcp-token" not in response.text
    assert not client.get(base).json["server"]["connected"]
    assert client.get(base + "/tools").json["items"] == []

def test_transport_policy_pagination_deadline_and_proxy(app, remote, monkeypatch):
    origin, state = remote
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    state["mode"] = "pages"
    with app.app_context():
        assert len(discover(origin, "disposable-mcp-token")) == 2
        with pytest.raises(MCPError, match="origin_not_allowed"):
            rpc("http://127.0.0.1:1", "secret", "tools/list", {})
        state["mode"] = "slow"
        started = time.monotonic()
        with pytest.raises(MCPError, match="remote_timeout"):
            rpc(origin, "disposable-mcp-token", "tools/list", {}, started + .15)
        assert time.monotonic() - started < .5

def test_bindings_atomic_review_reconnect_and_recreation(app, client, remote):
    origin, state = remote
    base = register(client, origin)
    confirmations = confirmed(client, base)
    path = "/api/classes/1/skills"
    assert client.post(path, json={"source_text": SOURCE}).json["error"] == "binding_review_required"
    response = client.post(path, data={"file": (BytesIO(SOURCE.encode()), "skill.txt"), "tool_confirmations": json.dumps(confirmations)})
    assert response.status_code == 201, response.json
    skill = response.json["skill"]
    path += f"/{skill['id']}"
    bad = SOURCE.replace("unit_convert@school", "unit_convert@missing")
    assert client.put(path, json={"source_text": bad}).status_code == 404
    assert client.get(path).json["skill"] == skill
    client.post(base + "/disconnect")
    assert client.put(path, json={"source_text": SOURCE}).status_code == 400
    confirmed(client, base)
    assert client.put(path, json={"source_text": SOURCE}).status_code == 200
    assert client.put(path, json={"source_text": SOURCE, "tool_confirmations": {"formula_hint@school": "0" * 64}}).status_code == 400
    state["description"] = "声明已变化，需要重新审阅"
    changed = confirmed(client, base)
    assert client.put(path, json={"source_text": SOURCE}).status_code == 400
    assert client.put(path, json={"source_text": SOURCE, "tool_confirmations": changed}).status_code == 200
    client.put(base, json={"token": "disposable-mcp-token"})
    confirmed(client, base)
    assert client.put(path, json={"source_text": SOURCE}).status_code == 400
    assert client.put(path, json={"source_text": SOURCE, "tool_confirmations": changed}).status_code == 200
    assert client.delete(base).status_code == 204
    with app.app_context():
        assert all(b.server_id is None for b in SkillMCPBinding.query.filter_by(skill_id=skill["id"]))
    register(client, origin)
    base2 = f"/api/classes/1/mcp/servers/{client.get('/api/classes/1/mcp/servers').json['items'][0]['id']}"
    confirmed(client, base2)
    assert client.put(path, json={"source_text": SOURCE}).status_code == 400

def test_parser_mcp_refs_and_legacy():
    assert parse_skill(SOURCE)["tools_json"] == ["knowledge_search", "formula_hint@school", "unit_convert@school"]
    assert parse_skill(SOURCE.replace("formula_hint@school", "knowledge_search"))["tools_json"].count("knowledge_search") == 1
    for invalid in ("Formula@school", "formula-hint@school", "formula_hint", "tool@School", "tool@"):
        with pytest.raises(SkillInputError): parse_skill(SOURCE.replace("formula_hint@school", invalid))
    assert parse_skill(SOURCE.replace("formula_hint@school，unit_convert@school", "knowledge_search"))["tools_json"] == ["knowledge_search"]
