"""Real MCP HTTP + decision fixture + SSE + read-only DB assertions."""
import json
from uuid import uuid4

def base(c): return c.base_class + "/mcp/servers"
def item(c): return base(c) + f"/{c.state['mcp_server']['id']}"

def mcp_servers_create(c):
    name = "school_" + uuid4().hex[:8]
    body = {"name": name, "base_url": "http://mcp-demo:8090", "token": "disposable-mcp-token"}
    response = c.http("POST", base(c), json=body, operation="mcp_servers_create")
    assert response.status_code == 201
    c.state["mcp_server"] = response.json()["server"]
    assert "token_ciphertext" not in response.text and "disposable-mcp-token" not in response.text
    row = c.sql("SELECT token_ciphertext, connected FROM mcp_servers WHERE id=%s", (c.state["mcp_server"]["id"],))[0]
    assert row[0] != body["token"] and not row[1]
    assert c.http("POST", base(c), json=body, operation="mcp_servers_create").status_code == 400
    for role in ("student", "admin"):
        assert c.http("POST", base(c), auth=role, json=body, operation="mcp_servers_create").status_code == 403
    assert c.http("POST", base(c), auth=None, json=body, operation="mcp_servers_create").status_code == 401

def mcp_servers_list(c):
    assert c.state["mcp_server"]["id"] in [s["id"] for s in c.http("GET", base(c), operation="mcp_servers_list").json()["items"]]

def mcp_servers_get(c):
    c.login("foreign_teacher")
    foreign = c.http("GET", item(c), auth="foreign_teacher", operation="mcp_servers_get")
    missing = c.http("GET", base(c) + "/2147483647", operation="mcp_servers_get")
    assert foreign.status_code == missing.status_code == 404 and foreign.content == missing.content
    assert c.http("GET", item(c), operation="mcp_servers_get").status_code == 200

def mcp_servers_update(c):
    before = c.sql("SELECT token_ciphertext, configuration_revision FROM mcp_servers WHERE id=%s", (c.state["mcp_server"]["id"],))
    assert c.http("PUT", item(c), json={"token": ""}, operation="mcp_servers_update").status_code == 200
    assert c.sql("SELECT token_ciphertext, configuration_revision FROM mcp_servers WHERE id=%s", (c.state["mcp_server"]["id"],)) == before
    assert c.http("PUT", item(c), json={"base_url": "http://mcp-demo:8090/path"}, operation="mcp_servers_update").status_code == 400

def mcp_servers_connect(c):
    for _ in range(2):
        response = c.http("POST", item(c) + "/connect", operation="mcp_servers_connect")
        assert response.status_code == 200 and response.json()["server"]["connected"]
    assert c.sql("SELECT count(*) FROM mcp_tools WHERE server_id=%s", (c.state["mcp_server"]["id"],))[0][0] == 2

def mcp_servers_tools(c):
    tools = c.http("GET", item(c) + "/tools", operation="mcp_servers_tools").json()["items"]
    assert {t["name"] for t in tools} == {"formula_hint", "unit_convert"}
    assert all(t["description"] and t["inputSchema"]["required"] == ["query"] and t["permitted"] for t in tools)
    confirmations = {t["ref"]: t["declaration_hash"] for t in tools}
    source = f"名称：MCP验收{c.state['nonce']}\n适用条件：MCP括号,单位\n工具：knowledge_search，" + "，".join(confirmations) + "\n启用：是\n\n只给下一步提示，不给最终答案。"
    before = c.sql("SELECT count(*) FROM skills")[0][0]
    assert c.http("POST", c.base_class + "/skills", json={"source_text": source}, operation="skills_create").status_code == 400
    assert c.sql("SELECT count(*) FROM skills")[0][0] == before
    response = c.http("POST", c.base_class + "/skills", json={"source_text": source, "tool_confirmations": confirmations}, operation="skills_create")
    assert response.status_code == 201
    c.state["mcp_skill"] = response.json()["skill"]
    agent = c.create_agent("MCP" + c.state["nonce"], skill_ids=[c.state["mcp_skill"]["id"]])
    conv = c.create_conversation(agent["id"])["id"]; c.state["mcp_conversation"] = conv
    frames = c.stream(conv, "MCP括号和单位的两轮验收")
    assert frames[-1][0] == "done"
    metas = [v for n, v, _ in frames if n == "meta"]
    calls = metas[-1]["tool_calls"]
    assert [call["round"] for call in calls] == [1, 2] and all(call["status"] == "ok" for call in calls)
    assert len({call["call_id"] for call in calls}) == 2
    assert max(i for i, f in enumerate(frames) if f[0] == "meta") < min(i for i, f in enumerate(frames) if f[0] == "delta")
    rows = c.sql("SELECT call_id,round,status FROM mcp_tool_calls WHERE conversation_id=%s ORDER BY sequence", (conv,))
    assert rows == [(call["call_id"], call["round"], call["status"]) for call in calls]
    saved = c.sql("SELECT tool_calls_json FROM messages WHERE conversation_id=%s ORDER BY id", (conv,))
    assert saved == [(calls,), (calls,)]
    assert c.sql("SELECT mcp_attempt_count FROM conversations WHERE id=%s", (conv,))[0][0] == 2
    frames = c.stream(conv, "MCP括号 不调用工具")
    assert frames[-1][0] == "done" and all("tool_calls" not in v for n, v, _ in frames if n == "meta")
    for marker in ("非法参数验收", "伪造工具验收", "无限工具验收", "零正文失败验收", "部分失败验收"):
        frames = c.stream(conv, "MCP括号 " + marker)
        assert frames[-1][0] == ("error" if "失败" in marker else "done")
    c.state["mcp_calls"] = calls

def mcp_servers_disconnect(c):
    assert c.http("POST", item(c) + "/disconnect", operation="mcp_servers_disconnect").status_code == 200
    assert c.http("GET", item(c) + "/tools", operation="mcp_servers_tools").json()["items"] == []
    conv = c.state["mcp_conversation"]
    before = c.sql("SELECT mcp_attempt_count FROM conversations WHERE id=%s", (conv,))[0][0]
    frames = c.stream(conv, "MCP括号 断开后拒绝")
    assert frames[-1][0] == "done"
    calls = [v for n, v, _ in frames if n == "meta"][-1]["tool_calls"]
    assert len(calls) == 2 and all(call["status"] == "denied" and call["reason_code"] == "server_unavailable" for call in calls)
    assert c.sql("SELECT mcp_attempt_count FROM conversations WHERE id=%s", (conv,))[0][0] == before

def mcp_tool_calls_list(c):
    response = c.http("GET", c.base_class + "/mcp/tool-calls?limit=1", operation="mcp_tool_calls_list")
    assert response.status_code == 200 and response.json()["next_cursor"]
    first = response.json()["items"][0]
    following = c.http("GET", c.base_class + f"/mcp/tool-calls?limit=1&cursor={response.json()['next_cursor']}", operation="mcp_tool_calls_list").json()["items"][0]
    assert following["id"] < first["id"] and len(first["text"]) <= 200
    assert c.http("GET", c.base_class + "/mcp/tool-calls", auth="student", operation="mcp_tool_calls_list").status_code == 403
    assert c.http("GET", c.base_class + "/mcp/tool-calls", auth="foreign_teacher", operation="mcp_tool_calls_list").json()["items"] == []
    foreign_filter = c.http("GET", c.base_class + f"/mcp/tool-calls?server_id={c.state['mcp_server']['id']}", auth="foreign_teacher", operation="mcp_tool_calls_list")
    missing_filter = c.http("GET", c.base_class + "/mcp/tool-calls?server_id=2147483647", operation="mcp_tool_calls_list")
    assert foreign_filter.status_code == missing_filter.status_code == 404 and foreign_filter.content == missing_filter.content

def mcp_servers_delete(c):
    before = c.sql("SELECT server_id,server_name FROM mcp_tool_calls WHERE conversation_id=%s ORDER BY id", (c.state["mcp_conversation"],))
    assert c.http("DELETE", item(c), operation="mcp_servers_delete").status_code == 204
    rows = c.sql("SELECT server_id,server_name FROM mcp_tool_calls WHERE conversation_id=%s ORDER BY id", (c.state["mcp_conversation"],))
    assert rows == [(None, name) for identifier, name in before] and rows
