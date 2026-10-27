"""Exercise the actual main Compose in a new, explicitly disposable project."""
import json
import os
from pathlib import Path
import subprocess

def main():
    root = Path(__file__).resolve().parents[2]
    command = ["docker", "compose", "-p", "campusclaw-mcp-main-smoke", "--env-file", str(root / ".env.example"), "-f", str(root / "docker-compose.yml")]
    environment = dict(os.environ, MCP_AUTH_TOKEN="disposable-mcp-token", MCP_ENABLED="false", CHAT_PROVIDER="deterministic", EMBEDDING_PROVIDER="deterministic", SEED_DEMO_DATA="false", SEMANTIC_RELEASE="false")
    def run(arguments):
        subprocess.run(command + arguments, env=environment, check=True)
    try:
        run(["up", "-d", "--build", "--wait", "postgres", "api", "mcp-demo"])
        run(["exec", "-T", "-e", "MCP_SMOKE_TOKEN=disposable-mcp-token", "api", "python", "-m", "evaluation.mcp_smoke"])
        run(["stop", "mcp-demo"])
        run(["exec", "-T", "api", "python", "-c", "import requests; assert requests.get('http://localhost:8080/health',timeout=5).status_code==200; assert requests.get('http://localhost:8080/api/classes/1/materials',timeout=5).status_code==401; print('PASS main Compose: MCP stopped, health200 and original material route401')"])
        evidence = root / "docs/mcp-acceptance/main-compose.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps({"project": "campusclaw-mcp-main-smoke", "source": "docker-compose.yml", "private_environment_file": False, "container_initialize_list_two_calls": "pass", "missing_token_401": "pass", "mcp_stopped_api_health": 200, "mcp_stopped_original_material_route": 401}, indent=2), encoding="utf-8")
    finally:
        # This project was created above, has no shared/development resources,
        # and is the only target of cleanup. Never run against the default project.
        run(["down", "--volumes"])

if __name__ == "__main__": main()
