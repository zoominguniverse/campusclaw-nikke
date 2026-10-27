"""Local trust policy. Remote declarations cannot grant permission."""
import json
import math
import re
from urllib.parse import urlsplit
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

SERVER_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
TOOL_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
TOOL_REF = re.compile(r"[a-z][a-z0-9_]{0,63}@[a-z][a-z0-9_-]{0,63}\Z")

class MCPError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code, self.status = code, status

def normalize_origin(value):
    try:
        if not isinstance(value, str) or len(value) > 512 or any(c.isspace() for c in value) or "\\" in value:
            raise ValueError()
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.path not in {"", "/"} or parts.query or parts.fragment:
            raise ValueError()
        host = parts.hostname.lower()
        host = f"[{host}]" if ":" in host else host
        port = parts.port
        suffix = f":{port}" if port and port != (443 if parts.scheme == "https" else 80) else ""
        return f"{parts.scheme}://{host}{suffix}"
    except (ValueError, TypeError):
        raise MCPError("invalid_origin") from None

def validate_mcp_config(config):
    try:
        policy = json.loads(config["MCP_TOOL_POLICY_JSON"])
        if not isinstance(policy, dict):
            raise ValueError()
        for origin, tools in policy.items():
            if normalize_origin(origin) != origin or not isinstance(tools, dict) or any(not TOOL_NAME.fullmatch(name) or permission != "read" for name, permission in tools.items()):
                raise ValueError()
        config["MCP_TOOL_POLICY"] = policy
        for key, upper in (("MCP_MAX_ROUNDS", 3), ("MCP_MAX_PROPOSALS", 16), ("MCP_MAX_ATTEMPTS_PER_TURN", 6), ("MCP_MAX_ATTEMPTS_PER_CONVERSATION", 30)):
            if type(config[key]) is not int or not 1 <= config[key] <= upper:
                raise ValueError()
        for key, upper in (("MCP_PHASE_TIMEOUT_SECONDS", 20), ("MCP_REQUEST_TIMEOUT_SECONDS", 5)):
            if not isinstance(config[key], (int, float)) or not math.isfinite(config[key]) or not 0 < config[key] <= upper:
                raise ValueError()
        key = config["MCP_TOKEN_ENCRYPTION_KEY"]
        if key:
            Fernet(key.encode("ascii"))
        if config["MCP_ENABLED"] and (not key or not policy):
            raise ValueError()
        if key in {config["SECRET_KEY"], config["AUTH_TOKEN_SECRET"]}:
            raise ValueError()
    except (ValueError, TypeError, UnicodeError, MCPError):
        raise RuntimeError("invalid MCP configuration: require a distinct Fernet key, exact read policy and bounded budgets") from None

def require_origin(value):
    if not current_app.config["MCP_ENABLED"]:
        raise MCPError("mcp_disabled")
    origin = normalize_origin(value)
    if origin not in current_app.config["MCP_TOOL_POLICY"]:
        raise MCPError("origin_not_allowed")
    return origin

def permitted(origin, tool):
    return current_app.config["MCP_ENABLED"] and current_app.config["MCP_TOOL_POLICY"].get(origin, {}).get(tool) == "read"

def encrypt_token(token):
    if not isinstance(token, str) or not 1 <= len(token) <= 2048 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise MCPError("invalid_token")
    try:
        return Fernet(current_app.config["MCP_TOKEN_ENCRYPTION_KEY"].encode()).encrypt(token.encode()).decode()
    except (ValueError, TypeError):
        raise MCPError("mcp_disabled") from None

def decrypt_token(ciphertext):
    try:
        return Fernet(current_app.config["MCP_TOKEN_ENCRYPTION_KEY"].encode()).decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        raise MCPError("credential_unavailable") from None

# Intentionally small JSON Schema subset. No refs, regex, extensions or resolver.
def validate_schema(schema, depth=0):
    allowed = {"type", "description", "properties", "required", "additionalProperties", "items", "enum", "minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems"}
    if depth > 8 or not isinstance(schema, dict) or set(schema) - allowed:
        raise MCPError("invalid_schema")
    kind = schema.get("type")
    if kind not in {"object", "array", "string", "integer", "number", "boolean", "null"}:
        raise MCPError("invalid_schema")
    if "description" in schema and (not isinstance(schema["description"], str) or len(schema["description"]) > 2000):
        raise MCPError("invalid_schema")
    for low, high in (("minLength", "maxLength"), ("minItems", "maxItems")):
        for name in (low, high):
            if name in schema and (type(schema[name]) is not int or not 0 <= schema[name] <= 16000):
                raise MCPError("invalid_schema")
        if schema.get(low, 0) > schema.get(high, 16000):
            raise MCPError("invalid_schema")
    for name in ("minimum", "maximum"):
        if name in schema and (type(schema[name]) not in (int, float) or not math.isfinite(schema[name])):
            raise MCPError("invalid_schema")
    if schema.get("minimum", -math.inf) > schema.get("maximum", math.inf):
        raise MCPError("invalid_schema")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not 1 <= len(schema["enum"]) <= 100 or any(isinstance(x, (dict, list)) for x in schema["enum"])):
        raise MCPError("invalid_schema")
    if kind == "object":
        properties, required = schema.get("properties", {}), schema.get("required", [])
        if not isinstance(properties, dict) or len(properties) > 32 or any(not isinstance(k, str) or not 1 <= len(k) <= 64 for k in properties) or not isinstance(required, list) or any(not isinstance(k, str) or k not in properties for k in required) or len(set(required)) != len(required) or type(schema.get("additionalProperties", False)) is not bool:
            raise MCPError("invalid_schema")
        for child in properties.values():
            validate_schema(child, depth + 1)
    elif kind == "array":
        validate_schema(schema.get("items"), depth + 1)
    elif set(schema) & {"properties", "required", "additionalProperties", "items"}:
        raise MCPError("invalid_schema")

def validate_arguments(value, schema, depth=0):
    if depth > 8:
        raise MCPError("invalid_arguments")
    kind = schema["type"]
    matches = {"object": type(value) is dict, "array": type(value) is list, "string": type(value) is str, "integer": type(value) is int, "number": type(value) in (int, float), "boolean": type(value) is bool, "null": value is None}
    if not matches[kind] or ("enum" in schema and value not in schema["enum"]):
        raise MCPError("invalid_arguments")
    if kind == "object":
        properties = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])) or (not schema.get("additionalProperties", False) and set(value) - set(properties)):
            raise MCPError("invalid_arguments")
        for key in set(value) & set(properties):
            validate_arguments(value[key], properties[key], depth + 1)
    elif kind == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 100):
            raise MCPError("invalid_arguments")
        for item in value:
            validate_arguments(item, schema["items"], depth + 1)
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value.strip()) <= schema.get("maxLength", 16000) or "\x00" in value:
            raise MCPError("invalid_arguments")
    elif kind in {"integer", "number"} and (not math.isfinite(value) or not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf)):
        raise MCPError("invalid_arguments")
