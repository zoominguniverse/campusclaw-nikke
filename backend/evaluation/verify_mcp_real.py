"""Read-only verification of the existing five-case run; never calls CHAT."""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / "docs/mcp-acceptance/real-model.json"
    result = json.loads(source.read_text(encoding="utf-8"))
    records = result["records"]
    assert [r["case"] for r in records] == ["no_call", "choose", "dependent", "remote_failure", "budget"]
    assert result["model"] == "deepseek-flash"
    identifiers = [r["conversation_id"] for r in records]
    assert len(set(identifiers)) == 5 and all(type(i) is int and i > 0 for i in identifiers)
    # Only these fresh synthetic conversations, on the fixed disposable database.
    query = """SELECT json_agg(row_to_json(t)) FROM (
        SELECT c.id, c.mcp_attempt_count,
        (SELECT json_agg(json_build_object('id',m.id,'role',m.role,
          'content',m.content,'completion_state',m.completion_state,
          'tool_calls',m.tool_calls_json,'citations',m.citations_json) ORDER BY m.id)
         FROM messages m WHERE m.conversation_id=c.id) AS messages
        FROM conversations c WHERE c.id IN (%s) ORDER BY c.id
    ) t""" % ",".join(str(i) for i in identifiers)
    command = ["docker", "compose", "-f", str(root / "docker-compose.mcp-test.yml"),
               "exec", "-T", "mcp-postgres", "psql", "-U", "mcp_readonly", "-d", "mcp_test",
               "-At", "-v", "ON_ERROR_STOP=1", "-c", "BEGIN READ ONLY; " + query + "; COMMIT;"]
    output = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    database = json.loads(next(line for line in output.splitlines() if line.startswith("[")))
    database = {r["id"]: r for r in database}
    checks = []
    for record in records:
        assert record["http_status"] == 200
        events = record["events"]
        assert events[0]["event"] == "meta" and events[-1]["event"] == "done"
        first_delta = next(i for i, e in enumerate(events) if e["event"] == "delta")
        assert not any(e["event"] == "meta" for e in events[first_delta:])
        metas = [e["data"] for e in events if e["event"] == "meta"]
        assert all(m["citations"] == [] and m["demo_mode"] is False for m in metas)
        calls = metas[-1].get("tool_calls", [])
        audit = record["audit"]
        assert len({c["call_id"] for c in calls}) == len(calls) == len(audit)
        for call, entry in zip(calls, audit):
            assert all(call[key] == entry[key] for key in ("call_id", "round", "status", "reason_code"))
            assert call["text"][:200] == entry["summary"]
        stored = database[record["conversation_id"]]
        assert stored["mcp_attempt_count"] == len(audit)
        assert [m["role"] for m in stored["messages"]] == ["user", "assistant"]
        for message in stored["messages"]:
            assert message["completion_state"] == "complete" and message["tool_calls"] == calls
            assert message["citations"] == []
        assert stored["messages"][0]["content"] == record["question"]
        assert stored["messages"][1]["content"] == record["text"]
        assert events[-1]["data"]["message_id"] == stored["messages"][1]["id"]
        checks.append({"case": record["case"], "conversation_id": record["conversation_id"],
                       "audit_meta_message_snapshot_match": True, "delta_equals_stored_text": True,
                       "attempts": stored["mcp_attempt_count"], "decision_requests": len(record["decision_protocol"]),
                       "tool_rounds": [a["round"] for a in audit],
                       "warning": metas[-1].get("tool_warning")})
    by_case = {r["case"]: r for r in records}
    assert not by_case["no_call"]["audit"] and by_case["no_call"]["decision_protocol"][0]["calls"] == []
    choice = by_case["choose"]["decision_protocol"][0]["calls"]
    assert len(choice) == 1 and choice[0]["function"]["name"].endswith("_formula_hint")
    assert "2-(3+x)" in choice[0]["arguments"]["query"].replace(" ", "")
    dependent = by_case["dependent"]
    assert [a["round"] for a in dependent["audit"]] == [1, 2]
    first, second = dependent["decision_protocol"][:2]
    assert not [m for m in first["messages"] if m["role"] == "tool"]
    first_id = first["calls"][0]["id"]
    received = [m for m in second["messages"] if m["role"] == "tool"]
    assert len(received) == 1 and received[0]["tool_call_id"] == first_id
    assert second["calls"][0]["function"]["name"].endswith("_unit_convert")
    assert "减号" in second["calls"][0]["arguments"]["query"] and "厘米" in second["calls"][0]["arguments"]["query"]
    assert [a["reason_code"] for a in by_case["remote_failure"]["audit"]] == ["remote_unauthorized"]
    budget = by_case["budget"]
    assert len(budget["decision_protocol"]) == 1 and all(a["round"] == 1 for a in budget["audit"])
    assert any(e["data"].get("tool_warning") for e in budget["events"] if e["event"] == "meta")
    report = {"model": result["model"], "scope": result["scope"],
              "source_modified_utc": datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
              "verification": "read-only existing records; no further CHAT requests", "cases": checks,
              "database_snapshots": list(database.values())}
    destination = root / "docs/mcp-acceptance/real-model-verification.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS five real cases: decisions, SSE/audit/message snapshots, persisted quotas and final text match")


if __name__ == "__main__":
    main()
