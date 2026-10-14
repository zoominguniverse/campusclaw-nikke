# Retrieval evaluation

Corpus: 1.0.1; split: release

Semantic release passed: True

| Category | Mode | Metric | Passed / total | Required | Incomplete |
| --- | --- | --- | --- | --- | --- |
| exact | keyword | top1 | 30/30 | 30 | 0 |
| distributed | keyword | recall5 | 30/30 | 29 | 0 |
| paraphrase | vector | recall5 | 40/40 | 36 | 0 |
| paraphrase | hybrid | recall5 | 40/40 | 36 | 0 |
| unrelated | hybrid | empty | 20/20 | 19 | 0 |

Failures exact/keyword: none; incomplete: none


Failures distributed/keyword: none; incomplete: none


Failures paraphrase/vector: none; incomplete: none


Failures paraphrase/hybrid: none; incomplete: none


Failures unrelated/hybrid: none; incomplete: none


```json
{
  "metadata": {
    "embedding_provider": "openai-compatible",
    "embedding_model": "text-embedding-v4",
    "embedding_revision": "local-bailian-v4-v1",
    "dimensions": 1024,
    "chat_provider": "openai-compatible",
    "chat_model": "deepseek-flash",
    "hardware": "Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.41",
    "structural_browser_performance_gates": "passed",
    "profile_fingerprint": "340c5e8586b85a9473c8f940bee385108cf146f8522480315c1a98ddca5a8bbe",
    "processing_version": "source-map-v1;chunker-v2;jieba-0.42.1/default-dict+terms-v2",
    "vector_threshold": 0.35,
    "corpus_hash": "0f03c5350422abb8df916827d5a466a4e9961f6683c1b81c3f7138ae5851ce19",
    "retrieval_version": "sentence-gated-v1",
    "chat_prompt_version": "grounded-json-v3-question-coverage",
    "component_evidence": {
      "permission-results.json": "a06b2e81f285b1573a7de1319722b38276a32de471e846dc9333dd7d1d294f44",
      "performance-real-sentence-gated.json": "a52534d2ba07cd2be8a69f4d820acbbd1580aba45428418804704e569c0e7091",
      "migration-real-v2.json": "c8d61e4fe9a3da05a1a0ee962756f5463e5b02b84b9c120f190134fddaf64024",
      "browser-results.md": "c48d5b81a048c6c582d55289d470a33a3cb2123d331007057a70a3c73d4bb8e0",
      "release-final-review.completed.json": "6bb5ce600504b8eda7b5d69d2cedfb46184252470d78cd4d58fc29c1d60a7cf6"
    },
    "performance_chat_prompt_version": "grounded-json-v2-exclusivity"
  },
  "stage_latency": {
    "db": {
      "count": 410,
      "p95_ms": 12.179463003121782
    },
    "embedding": {
      "count": 410,
      "p95_ms": 193.45027500094147
    },
    "chat": {
      "count": 410,
      "p95_ms": 760.4564880020916
    },
    "total": {
      "count": 410,
      "p95_ms": 955.1163809956051
    }
  },
  "required_reviews_incomplete": [],
  "exact_comparisons": []
}
```
