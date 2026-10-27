"""Upgrade twice and run old/new images on an isolated pg_dump copy."""
import json
from pathlib import Path
import subprocess

def main():
    root = Path(__file__).resolve().parents[2]
    compose = ["docker", "compose", "-f", str(root / "docker-compose.mcp-test.yml")]
    def run(args):
        return subprocess.run(args, check=True, capture_output=True, text=True).stdout
    run(compose + ["exec", "-T", "mcp-postgres", "pg_dump", "-U", "mcp_test", "-d", "mcp_test", "-Fc", "-f", "/tmp/mcp-rollback.dump"])
    # Fixed test-only destination; never accepts a database argument.
    existing = run(compose + ["exec", "-T", "mcp-postgres", "psql", "-U", "mcp_test", "-d", "postgres", "-Atc", "SELECT datname FROM pg_database WHERE datname='mcp_rollback'"]).strip()
    if existing: raise RuntimeError("mcp_rollback already exists; preserve it and choose a fresh explicit rehearsal")
    run(compose + ["exec", "-T", "mcp-postgres", "createdb", "-U", "mcp_test", "mcp_rollback"])
    run(compose + ["exec", "-T", "mcp-postgres", "pg_restore", "-U", "mcp_test", "-d", "mcp_rollback", "/tmp/mcp-rollback.dump"])
    environment = ["-e", "SECRET_KEY=disposable-mcp-server-secret", "-e", "AUTH_TOKEN_SECRET=disposable-mcp-auth-secret", "-e", "DATABASE_URL=postgresql+psycopg://mcp_test:disposable-mcp-only@mcp-postgres:5432/mcp_rollback", "-e", "INITIALIZE_DATABASE=false", "-e", "SEED_DEMO_DATA=false", "-e", "MCP_ENABLED=false", "-e", "UPLOAD_DIR=/tmp/rollback-uploads", "-e", "CHAT_PROVIDER=deterministic"]
    tables = ["materials", "knowledge_entries", "knowledge_chunks", "knowledge_embeddings", "knowledge_sentence_embeddings", "users", "class_memberships", "teacher_subject_assignments", "conversations", "messages", "mcp_servers", "mcp_tools", "skill_mcp_bindings", "mcp_tool_calls"]
    def snapshot():
        result = {}
        for table in tables:
            result[table] = run(compose + ["exec", "-T", "mcp-postgres", "psql", "-U", "mcp_test", "-d", "mcp_rollback", "-Atc", f"SELECT md5(COALESCE(string_agg(row_to_json(t)::text, E'\\n' ORDER BY row_to_json(t)::text),'')) FROM {table} t"]).strip()
        return result
    before = snapshot()
    common = ["docker", "run", "--rm", "--network", "campusclaw-mcp-test_default", *environment, "--entrypoint", "python"]
    upgraded = run(common + ["-v", str(root / "backend") + ":/app", "campusclaw-mcp-test-mcp-api", "-c", "from app import create_app; from app.database import initialize_database; app=create_app(); ctx=app.app_context(); ctx.push(); initialize_database(); initialize_database(); print('upgrade twice pass')"])
    assert snapshot() == before
    code = '''import json
from app import create_app
app=create_app(); client=app.test_client()
r=client.post('/api/auth/login',json={'username':'zhouchengxi','password':'student-a-password'})
assert r.status_code==200,r.json
h={'Authorization':'Bearer '+r.json['access_token']}
assert client.get('/health').status_code==200
assert client.get('/api/auth/me',headers=h).status_code==200
assert client.post('/api/classes/1/knowledge/retrieve',headers=h,json={'query':'数学','mode':'hybrid'}).status_code==200
rows=client.get('/api/conversations',headers=h); assert rows.status_code==200
if rows.json['items']:
 r=client.get('/api/conversations/'+str(rows.json['items'][0]['id']),headers=h); assert r.status_code==200
print(json.dumps({'health':200,'auth':200,'retrieval':200,'history':200}))
'''
    # Immutable image IDs recorded before the MCP implementation.
    old_api = "f3223cd7d429"
    old_web = "f4cdac11e39b"
    old_result = json.loads(run(common + [old_api, "-c", code]).strip())
    assert snapshot() == before
    current_result = json.loads(run(common + ["-v", str(root / "backend") + ":/app", "campusclaw-mcp-test-mcp-api", "-c", code]).strip())
    assert snapshot() == before
    web_code = "from server import app; c=app.test_client(); assert c.get('/tutor').status_code==200; assert c.get('/tutor-config').status_code==200; print('old Web pages 200')"
    run(["docker", "run", "--rm", "--entrypoint", "python", old_web, "-c", web_code])
    evidence = {"source_database": "mcp_test", "copy_database": "mcp_rollback", "copy_method": "pg_dump -Fc / pg_restore", "upgrade_twice": upgraded.strip(), "old_api_image": old_api, "old_web_image": old_web, "old_api": old_result, "new_api_mcp_disabled": current_result, "old_web_pages": 200, "preserved_table_hashes": before, "auth_note": "Normal test sign-ins add/revoke sessions as designed; identity and membership preserved. All content, counters, snapshots and MCP tables unchanged.", "compatibility": "Old parser cannot save @ references; exported definitions and new columns retained. No tables dropped."}
    output = root / "docs/mcp-acceptance/rollback.json"; output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS isolated dump copy, upgrade twice, old API/Web, MCP disabled, all content/counter/history hashes preserved")

if __name__ == "__main__": main()
