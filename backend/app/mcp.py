"""Teacher-only class MCP registry, discovery cache and bounded audit reader."""
from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError
from .api_docs import api_doc, obj, array, ref, STRING, INTEGER, BOOLEAN, SCHEMAS
from .auth import require_auth, json_error
from .authorization import subject_scope, is_teacher_member
from .extensions import db
from .models import MCPServer, MCPTool, MCPToolCall, SkillMCPBinding, utc_now
from .mcp_policy import MCPError, SERVER_NAME, require_origin, encrypt_token, decrypt_token, permitted
from .mcp_client import discover

mcp_bp = Blueprint("mcp", __name__)
NOT_FOUND = "resource not found"
SERVER_INPUT = obj({"name": {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,63}$"}, "base_url": STRING, "token": {"type": "string", "writeOnly": True, "maxLength": 2048}}, ["name", "base_url", "token"])
SCHEMAS.update({
    "MCPServer": obj({"id": INTEGER, "class_id": INTEGER, "name": STRING, "base_url": STRING, "has_token": BOOLEAN, "connected": BOOLEAN, "operation_revision": INTEGER, "configuration_revision": INTEGER, "last_error_code": {**STRING, "nullable": True}, "connected_at": {**STRING, "nullable": True}, "updated_at": STRING}),
    "MCPTool": obj({"name": STRING, "ref": STRING, "description": STRING, "inputSchema": {"type": "object"}, "declaration_hash": STRING, "permitted": BOOLEAN}),
    "MCPCall": obj({"id": INTEGER, "call_id": STRING, "ref": STRING, "round": INTEGER, "sequence": INTEGER, "status": {"type": "string", "enum": ["ok", "error", "denied"]}, "reason_code": {**STRING, "nullable": True}, "text": STRING, "duration_ms": INTEGER, "server_id": {**INTEGER, "nullable": True}, "server_name": STRING, "user_id": INTEGER, "conversation_id": INTEGER, "user_message_id": INTEGER, "created_at": STRING}),
})

def teacher_scope():
    scope = subject_scope(g.current_user)
    if not scope or not is_teacher_member(g.current_user, scope.class_id):
        return None, json_error(403, "teacher role required")
    return scope, None

def server_payload(server):
    return {"id": server.id, "class_id": server.class_id, "name": server.name, "base_url": server.base_url, "has_token": bool(server.token_ciphertext), "connected": server.connected, "operation_revision": server.operation_revision, "configuration_revision": server.configuration_revision, "last_error_code": server.last_error_code, "connected_at": server.connected_at.isoformat() if server.connected_at else None, "updated_at": server.updated_at.isoformat()}

def find_server(scope, identifier):
    return MCPServer.query.filter_by(id=identifier, class_id=scope.class_id).one_or_none()

def invalidate(server, *, configuration=False):
    # SQL increment is essential: concurrent requests may have stale ORM values.
    values = {MCPServer.connected: False, MCPServer.connected_at: None, MCPServer.operation_revision: MCPServer.operation_revision + 1, MCPServer.updated_at: utc_now(), MCPServer.updated_by: g.current_user.id, MCPServer.last_error_code: None}
    if configuration:
        values[MCPServer.configuration_revision] = MCPServer.configuration_revision + 1
    MCPServer.query.filter_by(id=server.id).update(values, synchronize_session=False)
    MCPTool.query.filter_by(server_id=server.id).delete(synchronize_session=False)
    db.session.flush()
    db.session.refresh(server)

@mcp_bp.get("/api/classes/<int:class_id>/mcp/servers")
@api_doc("mcp_servers_list", "教师列出本班MCP服务器", role="teacher", response=obj({"items": array(ref("MCPServer"))}))
@require_auth
def list_servers(class_id):
    scope, denied = teacher_scope()
    if denied: return denied
    return jsonify(items=[server_payload(s) for s in MCPServer.query.filter_by(class_id=scope.class_id).order_by(MCPServer.id)])

def write_server(server=None):
    scope, denied = teacher_scope()
    if denied: return denied
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - {"name", "base_url", "token"}:
            raise MCPError("invalid_request")
        name = body.get("name", server.name if server else None)
        if not isinstance(name, str) or not SERVER_NAME.fullmatch(name): raise MCPError("invalid_name")
        origin = require_origin(body.get("base_url", server.base_url if server else None))
        token = body.get("token")
        if token is not None and not isinstance(token, str): raise MCPError("invalid_token")
        if server is None:
            server = MCPServer(class_id=scope.class_id, name=name, base_url=origin, token_ciphertext=encrypt_token(token), created_by=g.current_user.id, updated_by=g.current_user.id)
            db.session.add(server)
        else:
            changed = name != server.name or origin != server.base_url or bool(token)
            if changed: invalidate(server, configuration=True)
            server.name, server.base_url = name, origin
            if token: server.token_ciphertext = encrypt_token(token)
            server.updated_at, server.updated_by = utc_now(), g.current_user.id
        db.session.commit()
        return jsonify(server=server_payload(server))
    except (MCPError, IntegrityError) as error:
        db.session.rollback()
        return json_error(400, "duplicate_server_name" if isinstance(error, IntegrityError) else error.code)

@mcp_bp.post("/api/classes/<int:class_id>/mcp/servers")
@api_doc("mcp_servers_create", "教师登记MCP服务器", role="teacher", body=SERVER_INPUT, status=201, response=obj({"server": ref("MCPServer")}), errors={400: "Invalid config or duplicate name"})
@require_auth
def create_server(class_id):
    response = write_server()
    if response.status_code == 200: response.status_code = 201
    return response

@mcp_bp.get("/api/classes/<int:class_id>/mcp/servers/<int:server_id>")
@api_doc("mcp_servers_get", "教师读取本班MCP服务器", role="teacher", response=obj({"server": ref("MCPServer")}), errors={404: NOT_FOUND})
@require_auth
def get_server(class_id, server_id):
    scope, denied = teacher_scope()
    if denied: return denied
    server = find_server(scope, server_id)
    return jsonify(server=server_payload(server)) if server else json_error(404, NOT_FOUND)

@mcp_bp.put("/api/classes/<int:class_id>/mcp/servers/<int:server_id>")
@api_doc("mcp_servers_update", "教师修改MCP服务器，空token保留", role="teacher", body=obj(SERVER_INPUT["properties"], []), response=obj({"server": ref("MCPServer")}), errors={400: "Invalid config or duplicate name", 404: NOT_FOUND})
@require_auth
def update_server(class_id, server_id):
    scope, denied = teacher_scope()
    if denied: return denied
    server = find_server(scope, server_id)
    return write_server(server) if server else json_error(404, NOT_FOUND)

@mcp_bp.delete("/api/classes/<int:class_id>/mcp/servers/<int:server_id>")
@api_doc("mcp_servers_delete", "教师删除服务器，保留确认和审计快照", role="teacher", status=204, errors={404: NOT_FOUND})
@require_auth
def delete_server(class_id, server_id):
    scope, denied = teacher_scope()
    if denied: return denied
    server = find_server(scope, server_id)
    if not server: return json_error(404, NOT_FOUND)
    invalidate(server)
    SkillMCPBinding.query.filter_by(server_id=server.id).update({"server_id": None}, synchronize_session=False)
    MCPToolCall.query.filter_by(server_id=server.id).update({"server_id": None}, synchronize_session=False)
    db.session.delete(server)
    db.session.commit()
    return "", 204

@mcp_bp.post("/api/classes/<int:class_id>/mcp/servers/<int:server_id>/connect")
@api_doc("mcp_servers_connect", "教师连接并完整发现工具", role="teacher", response=obj({"server": ref("MCPServer")}), errors={400: "MCP disabled or stale connect", 404: NOT_FOUND, 502: "Remote discovery failed"})
@require_auth
def connect_server(class_id, server_id):
    scope, denied = teacher_scope()
    if denied: return denied
    server = find_server(scope, server_id)
    if not server: return json_error(404, NOT_FOUND)
    invalidate(server)
    revision, origin, ciphertext = server.operation_revision, server.base_url, server.token_ciphertext
    db.session.commit()  # No transaction held across network IO.
    try:
        tools = discover(origin, decrypt_token(ciphertext))
        changed = MCPServer.query.filter_by(id=server_id, class_id=scope.class_id, operation_revision=revision).update({"connected": True, "connected_at": utc_now(), "last_error_code": None}, synchronize_session=False)
        if not changed:
            db.session.rollback()
            return json_error(400, "connection_superseded")
        MCPTool.query.filter_by(server_id=server_id).delete(synchronize_session=False)
        db.session.add_all(MCPTool(server_id=server_id, **tool) for tool in tools)
        db.session.commit()
        db.session.expire_all()
        return jsonify(server=server_payload(find_server(scope, server_id)))
    except MCPError as error:
        db.session.rollback()
        MCPServer.query.filter_by(id=server_id, class_id=scope.class_id, operation_revision=revision).update({"last_error_code": error.code}, synchronize_session=False)
        db.session.commit()
        return json_error(error.status, error.code)

@mcp_bp.post("/api/classes/<int:class_id>/mcp/servers/<int:server_id>/disconnect")
@api_doc("mcp_servers_disconnect", "教师断开并清空活动工具缓存", role="teacher", response=obj({"server": ref("MCPServer")}), errors={404: NOT_FOUND})
@require_auth
def disconnect_server(class_id, server_id):
    scope, denied = teacher_scope()
    if denied: return denied
    server = find_server(scope, server_id)
    if not server: return json_error(404, NOT_FOUND)
    invalidate(server)
    db.session.commit()
    return jsonify(server=server_payload(server))

@mcp_bp.get("/api/classes/<int:class_id>/mcp/servers/<int:server_id>/tools")
@api_doc("mcp_servers_tools", "教师读取完整缓存声明与本地许可", role="teacher", response=obj({"items": array(ref("MCPTool"))}), errors={404: NOT_FOUND})
@require_auth
def list_tools(class_id, server_id):
    scope, denied = teacher_scope()
    if denied: return denied
    server = find_server(scope, server_id)
    if not server: return json_error(404, NOT_FOUND)
    tools = MCPTool.query.filter_by(server_id=server_id).order_by(MCPTool.name).all() if server.connected else []
    return jsonify(items=[{"name": t.name, "ref": f"{t.name}@{server.name}", "description": t.description, "inputSchema": t.input_schema, "declaration_hash": t.declaration_hash, "permitted": bool(permitted(server.base_url, t.name))} for t in tools])

def call_payload(call):
    pending = call.status == "pending"
    return {"id": call.id, "call_id": call.call_id, "ref": call.tool_ref, "round": call.round, "sequence": call.sequence, "status": "error" if pending else call.status, "reason_code": "outcome_unknown" if pending else call.reason_code, "text": "调用结果未知，未自动重试" if pending else call.summary, "duration_ms": call.duration_ms, "server_id": call.server_id, "server_name": call.server_name, "user_id": call.user_id, "conversation_id": call.conversation_id, "user_message_id": call.user_message_id, "created_at": call.created_at.isoformat()}

@mcp_bp.get("/api/classes/<int:class_id>/mcp/tool-calls")
@api_doc("mcp_tool_calls_list", "教师按倒序游标读取本班工具审计", role="teacher", response=obj({"items": array(ref("MCPCall")), "next_cursor": {**INTEGER, "nullable": True}}), errors={400: "Invalid cursor or limit", 404: NOT_FOUND}, parameters=[{"name": name, "in": "query", "schema": INTEGER} for name in ("cursor", "limit", "server_id")])
@require_auth
def list_calls(class_id):
    scope, denied = teacher_scope()
    if denied: return denied
    try:
        limit = int(request.args.get("limit", 50))
        cursor = int(request.args["cursor"]) if "cursor" in request.args else None
        server_id = int(request.args["server_id"]) if "server_id" in request.args else None
        if not 1 <= limit <= 100 or (cursor is not None and not 1 <= cursor <= 2147483647) or (server_id is not None and not 1 <= server_id <= 2147483647): raise ValueError()
    except ValueError:
        return json_error(400, "invalid_pagination")
    if server_id is not None and not find_server(scope, server_id): return json_error(404, NOT_FOUND)
    query = MCPToolCall.query.filter_by(class_id=scope.class_id)
    if server_id is not None: query = query.filter_by(server_id=server_id)
    if cursor is not None: query = query.filter(MCPToolCall.id < cursor)
    rows = query.order_by(MCPToolCall.id.desc()).limit(limit + 1).all()
    return jsonify(items=[call_payload(c) for c in rows[:limit]], next_cursor=rows[limit - 1].id if len(rows) > limit else None)
