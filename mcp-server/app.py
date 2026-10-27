"""Small, deliberately bounded JSON-RPC MCP teaching service."""
import hmac
import os
from flask import Flask, jsonify, request

PROTOCOL_VERSION = "2024-11-05"
QUERY_SCHEMA = {"type": "object", "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 500}}, "required": ["query"], "additionalProperties": False}
TOOLS = [
    {"name": "formula_hint", "description": "给出去括号、移项或公式选择的下一步检查提示，不给出题目最终答案。", "inputSchema": QUERY_SCHEMA},
    {"name": "unit_convert", "description": "说明长度、面积、体积、时间和质量的单位关系与换算方向，不计算题目最终答案。", "inputSchema": QUERY_SCHEMA},
]


def tool_result(name, arguments):
    if name not in {tool["name"] for tool in TOOLS}:
        raise ValueError("unknown tool")
    if not isinstance(arguments, dict) or set(arguments) != {"query"}:
        raise ValueError("arguments must contain only query")
    query = arguments["query"]
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 500:
        raise ValueError("query must be a string of 2..500 characters")
    if name == "formula_hint":
        if any(word in query.lower() for word in ("括号", "parenthes", "(", "（")):
            text = "先看括号前的符号：前面是加号，括号内各项符号保持；前面是减号，每一项都要变号。若有乘数，检查是否乘到了括号内的每一项。请先自己写出这一步，再检查各项。"
        elif any(word in query for word in ("方程", "移项", "等式")):
            text = "先找出含未知数的项。等式两边同时做同一种运算，注意移项对应的符号变化；写完一步后代回原等式检查。"
        elif any(word in query for word in ("面积", "周长", "公式", "三角形", "圆", "长方形")):
            text = "先判断要求的是面积还是长度，再画图标出已知量。选择与图形对应的公式，检查每个量的单位是否一致，再由你代入计算。"
        else:
            return {"content": [{"type": "text", "text": "暂不支持该主题；可询问去括号、移项或几何公式的检查步骤。"}], "isError": True}
    else:
        groups = [(('平方', '面积'), "面积单位每相邻一级对应边长关系的平方；先把单位写成同一种面积单位，再判断应乘还是除。"),
                  (('立方', '体积', '毫升', '升'), "体积单位每相邻一级对应边长关系的立方；1 升等于 1000 毫升，1 立方分米等于 1 升。先统一单位再计算。"),
                  (('厘米', '毫米', '分米', '千米', '米', '长度'), "长度关系：1 千米等于 1000 米，1 米等于 10 分米或 100 厘米，1 厘米等于 10 毫米。大单位转小单位乘进率，反方向除进率。"),
                  (('小时', '分钟', '秒', '时间'), "时间关系：1 小时等于 60 分钟，1 分钟等于 60 秒。先识别转换跨了几级；大单位转小单位乘进率，反方向除进率。"),
                  (('千克', '克', '吨', '质量'), "质量关系：1 吨等于 1000 千克，1 千克等于 1000 克。先写出单位关系，再判断换算方向，由你完成数值计算。")]
        text = next((hint for words, hint in groups if any(word in query for word in words)), None)
        if text is None:
            return {"content": [{"type": "text", "text": "暂不支持该单位主题；可询问长度、面积、体积、时间或质量。"}], "isError": True}
    return {"content": [{"type": "text", "text": text}], "isError": False}


def create_app(token=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 32768
    expected = os.environ.get("MCP_AUTH_TOKEN", "") if token is None else token

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/mcp")
    def rpc():
        authorization = request.headers.get("Authorization", "")
        if not expected or not hmac.compare_digest(authorization.encode(), ("Bearer " + expected).encode()):
            return jsonify(error="unauthorized"), 401
        def error(code, message, identifier=None):
            return jsonify(jsonrpc="2.0", id=identifier, error={"code": code, "message": message})
        try:
            data = request.get_json(force=True)
        except Exception:
            return error(-32700, "parse error")
        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0" or not isinstance(data.get("method"), str) or ("id" in data and (isinstance(data["id"], bool) or not isinstance(data["id"], (str, int, type(None))))):
            return error(-32600, "invalid request")
        if "id" not in data:
            return "", 204
        identifier, method, params = data["id"], data["method"], data.get("params", {})
        if not isinstance(params, dict):
            return error(-32602, "invalid params", identifier)
        if method == "initialize":
            if params.get("protocolVersion") != PROTOCOL_VERSION:
                return error(-32602, "unsupported protocol version", identifier)
            result = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}}, "serverInfo": {"name": "campusclaw-teaching-tools", "version": "1.0.0"}}
        elif method == "tools/list":
            if params:
                return error(-32602, "invalid params", identifier)
            result = {"tools": TOOLS}
        elif method == "tools/call":
            try:
                if set(params) != {"name", "arguments"}:
                    raise ValueError("name and arguments required")
                result = tool_result(params["name"], params["arguments"])
            except (ValueError, TypeError):
                return error(-32602, "invalid tool or arguments", identifier)
        else:
            return error(-32601, "method not found", identifier)
        return jsonify(jsonrpc="2.0", id=identifier, result=result)
    return app


app = create_app()
