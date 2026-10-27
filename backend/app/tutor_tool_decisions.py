"""Non-streaming decisions; only structured function calls can dispatch tools."""
import hashlib
import json
import re
import time
import requests
from flask import current_app
from .mcp_client import read_json
from .mcp_policy import MCPError

def declarations(candidates):
    tools, aliases = [], {}
    for tool_ref, server_id, tool in candidates:
        name = f"mcp_{server_id}_{tool.name}"
        if len(name) > 64:
            name = name[:47] + "_" + hashlib.sha256(name.encode()).hexdigest()[:16]
        if name in aliases:
            raise MCPError("alias_collision")
        aliases[name] = tool_ref
        tools.append({"type": "function", "function": {"name": name, "description": tool.description, "parameters": tool.input_schema}})
    return tools, aliases

def parse_decision(body):
    try:
        choices = body["choices"]
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError()
        choice = choices[0]
        message = choice["message"]
        if not isinstance(message, dict): raise ValueError()
        calls = message.get("tool_calls") or []
        if not isinstance(calls, list) or len(calls) > 8 or choice.get("finish_reason") not in ({"tool_calls", "stop"} if calls else {"stop"}):
            raise ValueError()
        parsed, seen = [], set()
        for call in calls:
            identifier, function = call["id"], call["function"]
            if call.get("type") != "function" or not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier) or identifier in seen or not isinstance(function["name"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", function["name"]):
                raise ValueError()
            raw = function["arguments"]
            if not isinstance(raw, str) or len(raw.encode()) > 16384: raise ValueError()
            arguments = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(arguments, dict): raise ValueError()
            seen.add(identifier)
            parsed.append({"id": identifier, "type": "function", "function": {"name": function["name"], "arguments": raw}, "arguments": arguments})
        return parsed
    except (ValueError, KeyError, TypeError, IndexError, RecursionError):
        raise MCPError("decision_protocol_error") from None

def decide(messages, tools, deadline):
    if not tools: return []
    if current_app.config["CHAT_PROVIDER"] != "openai-compatible":
        raise MCPError("decision_unavailable")
    remaining = min(current_app.config["CHAT_TIMEOUT_SECONDS"], deadline - time.monotonic())
    if remaining <= 0: raise MCPError("quota_exhausted")
    payload = {"model": current_app.config["CHAT_MODEL"], "messages": messages, "tools": tools, "tool_choice": "auto", "stream": False, "max_tokens": 2048}
    if "deepseek.com" in current_app.config["CHAT_API_URL"]:
        payload["reasoning_effort"] = "none"
    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.post(current_app.config["CHAT_API_URL"] + "/chat/completions", json=payload, headers={"Authorization": "Bearer " + current_app.config["CHAT_API_KEY"]}, stream=True, allow_redirects=False, timeout=remaining) as response:
                if response.status_code != 200: raise MCPError("decision_unavailable")
                body = read_json(response, deadline, 65536)
    except requests.RequestException:
        raise MCPError("decision_unavailable") from None
    return parse_decision(body)
