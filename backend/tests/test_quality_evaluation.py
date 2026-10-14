import json
from pathlib import Path

import pytest

from evaluation.report import EXPECTED_RELEASE, summarize, validate_corpus, write_report


@pytest.fixture()
def corpus():
    return json.loads((Path(__file__).parents[1] / "evaluation/corpus-v1.json").read_text(encoding="utf-8"))


def test_corpus_counts_offsets_scopes_and_independent_dev(corpus):
    assert validate_corpus(corpus) == EXPECTED_RELEASE
    texts = {m["text"] for m in corpus["materials"] if m["split"] == "release"}
    assert all(m["text"] not in texts for m in corpus["materials"] if m["split"] == "dev")


def test_development_negatives_preserve_frozen_release(corpus):
    extended = json.loads((Path(__file__).parents[1] / "evaluation/corpus-dev-v1.json").read_text(encoding="utf-8"))
    assert validate_corpus(extended) == EXPECTED_RELEASE
    assert extended['materials'] == corpus['materials']
    assert [c for c in extended['cases'] if c['split'] == 'release'] == [c for c in corpus['cases'] if c['split'] == 'release']
    negatives = [c for c in extended['cases'] if c['split'] == 'dev' and c['category'] == 'unrelated']
    assert len(negatives) == 20
    assert all(not c['labels'] and c['expected_status'] == 'no_evidence' and c['scope'] == {'class': 'D', 'subjects': ['science']} for c in negatives)


def test_preset_metrics_counts_missing_failures_and_demo_release(corpus, tmp_path):
    results = []
    for case in corpus["cases"]:
        for mode in (["vector", "hybrid"] if case["category"] == "paraphrase" else ["hybrid"] if case["category"] == "unrelated" else ["keyword"]):
            hits = [{"material": label["material"], "chunk_id": case["id"], "source_spans": [{"start": label["start"], "end": label["end"]}]} for label in case["labels"]]
            results.append({"case_id": case["id"], "mode": mode, "status": "ok", "hits": hits, "chat_calls": 0, "latency_ms": {"db": 10}})
    results = [r for r in results if (r["case_id"], r["mode"]) != ("exact-01", "keyword")]
    next(r for r in results if r["case_id"] == "distributed-01")["hits"] = []
    next(r for r in results if r["case_id"] == "distributed-02")["hits"] = []
    next(r for r in results if r["case_id"] == "unrelated-01")["chat_calls"] = 1
    comparison = next(r for r in results if r["hits"])
    comparison["exact_top10"] = [comparison["hits"][0]["chunk_id"], "missing"]
    report = summarize(corpus, results, {"embedding_provider": "deterministic"})
    assert report["metrics"][0]["passed"] == 29
    assert report["metrics"][0]["incomplete"] == ["exact-01"]
    assert report["metrics"][1]["required"] == 29
    assert report["metrics"][1]["failures"] == ["distributed-01", "distributed-02"]
    assert report["metrics"][2]["required"] == 36
    assert report["metrics"][4]["passed"] == 19
    assert report["exact_comparisons"][0]["recall10"] == .5
    assert report["stage_latency"]["db"]["p95_ms"] == 10
    assert not report["semantic_release_passed"]
    write_report(report, tmp_path / "preset")
    assert json.loads((tmp_path / "preset.json").read_text(encoding="utf-8")) == report
    assert "distributed-01" in (tmp_path / "preset.md").read_text(encoding="utf-8")


def test_skipped_required_cases_are_incomplete(corpus):
    report = summarize(corpus, [{"case_id": "exact-01", "mode": "keyword", "status": "skipped"}], {})
    assert len(report["metrics"][0]["incomplete"]) == 30
    assert not report["metrics"][0]["gate_passed"]
