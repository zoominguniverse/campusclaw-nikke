"""Container-side protocol smoke; emits no credential or request headers."""
import json
import os
import urllib.request
import urllib.error

def main():
    origin = os.getenv("MCP_SMOKE_ORIGIN", "http://mcp-demo:8090")
    token = os.environ["MCP_SMOKE_TOKEN"]
    assert urllib.request.urlopen(origin + "/health", timeout=5).status == 200
    try:
        urllib.request.urlopen(urllib.request.Request(origin + "/mcp", data=b"{}", headers={"Content-Type": "application/json"}), timeout=5)
        raise AssertionError("missing credential accepted")
    except urllib.error.HTTPError as error:
        assert error.code == 401
    def rpc(method, params):
        payload = json.dumps({"jsonrpc": "2.0", "id": method, "method": method, "params": params}).encode()
        with urllib.request.urlopen(urllib.request.Request(origin + "/mcp", data=payload, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}), timeout=5) as response:
            body = json.load(response)
        assert body["id"] == method and "error" not in body
        return body["result"]
    assert rpc("initialize", {"protocolVersion": "2024-11-05"})["protocolVersion"] == "2024-11-05"
    assert {tool["name"] for tool in rpc("tools/list", {})["tools"]} == {"formula_hint", "unit_convert"}
    for name, query in (("formula_hint", "去括号 2-(3+x)"), ("unit_convert", "3米换算厘米")):
        result = rpc("tools/call", {"name": name, "arguments": {"query": query}})
        assert result["isError"] is False and result["content"][0]["text"]
    print("PASS health=200 missing-token=401 initialize/list/call ID-correlated, two bounded hint tools")

if __name__ == "__main__": main()
