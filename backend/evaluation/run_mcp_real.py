"""Local launcher: private .env -> temporary runtime env, never Docker build args."""
import os
from pathlib import Path
import subprocess
import tempfile

def main():
    root = Path(__file__).resolve().parents[2]
    values = {}
    for line in (root / ".env").read_text(encoding="utf-8-sig").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    keys = ("CHAT_API_URL", "CHAT_API_KEY", "CHAT_MODEL")
    if not all(values.get(key) for key in keys): raise RuntimeError("private real CHAT config missing")
    if values["CHAT_API_URL"].rstrip("/") != "https://api.deepseek.com" or values["CHAT_MODEL"] != "deepseek-flash":
        raise RuntimeError("real CHAT destination/model differs from the five-case authorization")
    runtime = {key: values[key] for key in keys}
    runtime.update(CHAT_PROVIDER="openai-compatible", SECRET_KEY="disposable-mcp-server-secret", AUTH_TOKEN_SECRET="disposable-mcp-auth-secret", DATABASE_URL="postgresql+psycopg://mcp_test:disposable-mcp-only@mcp-postgres:5432/mcp_test", TUTOR_DISPOSABLE_DATABASE="true", MCP_DISPOSABLE_DATABASE="true", MCP_ENABLED="true", MCP_TOKEN_ENCRYPTION_KEY="ZGlzcG9zYWJsZS1tY3AtdGVzdC1rZXktMDAwMDAwMDA=", MCP_TOOL_POLICY_JSON='{"http://mcp-demo:8090":{"formula_hint":"read","unit_convert":"read"}}', EMBEDDING_PROVIDER="deterministic", EMBEDDING_DIMENSIONS="64", UPLOAD_DIR="/tmp/real-mcp-uploads", TRUSTED_ORIGINS="http://localhost:5284")
    evidence = root / "docs" / "mcp-acceptance"
    evidence.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="campusclaw-mcp-runtime-", suffix=".env")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("\n".join(key + "=" + value for key, value in runtime.items()))
        return subprocess.run(["docker", "run", "--rm", "--network", "campusclaw-mcp-test_default", "--env-file", name, "-v", str(root / "backend") + ":/app", "-v", str(evidence) + ":/evidence", "--entrypoint", "python", "campusclaw-mcp-test-mcp-api", "-m", "evaluation.mcp_real_review"], check=False).returncode
    finally:
        Path(name).unlink(missing_ok=True)

if __name__ == "__main__": raise SystemExit(main())
