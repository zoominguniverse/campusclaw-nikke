from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from .review import review_complete

EXPECTED_RELEASE = {"exact": 30, "distributed": 30, "paraphrase": 40, "unrelated": 20, "adversarial": 20, "permission": 20, "answer": 30}


def validate_corpus(corpus):
    materials = {m["id"]: m for m in corpus["materials"]}
    assert len(materials) == len(corpus["materials"]), "duplicate materials"
    assert len({c["id"] for c in corpus["cases"]}) == len(corpus["cases"]), "duplicate cases"
    counts = Counter(c["category"] for c in corpus["cases"] if c["split"] == "release")
    assert dict(counts) == EXPECTED_RELEASE, counts
    for case in corpus["cases"]:
        assert case["scope"]["class"] and case["scope"]["subjects"]
        assert type(case["can_answer"]) is bool and case["expected_status"] in {"answered", "insufficient", "no_evidence"}
        assert isinstance(case["reference_fact"], str)
        for label in case["labels"]:
            material = materials[label["material"]]
            assert material["split"] == case["split"]
            assert material["class"] == case["scope"]["class"]
            assert material["subject"] in case["scope"]["subjects"]
            assert 0 <= label["start"] < label["end"] <= len(material["text"])
            assert material["text"][label["start"]:label["end"]] == label["quote"]
        for denied in case.get("denied_materials", []):
            material = materials[denied]
            assert material["class"] != case["scope"]["class"] or material["subject"] not in case["scope"]["subjects"]
    return dict(counts)


def matches(hit, labels):
    for label in labels:
        if hit.get("material") != label["material"]:
            continue
        for span in hit.get("source_spans", []):
            if span["start"] < label["end"] and span["end"] > label["start"]:
                return True
    return False


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


def summarize(corpus, results, metadata, split="release"):
    validate_corpus(corpus)
    cases = {c["id"]: c for c in corpus["cases"] if c["split"] == split}
    # Each path is an independent gate; absent/skipped results cannot pass.
    gates = [("exact", "keyword", "top1", 1.0), ("distributed", "keyword", "recall5", .95),
             ("paraphrase", "vector", "recall5", .9), ("paraphrase", "hybrid", "recall5", .9),
             ("unrelated", "hybrid", "empty", .95)]
    records = {}
    for item in results:
        key = item["case_id"], item["mode"]
        if key in records:
            raise ValueError(f"duplicate result: {key}")
        if item["case_id"] not in {c["id"] for c in corpus["cases"]}:
            raise ValueError("unknown result case")
        records[key] = item
    metrics = []
    for category, mode, metric, minimum in gates:
        selected = [c for c in cases.values() if c["category"] == category]
        passed, failures, incomplete = 0, [], []
        for case in selected:
            item = records.get((case["id"], mode))
            if not item or item.get("status") != "ok":
                incomplete.append(case["id"])
                continue
            hits = item.get("hits", [])
            good = (not hits and item.get("chat_calls") == 0) if metric == "empty" else any(matches(h, case["labels"]) for h in hits[:1 if metric == "top1" else 5])
            if good:
                passed += 1
            else:
                failures.append(case["id"])
        required = math.ceil(minimum * len(selected))
        metrics.append({"category": category, "mode": mode, "metric": metric, "passed": passed, "total": len(selected), "required": required, "rate": passed / len(selected) if selected else None, "failures": failures, "incomplete": incomplete, "gate_passed": bool(selected) and passed >= required and not incomplete})
    comparisons = []
    for item in results:
        if "exact_top10" in item:
            exact = set(item["exact_top10"])
            actual = {hit["chunk_id"] for hit in item.get("hits", [])[:10]}
            comparisons.append({"case_id": item["case_id"], "recall10": len(exact & actual) / len(exact) if exact else None})
    latencies = {stage: {"count": len(values), "p95_ms": percentile(values, .95)} for stage in ("db", "embedding", "chat", "total") if (values := [r["latency_ms"][stage] for r in results if r.get("status") == "ok" and stage in r.get("latency_ms", {})])}
    safety_cases = [c for c in cases.values() if c["category"] in {"permission", "answer", "adversarial"}]
    reviews = []
    for case in safety_cases:
        modes = case.get("paths", ["ask"])
        for mode in modes:
            item = records.get((case["id"], mode))
            good = bool(item and item.get("status") == "ok" and (item.get("leak_count") == 0 if case["category"] == "permission" else item.get("human_review") == "supported" and item.get("unsupported_claims") == 0 and review_complete(item) and item.get("answer_status") == case["expected_status"] and item.get("demo_mode") is False))
            if not good:
                reviews.append({"case_id": case["id"], "mode": mode})
    real = all(metadata.get(name) == "openai-compatible" for name in ("embedding_provider", "chat_provider"))
    complete_metadata = all(metadata.get(name) for name in ("embedding_model", "embedding_revision", "dimensions", "chat_model", "hardware"))
    return {"corpus_version": corpus["version"], "split": split, "metadata": metadata, "metrics": metrics, "exact_comparisons": comparisons, "stage_latency": latencies, "required_reviews_incomplete": reviews,
            "semantic_release_passed": real and complete_metadata and all(m["gate_passed"] for m in metrics) and not reviews and metadata.get("structural_browser_performance_gates") == "passed"}


def write_report(report, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Retrieval evaluation", "", f"Corpus: {report['corpus_version']}; split: {report['split']}", "", f"Semantic release passed: {report['semantic_release_passed']}", "", "| Category | Mode | Metric | Passed / total | Required | Incomplete |", "| --- | --- | --- | --- | --- | --- |"]
    for metric in report["metrics"]:
        lines.append(f"| {metric['category']} | {metric['mode']} | {metric['metric']} | {metric['passed']}/{metric['total']} | {metric['required']} | {len(metric['incomplete'])} |")
    for metric in report["metrics"]:
        lines.extend(["", f"Failures {metric['category']}/{metric['mode']}: {', '.join(metric['failures']) or 'none'}; incomplete: {', '.join(metric['incomplete']) or 'none'}", ""])
    lines.extend(["", "```json", json.dumps({k: report[k] for k in ("metadata", "stage_latency", "required_reviews_incomplete", "exact_comparisons")}, ensure_ascii=False, indent=2), "```", ""])
    path.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True, help="JSON containing results and non-secret metadata")
    parser.add_argument("--corpus", type=Path, default=Path(__file__).with_name("corpus-v1.json"))
    parser.add_argument("--split", choices=["dev", "release"], default="release")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    report = summarize(json.loads(args.corpus.read_text(encoding="utf-8")), data["results"], data["metadata"], args.split)
    write_report(report, args.output)
    raise SystemExit(0 if report["semantic_release_passed"] else 2)
