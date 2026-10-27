"""Each exported scenario belongs to its corresponding URL/method case file."""
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import requests


def prompt_templates_list(c):
    response = c.http('GET', c.base_class + '/prompt-templates', operation='prompt_templates_list')
    assert response.status_code == 200 and len(response.json()['items']) == 6
    assert c.http('GET', c.base_class + '/prompt-templates', auth='student', operation='prompt_templates_list').status_code == 403


def prompt_templates_render(c):
    before = c.sql('SELECT count(*) FROM tutor_agents')[0][0]
    response = c.http('POST', c.base_class + '/prompt-templates/lesson-plan/render', json={'variables': {'subject': '数学', 'topic': '分数', 'minutes': '35'}}, operation='prompt_templates_render')
    assert response.status_code == 200 and '35分钟' in response.json()['template']['prompt']
    assert c.http('POST', c.base_class + '/prompt-templates/lesson-plan/render', json={'variables': {'minutes': '0'}}, operation='prompt_templates_render').status_code == 400
    assert c.sql('SELECT count(*) FROM tutor_agents')[0][0] == before


def auth_login(c):
    for role in ("teacher", "student", "classmate", "foreign", "admin"):
        data = c.login(role)
        rows = c.sql("SELECT t.token_hash, t.token_type, s.user_id, s.revoked_at FROM auth_tokens t JOIN sessions s ON s.id=t.session_id WHERE s.user_id=%s AND s.revoked_at IS NULL", (data["user"]["id"],))
        assert len(rows) == 2 and {r[1] for r in rows} == {"access", "refresh"}
        assert all(r[0] not in (data["access_token"], data["refresh_token"]) and len(r[0]) == 64 for r in rows)
    before = c.sql("SELECT count(*) FROM auth_tokens")[0][0]
    assert c.http("POST", "/api/auth/login", auth=None, json={"username": "nonexistent", "password": "bad"}, operation="auth_login").status_code == 401
    assert c.sql("SELECT count(*) FROM auth_tokens")[0][0] == before
    c.state["nonce"] = uuid4().hex[:8]


def auth_me(c):
    assert c.http("GET", "/api/auth/me", auth="student", operation="auth_me").json()["user"] == c.users["student"]
    assert c.http("GET", "/api/auth/me", auth=None, operation="auth_me").status_code == 401


def materials_upload(c):
    c.state["subject"] = c.sql("SELECT subject_id FROM teacher_subject_assignments WHERE teacher_id=%s AND is_active", (c.users["teacher"]["id"],))[0][0]
    body = "😀数学去括号时检查每一项是否乘到系数。分数相加要检查分母。\n<script>window.fixtureUnsafe=true</script>\n"
    response = c.http("POST", c.base_class + "/materials", files={"file": ("lesson5.md", body.encode(), "text/markdown")}, data={"subject_id": c.state["subject"], "title": "数学API验收" + c.state["nonce"]}, operation="materials_upload")
    assert response.status_code == 201 and response.json()["indexing"]["status"] == "ready"
    c.state["material"] = response.json()["material"]
    c.state["source"] = body
    rows = c.sql("SELECT class_id, subject_id FROM materials WHERE id=%s", (c.state["material"]["id"],))
    assert rows == [(c.users["teacher"]["class_id"], c.state["subject"])]
    assert c.sql("SELECT count(*) FROM knowledge_chunks WHERE material_id=%s AND index_status='ready'", (c.state["material"]["id"],))[0][0] > 0
    before = c.sql("SELECT count(*) FROM materials")[0][0]
    assert c.http("POST", c.base_class + "/materials", auth="student", files={"file": ("bad.txt", b"bad")}, data={"subject_id": c.state["subject"]}).status_code == 403
    assert c.sql("SELECT count(*) FROM materials")[0][0] == before


def materials_list(c):
    data = c.http("GET", c.base_class + "/materials", operation="materials_list").json()
    assert c.state["material"]["id"] in [item["id"] for item in data["items"]]
    assert all(item["subject_id"] == c.state["subject"] for item in data["items"])
    assert c.http("GET", c.base_class + "/materials", auth=None, operation="materials_list").status_code == 401


def materials_get(c):
    path = c.base_class + "/materials/" + c.state["material"]["id"]
    data = c.http("GET", path, operation="materials_get").json()
    assert data["body_text"] == c.state["source"]
    assert data["source_hash"] == c.sql("SELECT source_hash FROM knowledge_index_generations g JOIN knowledge_entries e ON e.id=g.knowledge_entry_id WHERE e.material_id=%s AND g.status='ready'", (c.state["material"]["id"],))[0][0]
    assert c.http("GET", path, auth="foreign", operation="materials_get").status_code == 404


def materials_download(c):
    response = c.http("GET", c.base_class + "/materials/" + c.state["material"]["id"] + "/download", operation="materials_download")
    assert response.status_code == 200 and response.content.decode() == c.state["source"]
    assert "attachment" in response.headers["Content-Disposition"]


def materials_reindex(c):
    material_id = c.state["material"]["id"]
    previous = c.sql("SELECT id FROM knowledge_index_generations WHERE knowledge_entry_id=(SELECT id FROM knowledge_entries WHERE material_id=%s) AND status='ready'", (material_id,))[0][0]
    response = c.http("POST", c.base_class + f"/materials/{material_id}/reindex", json={"chunking": {"strategy": "hierarchy"}}, operation="materials_reindex")
    assert response.status_code == 200 and response.json()["indexing"]["status"] == "ready"
    assert c.sql("SELECT status FROM knowledge_index_generations WHERE id=%s", (previous,))[0][0] == "retired"


def materials_update(c):
    material_id = c.state["material"]["id"]
    title = "数学改名验收" + c.state["nonce"]
    response = c.http("PUT", c.base_class + f"/materials/{material_id}", json={"title": title}, operation="materials_update")
    assert response.status_code == 200 and c.sql("SELECT title FROM materials WHERE id=%s", (material_id,))[0][0] == title


def knowledge_retrieve(c):
    response = c.http("POST", c.base_class + "/knowledge/retrieve", json={"query": "数学去括号", "mode": "hybrid", "subject_id": c.state["subject"]}, operation="knowledge_retrieve")
    hits = response.json()["hits"]
    assert response.status_code == 200 and hits
    assert all(hit["subject_id"] == c.state["subject"] for hit in hits)
    for hit in hits:
        assert c.sql("SELECT class_id, subject_id FROM knowledge_chunks WHERE id=%s", (hit["chunk_id"],))[0] == (1, c.state["subject"])
    c.state["hit"] = next(hit for hit in hits if hit["material_id"] == c.state["material"]["id"])
    assert c.http("POST", c.base_class + "/knowledge/retrieve", auth=None, json={"query": "数学"}, operation="knowledge_retrieve").status_code == 401
    foreign = c.http("POST", c.base_class + "/knowledge/retrieve", auth="foreign", json={"query": "数学", "mode": "keyword"}, operation="knowledge_retrieve").json()
    assert all(hit["material_id"] != c.state["material"]["id"] for hit in foreign["hits"])


def knowledge_evidence(c):
    hit = c.state["hit"]
    response = c.http("GET", c.base_class + f"/knowledge/chunks/{hit['chunk_id']}?source_hash={hit['source_hash']}", operation="knowledge_evidence")
    assert response.status_code == 200 and response.json()["evidence"]["material_id"] == hit["material_id"]
    assert c.http("GET", c.base_class + f"/knowledge/chunks/{hit['chunk_id']}", auth="foreign", operation="knowledge_evidence").status_code == 404


def knowledge_ask(c):
    response = c.http("POST", c.base_class + "/knowledge/ask", json={"question": "数学去括号"}, operation="knowledge_ask")
    assert response.status_code == 200 and len(response.json()["answer"]) <= 200
    no_evidence = c.http("POST", c.base_class + "/knowledge/ask", json={"question": "数学去括号", "subject_id": 2147483647}, operation="knowledge_ask").json()
    assert no_evidence["status"] == "no_evidence" and no_evidence["citations"] == []


def skills_create(c):
    skill = c.create_skill(c.state["nonce"])
    c.state["skill"] = skill
    assert c.sql("SELECT source_text, enabled, created_by FROM skills WHERE id=%s", (skill["id"],)) == [(skill["source_text"], True, c.users["teacher"]["id"])]
    before = c.sql("SELECT count(*) FROM skills")[0][0]
    for source in (skill["source_text"], "名称：非法\n启用：是\n\n正文", skill["source_text"].replace("knowledge_search", "shell")):
        assert c.http("POST", c.base_class + "/skills", json={"source_text": source}, operation="skills_create").status_code == 400
    assert c.sql("SELECT count(*) FROM skills")[0][0] == before
    assert c.http("POST", c.base_class + "/skills", auth="student", json={"source_text": skill["source_text"]}, operation="skills_create").status_code == 403
    foreign = c.http("GET", "/api/classes/2/skills", auth="foreign", operation="skills_list").json()["items"]
    c.state["foreign_skill"] = foreign[0]["id"]


def skills_list(c):
    items = c.http("GET", c.base_class + "/skills", auth="student", operation="skills_list").json()["items"]
    assert c.state["skill"]["id"] in [item["id"] for item in items]
    assert all(item["class_id"] == 1 for item in items)


def skills_get(c):
    skill = c.state["skill"]
    assert c.http("GET", c.base_class + f"/skills/{skill['id']}", operation="skills_get").json()["skill"]["source_text"] == skill["source_text"]
    foreign = c.http("GET", c.base_class + f"/skills/{c.state['foreign_skill']}", operation="skills_get")
    missing = c.http("GET", c.base_class + "/skills/2147483647", operation="skills_get")
    assert foreign.status_code == missing.status_code == 404 and foreign.content == missing.content


def skills_update(c):
    skill = c.state["skill"]
    source = "\ufeff" + skill["source_text"].replace("\n", "\r\n")
    response = c.http("PUT", c.base_class + f"/skills/{skill['id']}", files={"file": ("skill.txt", source.encode(), "text/plain")}, operation="skills_update")
    assert response.status_code == 200 and response.json()["skill"]["source_text"] == source
    assert c.sql("SELECT source_text, updated_by FROM skills WHERE id=%s", (skill["id"],))[0] == (source, c.users["teacher"]["id"])
    c.state["skill"] = response.json()["skill"]


def agents_create(c):
    agent = c.create_agent(c.state["nonce"], skill_ids=[c.state["skill"]["id"]], material_ids=[c.state["material"]["id"]])
    c.state["agent"] = agent
    assert c.sql("SELECT skill_id FROM tutor_agent_skills WHERE agent_id=%s", (agent["id"],)) == [(c.state["skill"]["id"],)]
    assert c.sql("SELECT material_id FROM tutor_agent_materials WHERE agent_id=%s", (agent["id"],)) == [(c.state["material"]["id"],)]
    before = c.sql("SELECT count(*) FROM tutor_agents")[0][0]
    assert c.http("POST", c.base_class + "/agents", json={"name": agent["name"]}, operation="agents_create").status_code == 400
    for role in ("student", "admin"):
        assert c.http("POST", c.base_class + "/agents", auth=role, json={"name": "denied"}, operation="agents_create").status_code == 403
    assert c.sql("SELECT count(*) FROM tutor_agents")[0][0] == before


def agents_list(c):
    items = c.http("GET", c.base_class + "/agents", auth="student", operation="agents_list").json()["items"]
    assert c.state["agent"]["id"] in [item["id"] for item in items]
    assert all(item["enabled"] and item["class_id"] == 1 for item in items)


def agents_get(c):
    agent = c.state["agent"]
    assert c.http("GET", c.base_class + f"/agents/{agent['id']}", operation="agents_get").json()["agent"]["skill_ids"] == agent["skill_ids"]
    other = c.http("GET", "/api/classes/2/agents", auth="foreign", operation="agents_list").json()["items"][0]
    foreign = c.http("GET", c.base_class + f"/agents/{other['id']}", operation="agents_get")
    missing = c.http("GET", c.base_class + "/agents/2147483647", operation="agents_get")
    assert foreign.status_code == missing.status_code == 404 and foreign.content == missing.content


def agents_update(c):
    agent = c.state["agent"]
    path = c.base_class + f"/agents/{agent['id']}"
    before = c.sql("SELECT name, prompt FROM tutor_agents WHERE id=%s", (agent["id"],))
    assert c.http("PUT", path, json={"name": "must not persist", "skill_ids": [c.state["skill"]["id"], c.state["foreign_skill"]]}, operation="agents_update").status_code == 404
    assert c.sql("SELECT name, prompt FROM tutor_agents WHERE id=%s", (agent["id"],)) == before
    assert c.sql("SELECT skill_id FROM tutor_agent_skills WHERE agent_id=%s", (agent["id"],)) == [(c.state["skill"]["id"],)]
    assert c.http("PUT", path, json={"prompt": ""}, operation="agents_update").status_code == 200
    assert c.sql("SELECT material_id FROM tutor_agent_materials WHERE agent_id=%s", (agent["id"],)) == [(c.state["material"]["id"],)]
    response = c.http("PUT", path, json={"skill_ids": []}, operation="agents_update")
    assert response.json()["agent"]["skill_ids"] == [] and c.sql("SELECT count(*) FROM tutor_agent_skills WHERE agent_id=%s", (agent["id"],))[0][0] == 0
    assert c.http("PUT", path, json={"skill_ids": [c.state["skill"]["id"]]}, operation="agents_update").status_code == 200


def conversations_create(c):
    conv = c.create_conversation()
    c.state["conversation"] = conv
    assert c.sql("SELECT user_id,class_id,agent_id FROM conversations WHERE id=%s", (conv["id"],)) == [(c.users["student"]["id"], 1, c.state["agent"]["id"])]
    before = c.sql("SELECT count(*) FROM conversations")[0][0]
    assert c.http("POST", "/api/conversations", auth="student", json={}, operation="conversations_create").status_code == 400
    assert c.http("POST", "/api/conversations", auth=None, json={"agent_id": c.state["agent"]["id"]}, operation="conversations_create").status_code == 401
    c.http("PUT", c.base_class + f"/agents/{c.state['agent']['id']}", json={"enabled": False}, operation="agents_update")
    disabled = c.http("POST", "/api/conversations", auth="student", json={"agent_id": c.state["agent"]["id"]}, operation="conversations_create")
    missing = c.http("POST", "/api/conversations", auth="student", json={"agent_id": 2147483647}, operation="conversations_create")
    assert disabled.status_code == missing.status_code == 404 and disabled.content == missing.content
    assert c.sql("SELECT count(*) FROM conversations")[0][0] == before
    # The existing conversation remains readable while agent selection is disabled.
    assert c.http("GET", f"/api/conversations/{conv['id']}", auth="student", operation="conversations_get").status_code == 200


def conversations_list(c):
    items = c.http("GET", "/api/conversations", auth="student", operation="conversations_list").json()["items"]
    assert c.state["conversation"]["id"] in [item["id"] for item in items]
    assert all(item["user_id"] == c.users["student"]["id"] and item["class_id"] == 1 for item in items)


def conversations_get(c):
    ident = c.state["conversation"]["id"]
    assert c.http("GET", f"/api/conversations/{ident}", auth="student", operation="conversations_get").status_code == 200
    responses = [c.http("GET", f"/api/conversations/{ident}", auth=role, operation="conversations_get") for role in ("classmate", "foreign")]
    responses.append(c.http("GET", "/api/conversations/2147483647", auth="student", operation="conversations_get"))
    assert all(response.status_code == 404 for response in responses) and len({response.content for response in responses}) == 1


def messages_create(c):
    ident = c.state["conversation"]["id"]
    responses = [c.http("POST", f"/api/conversations/{ident}/messages", auth=role, json={"question": "数学去括号"}) for role in ("classmate", "foreign")]
    responses.append(c.http("POST", "/api/conversations/2147483647/messages", auth="student", json={"question": "数学去括号"}))
    assert all(response.status_code == 404 for response in responses) and len({response.content for response in responses}) == 1
    before = c.sql("SELECT count(*) FROM messages WHERE conversation_id=%s", (ident,))[0][0]
    assert c.http("POST", f"/api/conversations/{ident}/messages", auth="student", json={"question": "x"}).status_code == 400
    assert c.sql("SELECT count(*) FROM messages WHERE conversation_id=%s", (ident,))[0][0] == before
    seen = []
    def inspect(name, value):
        if name == "delta" and not seen:
            seen.append(True)
            assert c.http("GET", "/health", auth=None).status_code == 200
            blocked = c.http("POST", f"/api/conversations/{ident}/messages", auth="student", json={"question": "并发不得重复保存"})
            assert blocked.status_code == 409
            assert c.sql("SELECT count(*) FROM messages WHERE conversation_id=%s AND role='user'", (ident,))[0][0] == 1
            assert c.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted")[0][0] >= 1
    frames = c.stream(ident, "数学去括号", on_event=inspect)
    assert frames[-1][0] == "done" and frames[0][1]["skill"]["id"] == c.state["skill"]["id"]
    assert frames[0][1]["citations"] and all(hit["material_id"] == c.state["material"]["id"] for hit in frames[0][1]["citations"])
    text = "".join(value["text"] for name, value, _ in frames if name == "delta")
    assert "[999]" not in text and "[1]" in text and "hidden fixture" not in text
    row = c.sql("SELECT content,citations_json,skill_name,completion_state FROM messages WHERE id=%s", (frames[-1][1]["message_id"],))[0]
    assert row == (text, frames[0][1]["citations"], c.state["skill"]["name"], "complete")
    first_delta = next(t for name, _, t in frames if name == "delta")
    assert first_delta < 1 and frames[-1][2] - first_delta >= .9, "web proxy buffered the stream"
    assert c.sql("SELECT title FROM conversations WHERE id=%s", (ident,))[0][0] == "数学去括号"
    assert c.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted")[0][0] == 0
    # Same account, different conversations run concurrently across HTTP workers.
    c.http("PUT", c.base_class + f"/agents/{c.state['agent']['id']}", json={"enabled": True}, operation="agents_update")
    other = c.create_conversation()["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda conv: c.stream(conv, "数学去括号"), [ident, other]))
    assert all(result[-1][0] == "done" for result in results)
    # Cancel the web response after a delta and observe PostgreSQL lock cleanup.
    cancelled = c.create_conversation()["id"]
    response = c.http("POST", f"/api/conversations/{cancelled}/messages", auth="student", json={"question": "数学慢流验收"}, stream=True)
    received = []
    delta_started = False
    try:
        for line in response.iter_lines(chunk_size=1):
            received.append(line.decode("utf-8"))
            if line == b"event: delta":
                delta_started = True
            if delta_started and not line:
                break
    finally:
        response.close()
    deadline = time.monotonic() + 7
    while time.monotonic() < deadline and c.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted")[0][0]:
        time.sleep(.1)
    assert c.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted")[0][0] == 0
    states = c.sql("SELECT completion_state FROM messages WHERE conversation_id=%s AND role='assistant'", (cancelled,))
    assert states == [("interrupted",)], f"cancelled response saved unexpected states: {states}"
    c.records.append({"cancelled_conversation": cancelled, "received_frames": received, "saved_state": "interrupted", "advisory_locks_after": 0})
    # Empty material binding still calls chat and removes every numeric marker.
    empty = c.create_agent(material_ids=[], skill_ids=[])
    empty_conv = c.create_conversation(empty["id"])["id"]
    frames = c.stream(empty_conv, "数学去括号")
    assert frames[0][1]["citations"] == [] and frames[0][1]["skill"] is None
    assert "[1]" not in "".join(v["text"] for n, v, _ in frames if n == "delta") and frames[-1][0] == "done"
    # No retrieval hit remains a genuine chat request with no citation numbers.
    frames = c.stream(ident, "zzzzzzzzzzzzzzzz")
    assert frames[0][1]["citations"] == [] and frames[-1][0] == "done"
    for question, has_partial in [("数学部分失败验收", True), ("数学零正文失败验收", False), ("数学EOF失败验收", True)]:
        before = c.sql("SELECT count(*) FROM messages WHERE conversation_id=%s AND role='assistant'", (ident,))[0][0]
        frames = c.stream(ident, question)
        assert frames[-1][0] == "error" and "done" not in [name for name, _, _ in frames]
        rows = c.sql("SELECT completion_state FROM messages WHERE conversation_id=%s AND role='assistant' ORDER BY id DESC", (ident,))
        assert len(rows) == before + int(has_partial)
        if has_partial:
            assert rows[0][0] == "interrupted"
    response = c.http("POST", f"/api/conversations/{ident}/messages", auth="student", json={"question": "首帧失败验收"})
    assert response.status_code == 503
    assert c.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted")[0][0] == 0
    frames = c.stream(ident, "数学去括号继续")
    assert frames[-1][0] == "done"


def skills_delete(c):
    ident = c.state["skill"]["id"]
    assert c.sql("SELECT count(*) FROM tutor_agent_skills WHERE skill_id=%s", (ident,))[0][0] > 0
    assert c.http("DELETE", c.base_class + f"/skills/{ident}", auth="student", operation="skills_delete").status_code == 403
    assert c.http("DELETE", c.base_class + f"/skills/{ident}", operation="skills_delete").status_code == 204
    assert c.sql("SELECT count(*) FROM skills WHERE id=%s", (ident,))[0][0] == 0
    assert c.sql("SELECT count(*) FROM tutor_agent_skills WHERE skill_id=%s", (ident,))[0][0] == 0


def materials_delete(c):
    material = c.state["material"]["id"]
    snapshots = c.sql("SELECT id,citations_json FROM messages WHERE conversation_id=%s AND role='assistant'", (c.state["conversation"]["id"],))
    assert c.http("POST", c.base_class + f"/materials/{material}/reindex", json={"chunking": {"strategy": "auto"}}, operation="materials_reindex").status_code == 200
    citation = next(hit for _, citations in snapshots for hit in citations)
    retired = c.http("GET", c.base_class + f"/knowledge/chunks/{citation['chunk_id']}?source_hash={citation['source_hash']}", operation="knowledge_evidence")
    assert retired.status_code == 200 and retired.json()["evidence"]["generation_id"] == citation["generation_id"]
    assert c.http("DELETE", c.base_class + f"/materials/{material}", operation="materials_delete").status_code == 204
    assert c.sql("SELECT count(*) FROM tutor_agent_materials WHERE material_id=%s", (material,))[0][0] == 0
    for table in ("materials", "knowledge_entries", "knowledge_chunks"):
        column = "id" if table == "materials" else "material_id"
        assert c.sql(f"SELECT count(*) FROM {table} WHERE {column}=%s", (material,))[0][0] == 0
    assert c.sql("SELECT id,citations_json FROM messages WHERE conversation_id=%s AND role='assistant'", (c.state["conversation"]["id"],)) == snapshots
    data = c.http("GET", f"/api/conversations/{c.state['conversation']['id']}", auth="student", operation="conversations_get").json()
    assert all(hit.get("unavailable") for item in data["messages"] for hit in item["citations"])


def auth_refresh(c):
    old = c.refresh["student"]
    response = c.http("POST", "/api/auth/token/refresh", auth=None, headers={"Authorization": "Bearer " + old}, operation="auth_refresh")
    assert response.status_code == 200 and response.json()["refresh_token"] != old
    data = response.json()
    c.tokens["student"], c.refresh["student"] = data["access_token"], data["refresh_token"]
    assert c.sql("SELECT count(*) FROM auth_tokens t JOIN sessions s ON s.id=t.session_id WHERE s.user_id=%s AND t.token_type='refresh' AND t.revoked_at IS NOT NULL", (c.users["student"]["id"],))[0][0] >= 1


def auth_logout(c):
    assert c.http("POST", "/api/auth/logout", auth="student", operation="auth_logout").status_code == 204
    assert c.http("GET", "/api/auth/me", auth="student", operation="auth_me").status_code == 401
    assert c.sql("SELECT count(*) FROM sessions WHERE user_id=%s AND revoked_at IS NULL", (c.users["student"]["id"],))[0][0] == 0
