"""Bounded HTTP transport for the teaching MCP subset (no redirects/proxies)."""
import hashlib
import json
import time
from uuid import uuid4
import requests
from flask import current_app
from .mcp_policy import MCPError, TOOL_NAME, require_origin, validate_schema

PROTOCOL_VERSION = "2024-11-05"

def read_json(response, deadline, limit):
    content = bytearray()
    try:
        for part in response.iter_content(chunk_size=1):
            if time.monotonic() >= deadline:
                raise MCPError("remote_timeout", 502)
            content.extend(part)
            if len(content) > limit:
                raise MCPError("response_too_large", 502)
        return json.loads(content.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except MCPError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise MCPError("invalid_response", 502) from None

def rpc(base_url, token, method, params, deadline=None):
    origin = require_origin(base_url)
    deadline = min(deadline if deadline is not None else float("inf"), time.monotonic() + current_app.config["MCP_REQUEST_TIMEOUT_SECONDS"])
    remaining = min(current_app.config["MCP_REQUEST_TIMEOUT_SECONDS"], deadline - time.monotonic())
    if remaining <= 0:
        raise MCPError("remote_timeout", 502)
    identifier = uuid4().hex
    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.post(origin + "/mcp", json={"jsonrpc": "2.0", "id": identifier, "method": method, "params": params}, headers={"Authorization": "Bearer " + token}, timeout=remaining, stream=True, allow_redirects=False) as response:
                if response.status_code != 200:
                    raise MCPError("remote_unauthorized" if response.status_code == 401 else "remote_http_error", 502)
                body = read_json(response, deadline, 256 * 1024)
    except requests.RequestException as error:
        raise MCPError("remote_timeout" if isinstance(error, (requests.Timeout, requests.ConnectionError)) else "remote_unavailable", 502) from None
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0" or body.get("id") != identifier or ("result" in body) == ("error" in body) or "error" in body or not isinstance(body.get("result"), dict):
        raise MCPError("invalid_response", 502)
    return body["result"]

def discover(base_url, token):
    deadline = time.monotonic() + current_app.config["MCP_PHASE_TIMEOUT_SECONDS"]
    initialized = rpc(base_url, token, "initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "campusclaw", "version": "6.0"}}, deadline)
    if initialized.get("protocolVersion") != PROTOCOL_VERSION:
        raise MCPError("unsupported_protocol", 502)
    tools, names, cursors, cursor, total = [], set(), set(), None, 0
    while True:
        result = rpc(base_url, token, "tools/list", {"cursor": cursor} if cursor else {}, deadline)
        page = result.get("tools")
        if not isinstance(page, list):
            raise MCPError("invalid_declaration", 502)
        total += len(json.dumps(result, ensure_ascii=False).encode())
        if total > 256 * 1024 or len(tools) + len(page) > 32:
            raise MCPError("discovery_limit", 502)
        for tool in page:
            serialized = json.dumps(tool, ensure_ascii=False)
            credentials = [token, current_app.config.get("CHAT_API_KEY"), current_app.config.get("MCP_TOKEN_ENCRYPTION_KEY"), current_app.config.get("AUTH_TOKEN_SECRET"), current_app.config.get("SECRET_KEY")]
            if any(secret and secret in serialized for secret in credentials):
                raise MCPError("unsafe_declaration", 502)
            if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not TOOL_NAME.fullmatch(tool["name"]) or tool["name"] in names or not isinstance(tool.get("description"), str) or not 1 <= len(tool["description"]) <= 2000:
                raise MCPError("invalid_declaration", 502)
            schema = tool.get("inputSchema")
            if len(json.dumps(schema, ensure_ascii=False).encode()) > 16384:
                raise MCPError("invalid_schema", 502)
            try:
                validate_schema(schema)
            except MCPError:
                raise MCPError("invalid_schema", 502) from None
            if schema["type"] != "object":
                raise MCPError("invalid_schema", 502)
            declaration = {"name": tool["name"], "description": tool["description"], "inputSchema": schema}
            digest = hashlib.sha256(json.dumps(declaration, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            tools.append(dict(name=tool["name"], description=tool["description"], input_schema=schema, declaration_hash=digest))
            names.add(tool["name"])
        cursor = result.get("nextCursor")
        if cursor is None:
            return tools
        if not isinstance(cursor, str) or not cursor or len(cursor) > 256 or cursor in cursors or len(cursors) >= 32:
            raise MCPError("invalid_cursor", 502)
        cursors.add(cursor)
