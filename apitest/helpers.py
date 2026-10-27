"""HTTP, streamed SSE, schema checks and genuinely read-only database assertions."""
import json
import os
import re
import time
import threading
from uuid import uuid4
from urllib.parse import urlsplit

import psycopg
import requests

ACCOUNTS = {"teacher": ("linzimo", "teacher-password"), "student": ("zhouchengxi", "student-a-password"),
            "classmate": ("tutor_classmate", "classmate-test-password"), "foreign": ("xiewanqing", "student-b-password"),
            "admin": ("zhangruoxi", "super-admin-password"), "foreign_teacher": ("songxinyue", "teacher-b-password")}


def redact(value, secrets=()):
    text = str(value)
    for secret in sorted(set(s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9_.\-]+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)(password|access_token|refresh_token|api_key|token_ciphertext|mcp_auth_token|mcp_token_encryption_key)([\"\s:=]+)[^\s,}\"<]+', r'\1\2[REDACTED]', text)
    text = re.sub(r'(?i)(postgres(?:ql)?(?:\+\w+)?://[^:]+:)[^@]+', r'\1[REDACTED]', text)
    return text


def schema_check(value, schema, document):
    if "$ref" in schema:
        return schema_check(value, document["components"]["schemas"][schema["$ref"].split("/")[-1]], document)
    if value is None and schema.get("nullable"):
        return
    expected = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int, "number": (float, int), "boolean": bool}
    if expected:
        assert isinstance(value, types[expected]) and (expected not in ("integer", "number") or type(value) is not bool), f"schema type: {expected}"
    if "enum" in schema:
        assert value in schema["enum"], "schema enum"
    if isinstance(value, dict):
        assert all(key in value for key in schema.get("required", [])), "required response field missing"
        for key, child in schema.get("properties", {}).items():
            if key in value:
                schema_check(value[key], child, document)
    if expected == "array":
        for item in value:
            schema_check(item, schema["items"], document)


class Context:
    def __init__(self):
        self.base = os.getenv("TUTOR_TEST_BASE_URL", "").rstrip("/")
        self.database = os.getenv("TUTOR_TEST_DATABASE_URL", "")
        self.info = os.getenv("TUTOR_TEST_INFO_URL", "")
        self.provider = os.getenv("TUTOR_TEST_PROVIDER_URL", "")
        self.mcp = os.getenv("MCP_DISPOSABLE_DATABASE") == "true"
        self.tokens, self.refresh, self.users, self.state, self.records = {}, {}, {}, {}, []
        self.secrets = [password for _, password in ACCOUNTS.values()]
        self.secrets.extend(["disposable-mcp-token", "ZGlzcG9zYWJsZS1tY3AtdGVzdC1rZXktMDAwMDAwMDA="])
        self.lock = threading.Lock()

    def preflight(self):
        parsed = urlsplit(self.base)
        web_port, web_host = (5284, "mcp-web") if self.mcp else (5176, "tutor-web")
        database, readonly, db_host, db_port = ("mcp_test", "mcp_readonly", "mcp-postgres", "5548") if self.mcp else ("tutor_test", "tutor_readonly", "tutor-postgres", "5546")
        allowed_base = parsed.scheme == "http" and not parsed.username and not parsed.password and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment and ((parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port == web_port) or (parsed.hostname == web_host and parsed.port == 5173))
        db_info = psycopg.conninfo.conninfo_to_dict(self.database)
        assert os.getenv("TUTOR_DISPOSABLE_DATABASE") == "true" and allowed_base, "runner requires the named disposable web environment"
        assert db_info.get("dbname") == database and db_info.get("user") == readonly, "runner requires the fixture database and read-only DB role"
        allowed_db = (db_info.get("host") == db_host and db_info.get("port", "5432") == "5432") or (db_info.get("host") in {"localhost", "127.0.0.1"} and db_info.get("port") == db_port)
        assert allowed_db, "development database targets are forbidden"
        self.secrets.append(db_info.get("password", ""))
        info = requests.get(self.info, timeout=10).json()
        expected = {"environment": "disposable-mcp-test", "database": "mcp_test", "fixture": "lesson-six-v1"} if self.mcp else {"environment": "disposable-tutor-test", "database": "tutor_test", "fixture": "lesson-five-v1"}
        assert info == expected, "fixture identity mismatch"
        assert self.sql("SELECT current_database(), current_user")[0] == (database, readonly)
        assert not self.sql("SELECT has_table_privilege(current_user, 'messages', 'INSERT')")[0][0]
        self.document = requests.get(self.base + "/openapi.json", timeout=10).json()

    def sql(self, query, parameters=()):
        assert query.lstrip().upper().startswith("SELECT"), "only SELECT assertions allowed"
        with psycopg.connect(self.database, autocommit=False) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            return connection.execute(query, parameters).fetchall()

    def login(self, role):
        username, password = ACCOUNTS[role]
        response = self.http("POST", "/api/auth/login", auth=None, json={"username": username, "password": password}, operation="auth_login")
        assert response.status_code == 200
        data = response.json()
        self.tokens[role], self.refresh[role], self.users[role] = data["access_token"], data["refresh_token"], data["user"]
        self.secrets.extend([data["access_token"], data["refresh_token"]])
        return data

    def http(self, method, path, auth="teacher", operation=None, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        if auth:
            headers["Authorization"] = "Bearer " + self.tokens[auth]
        response = requests.request(method, self.base + path, headers=headers, timeout=45 if kwargs.get("stream") else 15, **kwargs)
        record = {"method": method, "path": path, "status": response.status_code}
        if not kwargs.get("stream") and "json" in response.headers.get("Content-Type", ""):
            data = response.json()
            for key in ("access_token", "refresh_token"):
                if isinstance(data, dict) and key in data:
                    self.secrets.append(data[key])
            record["response"] = data
            if operation:
                definition = next(op for methods in self.document["paths"].values() for op in methods.values() if op["operationId"] == operation)
                schema = definition["responses"][str(response.status_code)]["content"]["application/json"]["schema"]
                schema_check(data, schema, self.document)
        with self.lock:
            self.records.append(record)
        return response

    @property
    def base_class(self):
        return f"/api/classes/{self.users['teacher']['class_id']}"

    def create_skill(self, suffix="", enabled=True):
        suffix = suffix or uuid4().hex[:8]
        source = f"名称：接口验收{suffix}\n适用条件：数学,去括号,分数\n资料：数学\n工具：knowledge_search\n启用：{'是' if enabled else '否'}\n\n通过提问提示下一步，不给最终答案。"
        response = self.http("POST", self.base_class + "/skills", json={"source_text": source}, operation="skills_create")
        assert response.status_code == 201
        return response.json()["skill"]

    def create_agent(self, suffix="", **fields):
        suffix = suffix or uuid4().hex[:8]
        body = {"name": "接口验收助手" + suffix, "prompt": "请耐心辅导", "skill_ids": [], "material_ids": [], **fields}
        response = self.http("POST", self.base_class + "/agents", json=body, operation="agents_create")
        assert response.status_code == 201
        return response.json()["agent"]

    def create_conversation(self, agent_id=None, auth="student"):
        if agent_id is None:
            agent_id = self.state["agent"]["id"]
        response = self.http("POST", "/api/conversations", auth=auth, json={"agent_id": agent_id}, operation="conversations_create")
        assert response.status_code == 201
        return response.json()["conversation"]

    def stream(self, ident, question, auth="student", on_event=None):
        began = time.monotonic()
        response = self.http("POST", f"/api/conversations/{ident}/messages", auth=auth, json={"question": question}, stream=True)
        assert response.status_code == 200 and response.headers["Content-Type"].startswith("text/event-stream")
        events, name, data = [], None, []
        try:
            for raw in response.iter_lines(chunk_size=1):
                line = raw.decode("utf-8")
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: "):
                    data.append(line[6:])
                elif not line and data:
                    value = json.loads("\n".join(data))
                    schema = self.document["paths"]["/api/conversations/{conversation_id}/messages"]["post"]["x-sse-events"][name]
                    schema_check(value, schema, self.document)
                    events.append((name, value, time.monotonic() - began))
                    if on_event:
                        on_event(name, value)
                    name, data = None, []
        finally:
            response.close()
            with self.lock:
                self.records.append({"stream": ident, "events": events})
        assert events and events[0][0] == "meta"
        return events
