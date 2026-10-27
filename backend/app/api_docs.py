"""Handler-owned OpenAPI metadata. No separate handwritten path registry."""
from copy import deepcopy
import re

from flask import Blueprint, current_app, jsonify

docs_bp = Blueprint("api_docs", __name__)
STRING = {"type": "string"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}


def obj(properties, required=None):
    return {"type": "object", "properties": properties, "required": list(properties) if required is None else list(required)}


def array(items):
    return {"type": "array", "items": items}


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


USER = obj({"id": INTEGER, "username": STRING, "role": {"type": "string", "enum": ["super_admin", "class_admin", "teacher", "student"]}, "class_id": INTEGER})
TOKEN_PAIR = obj({"user": USER, "token_type": {"type": "string", "enum": ["Bearer"]}, "access_token": STRING,
                  "refresh_token": STRING, "expires_in": INTEGER, "refresh_expires_in": INTEGER})
SCHEMAS = {
    "Error": obj({"error": STRING, "code": STRING}, ["error"]),
    "User": USER, "TokenPair": TOKEN_PAIR,
    "Material": obj({"id": {"type": "string", "format": "uuid"}, "title": STRING, "subject_id": INTEGER, "subject_name": STRING,
                     "original_filename": STRING, "created_at": {"type": "string", "format": "date-time"}, "index_status": STRING,
                     "source_saved": BOOLEAN, "searchable_status": STRING, "latest_attempt_status": STRING,
                     "latest_attempt_error_code": {"type": "string", "nullable": True}, "index_compatibility": STRING,
                     "generation_id": {"type": "integer", "nullable": True}, "latest_generation_id": {"type": "integer", "nullable": True},
                     "chunking": {"type": "object"}}),
    "Evidence": obj({"subject_id": INTEGER, "subject_name": STRING, "material_id": STRING, "material_title": STRING,
                     "chunk_id": INTEGER, "chunk_index": INTEGER, "generation_id": INTEGER, "source_hash": STRING,
                     "excerpt": STRING, "source_spans": array(obj({"start": INTEGER, "end": INTEGER})),
                     "start_offset": INTEGER, "end_offset": INTEGER, "offset_basis": STRING,
                     "excerpt_start_offset": INTEGER, "excerpt_end_offset": INTEGER, "excerpt_truncated": BOOLEAN,
                     "offset_unit": STRING, "provenance_version": STRING, "evidence_key": {"type": "array", "items": {}},
                     "score": {"type": "number"}}, ["material_id", "material_title", "chunk_id", "chunk_index", "generation_id", "excerpt"]),
    "Chunking": obj({"strategy": {"type": "string", "enum": ["auto", "custom", "hierarchy"]}, "max_length": {"type": "integer", "minimum": 100, "maximum": 2000},
                     "overlap_percent": {"type": "number", "minimum": 0, "maximum": 50}, "separators": array(STRING),
                     "remove_urls": BOOLEAN, "remove_emails": BOOLEAN, "collapse_whitespace": BOOLEAN}, []),
}
SCHEMAS["CitationSnapshot"] = obj({**SCHEMAS["Evidence"]["properties"], "index": INTEGER, "unavailable": BOOLEAN,
    "source_segments": array(obj({"start": {"type": "integer", "nullable": True}, "end": {"type": "integer", "nullable": True}, "text": STRING}))},
    ["material_id", "material_title", "chunk_id", "chunk_index", "generation_id"])
for name in ("source_hash", "excerpt_start_offset", "excerpt_end_offset"):
    SCHEMAS["Evidence"]["properties"][name] = {**SCHEMAS["Evidence"]["properties"][name], "nullable": True}


def api_doc(operation_id, summary, *, body=None, response=None, status=200, public=False, role=None,
            errors=None, parameters=None, multipart=None, streaming=False, description="", response_media="application/json"):
    def decorate(function):
        function.api_documentation = dict(operation_id=operation_id, summary=summary, body=body, response=response,
                                          status=status, public=public, role=role, errors=errors or {},
                                          parameters=parameters or [], multipart=multipart, streaming=streaming,
                                          description=description, response_media=response_media)
        return function
    return decorate


def _check_schema(schema):
    if not isinstance(schema, dict):
        raise ValueError("API schema must be an object")
    if "$ref" in schema:
        if schema["$ref"].split("/")[-1] not in SCHEMAS:
            raise ValueError("unknown API schema reference")
        return
    if schema.get("type") not in {None, "object", "array", "string", "integer", "number", "boolean"}:
        raise ValueError("invalid API schema type")
    properties = schema.get("properties", {})
    if any(key not in properties for key in schema.get("required", [])):
        raise ValueError("required schema property is missing")
    for child in properties.values():
        _check_schema(child)
    if schema.get("type") == "array":
        if "items" not in schema:
            raise ValueError("array schema needs items")
        _check_schema(schema["items"])


def generate_document(app, required_operations=()):
    paths, identifiers = {}, set()
    for name, schema in SCHEMAS.items():
        _check_schema(schema)
    for rule in app.url_map.iter_rules():
        annotation = getattr(app.view_functions[rule.endpoint], "api_documentation", None)
        if annotation is None:
            continue
        methods = rule.methods - {"HEAD", "OPTIONS"}
        if len(methods) != 1:
            raise ValueError(f"documented handler needs one method: {rule}")
        ident = annotation["operation_id"]
        if ident in identifiers:
            raise ValueError(f"duplicate operationId: {ident}")
        identifiers.add(ident)
        parameters = deepcopy(annotation["parameters"])
        for argument in sorted(rule.arguments):
            converter = rule._converters[argument].__class__.__name__
            schema = INTEGER if converter == "IntegerConverter" else STRING
            parameters.append({"name": argument, "in": "path", "required": True, "schema": schema})
        responses = {str(annotation["status"]): {"description": "Success"}}
        if annotation["status"] != 204:
            schema = annotation["response"] or {"type": "object"}
            _check_schema(schema)
            media = "text/event-stream" if annotation["streaming"] else annotation["response_media"]
            responses[str(annotation["status"])]["content"] = {media: {"schema": schema}}
        errors = {**({} if annotation["public"] else {401: "Missing, expired or revoked Bearer access token", 403: "Role or subject access denied"}), **annotation["errors"]}
        for code, explanation in errors.items():
            responses[str(code)] = {"description": explanation, "content": {"application/json": {"schema": ref("Error")}}}
        operation = {"operationId": ident, "summary": annotation["summary"], "description": annotation["description"],
                     "parameters": parameters, "responses": responses,
                     "security": [] if annotation["public"] else [{"BearerAuth": []}]}
        if annotation["role"]:
            operation["x-role"] = annotation["role"]
        content = {}
        for media, schema in [("application/json", annotation["body"]), ("multipart/form-data", annotation["multipart"])]:
            if schema is not None:
                _check_schema(schema)
                content[media] = {"schema": schema}
        if content:
            operation["requestBody"] = {"required": True, "content": content}
        if annotation["streaming"]:
            operation["x-sse-events"] = {
                "meta": obj({"status": {"type": "string", "enum": ["ok"]}, "skill": {**obj({"id": INTEGER, "name": STRING}), "nullable": True}, "citations": array(ref("CitationSnapshot")), "demo_mode": BOOLEAN, "tool_calls": array(obj({"call_id": STRING, "ref": STRING, "round": INTEGER, "status": {"type": "string", "enum": ["ok", "error", "denied"]}, "reason_code": {**STRING, "nullable": True}, "text": STRING})), "tool_warning": STRING}, ["status", "skill", "citations", "demo_mode"]),
                "delta": obj({"text": STRING}), "done": obj({"message_id": INTEGER}), "error": obj({"error": STRING}),
            }
            operation["x-sse-meta-updates"] = "MCP: initial meta then cumulative tool_calls meta updates before delta; merge by call_id. No MCP: one meta. Never replay POST."
        path = re.sub(r"<(?:(?:[^:>]+):)?([^>]+)>", r"{\1}", rule.rule)
        paths.setdefault(path, {})[next(iter(methods)).lower()] = operation
    missing = set(required_operations) - identifiers
    if missing:
        raise ValueError(f"missing API documentation: {sorted(missing)}")
    return {"openapi": "3.0.3", "info": {"title": "CampusClaw API", "version": "5.0.0",
             "description": "不透明 Bearer access/refresh tokens。身份和有效班级来自认证，学生不能调用教师写接口。会话SSE与原证据问答具有不同的无证据契约。"},
            "servers": [{"url": "/"}], "paths": paths,
            "components": {"securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer", "description": "Access token; refresh endpoint requires the refresh token instead."}}, "schemas": deepcopy(SCHEMAS)}}


@docs_bp.get("/openapi.json")
@api_doc("docs_openapi", "读取生成的OpenAPI文档", public=True)
def openapi():
    return jsonify(generate_document(current_app))


SWAGGER_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CampusClaw Swagger</title><link rel="stylesheet" href="/static/swagger/swagger-ui.css"></head><body><div id="swagger-ui"></div><script src="/static/swagger/swagger-ui-bundle.js"></script><script src="/static/swagger/init.js"></script></body></html>"""


@docs_bp.get("/swagger/")
@api_doc("docs_swagger", "打开Swagger UI", public=True, response=STRING, response_media="text/html")
def swagger():
    return SWAGGER_HTML


@docs_bp.get("/swagger/index.html")
@api_doc("docs_swagger_index", "打开Swagger UI兼容入口", public=True, response=STRING, response_media="text/html")
def swagger_index():
    return SWAGGER_HTML
