"""Discover one file per operation, continue failures, always emit a redacted report."""
import argparse
import html
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

from helpers import Context, redact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inject-failure", action="store_true", help="verify failure report and nonzero exit")
    args = parser.parse_args()
    context, results = Context(), []
    try:
        context.preflight()
        cases = []
        for path in Path(__file__).parent.joinpath("cases").rglob("*.py"):
            spec = importlib.util.spec_from_file_location("case_" + str(len(cases)), path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cases.append((module.ORDER, str(path.relative_to(Path(__file__).parent)), module))
        ids = [module.OPERATION_ID for _, _, module in cases]
        assert len(ids) == len(set(ids)), "each operation must have one script"
        documented = {op["operationId"] for path, methods in context.document["paths"].items() if path.startswith("/api/") for op in methods.values()}
        assert documented == set(ids), "documented operations and case inventory differ: " + str(documented ^ set(ids))
        for _, name, module in sorted(cases):
            start, record_start = time.monotonic(), len(context.records)
            try:
                if getattr(module, "MCP_REQUIRED", False) and not context.mcp:
                    status, error = "SKIP", "Requires the distinct lesson-six MCP fixture; no MCP acceptance claimed."
                else:
                    module.run(context)
                    status, error = "PASS", ""
            except Exception as exception:
                status, error = "FAIL", traceback.format_exc()
            results.append({"case": name, "operation": module.OPERATION_ID, "status": status,
                            "seconds": round(time.monotonic() - start, 3), "error": error, "evidence": context.records[record_start:]})
            print(status, name, flush=True)
        if args.inject_failure:
            results.append({"case": "report-negative-self-check", "status": "FAIL", "error": "Bearer report-secret access_token=report-secret"})
            context.secrets.append("report-secret")
    except Exception as exception:
        results.append({"case": "preflight", "status": "FAIL", "error": f"{type(exception).__name__}: {exception}"})
    folder = Path(__file__).parent / "reports"
    folder.mkdir(exist_ok=True)
    safe = redact(json.dumps(results, ensure_ascii=False, indent=2), context.secrets)
    report = folder / "latest.html"
    report.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>CampusClaw API test</title><h1>Lesson 5 + 6 API verification</h1><p>' +
                      str(sum(r["status"] == "PASS" for r in results)) + '/' + str(len(results)) + ' passed; ' + str(sum(r["status"] == "SKIP" for r in results)) + ' skipped</p><pre>' + html.escape(safe) + '</pre></html>', encoding="utf-8")
    assert all(secret not in report.read_text(encoding="utf-8") for secret in context.secrets if len(secret) >= 8), "report leaked a credential"
    print("Report:", report, flush=True)
    return int(any(result["status"] == "FAIL" for result in results))


if __name__ == "__main__":
    sys.exit(main())
