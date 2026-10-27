"""Actual HTTP SSE fixture with controlled delays and protocol faults."""
import json
import time
import threading
from flask import Flask, Response, request

app = Flask(__name__)
guard = threading.Lock()
stats = {"started": 0, "completed": 0, "closed": 0, "last_started": 0, "last_completed": 0, "decisions": 0}


@app.get("/status")
def status():
    with guard:
        return dict(stats)


@app.post("/chat/completions")
def completion():
    payload = request.get_json()
    question = payload["messages"][-1]["content"]
    with guard:
        stats["started"] += 1
        stats["last_started"] = time.time()
    if "首帧失败验收" in question:
        return {"error": "fixture failure"}, 503
    if not payload.get("stream"):
        if payload.get("tools"):
            with guard:
                stats["decisions"] += 1
            question = next(m["content"] for m in reversed(payload["messages"]) if m["role"] == "user")
            results = [m for m in payload["messages"] if m["role"] == "tool"]
            if "不调用工具" in question or (len(results) >= 2 and "无限工具验收" not in question):
                return {"choices": [{"message": {"content": "decision prose is not final text"}, "finish_reason": "stop"}]}
            names = [t["function"]["name"] for t in payload["tools"]]
            preferred = "unit_convert" if results else "formula_hint"
            name = next((n for n in names if preferred in n), names[0])
            if "伪造工具验收" in question: name = "mcp_999_foreign"
            arguments = {"query": "单位换算：米和厘米" if results else "去括号 2-(3+x)"}
            if "非法参数验收" in question: arguments = {"query": 42}
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": f"fixture_call_{len(results)}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}]}, "finish_reason": "tool_calls"}]}
        return {"choices": [{"message": {"content": json.dumps({"status": "insufficient", "claims": []})}}]}

    def frame(value):
        return "data: " + json.dumps(value, ensure_ascii=False) + "\n\n"

    def stream():
        try:
            yield frame({"choices": [{"index": 0, "delta": {"role": "assistant", "reasoning_content": "hidden fixture reasoning"}}]})
            time.sleep(.15)
            if "零正文失败验收" in question:
                yield frame({"error": "hidden fixture fault"})
                return
            yield frame({"choices": [{"index": 0, "delta": {"content": "测试模式：请先检查条件😀。"}}]})
            time.sleep(5 if "UI取消验收" in question else .2)
            if "部分失败验收" in question:
                yield frame({"error": "hidden fixture fault"})
                return
            yield frame({"choices": [{"index": 0, "delta": {"content": "再说明每一步的理由["}}]})
            time.sleep(.15)
            yield frame({"choices": [{"index": 0, "delta": {"content": "1]，不跳过思考。[999] <script>window.fixtureUnsafe=true</script>"}}]})
            time.sleep(1 if "慢流验收" not in question else 3)
            if "EOF失败验收" in question:
                return
            yield frame({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
            with guard:
                stats["completed"] += 1
                stats["last_completed"] = time.time()
            yield "data: [DONE]\n\n"
        finally:
            with guard:
                stats["closed"] += 1

    return Response(stream(), mimetype="text/event-stream")
