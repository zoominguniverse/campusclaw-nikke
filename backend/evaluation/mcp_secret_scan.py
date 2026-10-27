"""Local-only credential comparison; never prints or passes credentials to Docker."""
import json
from pathlib import Path
import subprocess

def main():
    root = Path(__file__).resolve().parents[2]
    secrets = []
    for line in (root / ".env").read_text(encoding="utf-8-sig").splitlines():
        if not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if any(word in key for word in ("SECRET", "PASSWORD", "API_KEY", "MCP_AUTH_TOKEN", "MCP_TOKEN_ENCRYPTION_KEY")) and len(value) >= 8:
                secrets.append(value)
    scanned = []
    for directory in (root / "frontend", root / "mcp-server"):
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".js", ".html", ".css", ".py", ".txt", ".md"}:
                contents = path.read_text(encoding="utf-8", errors="replace")
                assert not any(secret in contents for secret in secrets), "private credential found in public/build source"
    images = ["campusclaw-mcp-test-mcp-api", "campusclaw-mcp-test-mcp-web", "campusclaw-mcp-test-mcp-demo"]
    code = "from pathlib import Path; import sys; [sys.stdout.buffer.write(p.read_bytes()+b'\\n') for p in Path('/app').rglob('*') if p.is_file() and p.suffix in {'.py','.js','.css','.html','.txt','.md','.env'} and p.stat().st_size<2000000]"
    for image in images:
        history = subprocess.run(["docker", "history", "--no-trunc", "--format", "{{.CreatedBy}}", image], check=True, capture_output=True).stdout
        files = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", image, "-c", code], check=True, capture_output=True).stdout
        assert not any(secret.encode() in history + files for secret in secrets), "private credential found in image"
        scanned.append(image)
    report = root / "apitest/reports/latest.html"
    if report.exists():
        contents = report.read_text(encoding="utf-8")
        assert not any(secret in contents for secret in secrets + ["disposable-mcp-token", "ZGlzcG9zYWJsZS1tY3AtdGVzdC1rZXktMDAwMDAwMDA="]), "credential found in report"
    review_files = list((root / "docs/mcp-acceptance").glob("*.json")) + list((root / "docs/mcp-acceptance").glob("*.txt"))
    for path in review_files:
        contents = path.read_text(encoding="utf-8")
        assert not any(secret in contents for secret in secrets + ["disposable-mcp-token", "ZGlzcG9zYWJsZS1tY3AtdGVzdC1rZXktMDAwMDAwMDA="]), "credential found in acceptance evidence"
    evidence = {"private_credentials_compared_locally": len(secrets), "frontend_and_mcp_source": "pass", "image_history_and_app_files": scanned, "docker_scan_network": "none", "report": "pass", "acceptance_json_and_text_records": "pass", "actual_values_printed_or_sent_to_container": False}
    output = root / "docs/mcp-acceptance/secret-scan.json"; output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("PASS private credentials absent from frontend/tool sources, three image histories/app files, HTML report and acceptance records")

if __name__ == "__main__": main()
