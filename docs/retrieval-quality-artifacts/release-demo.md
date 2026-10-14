# Retrieval evaluation

Corpus: 1.0.1; split: release

Semantic release passed: False

| Category | Mode | Metric | Passed / total | Required | Incomplete |
| --- | --- | --- | --- | --- | --- |
| exact | keyword | top1 | 30/30 | 30 | 0 |

Failures exact/keyword: none; incomplete: none

| distributed | keyword | recall5 | 30/30 | 29 | 0 |

Failures distributed/keyword: none; incomplete: none

| paraphrase | vector | recall5 | 0/40 | 36 | 40 |

Failures paraphrase/vector: none; incomplete: paraphrase-01, paraphrase-31, paraphrase-02, paraphrase-32, paraphrase-03, paraphrase-33, paraphrase-04, paraphrase-34, paraphrase-05, paraphrase-35, paraphrase-06, paraphrase-36, paraphrase-07, paraphrase-37, paraphrase-08, paraphrase-38, paraphrase-09, paraphrase-39, paraphrase-10, paraphrase-40, paraphrase-11, paraphrase-12, paraphrase-13, paraphrase-14, paraphrase-15, paraphrase-16, paraphrase-17, paraphrase-18, paraphrase-19, paraphrase-20, paraphrase-21, paraphrase-22, paraphrase-23, paraphrase-24, paraphrase-25, paraphrase-26, paraphrase-27, paraphrase-28, paraphrase-29, paraphrase-30

| paraphrase | hybrid | recall5 | 0/40 | 36 | 40 |

Failures paraphrase/hybrid: none; incomplete: paraphrase-01, paraphrase-31, paraphrase-02, paraphrase-32, paraphrase-03, paraphrase-33, paraphrase-04, paraphrase-34, paraphrase-05, paraphrase-35, paraphrase-06, paraphrase-36, paraphrase-07, paraphrase-37, paraphrase-08, paraphrase-38, paraphrase-09, paraphrase-39, paraphrase-10, paraphrase-40, paraphrase-11, paraphrase-12, paraphrase-13, paraphrase-14, paraphrase-15, paraphrase-16, paraphrase-17, paraphrase-18, paraphrase-19, paraphrase-20, paraphrase-21, paraphrase-22, paraphrase-23, paraphrase-24, paraphrase-25, paraphrase-26, paraphrase-27, paraphrase-28, paraphrase-29, paraphrase-30

| unrelated | hybrid | empty | 0/20 | 19 | 20 |

Failures unrelated/hybrid: none; incomplete: unrelated-01, unrelated-02, unrelated-03, unrelated-04, unrelated-05, unrelated-06, unrelated-07, unrelated-08, unrelated-09, unrelated-10, unrelated-11, unrelated-12, unrelated-13, unrelated-14, unrelated-15, unrelated-16, unrelated-17, unrelated-18, unrelated-19, unrelated-20


```json
{
  "metadata": {
    "embedding_provider": "deterministic",
    "embedding_model": "campusclaw-deterministic",
    "embedding_revision": "sha256-demo-v1",
    "dimensions": 64,
    "chat_provider": "deterministic",
    "chat_model": "campusclaw-deterministic",
    "hardware": "Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.41",
    "structural_browser_performance_gates": "incomplete",
    "profile_fingerprint": "93a61e494055dd956a003109bb9b215031372bab1704bd607bdc6ef4a4d98274",
    "processing_version": "source-map-v1;chunker-v2;jieba-0.42.1/default-dict+terms-v2",
    "vector_threshold": 0.35,
    "corpus_hash": "0f03c5350422abb8df916827d5a466a4e9961f6683c1b81c3f7138ae5851ce19"
  },
  "stage_latency": {
    "db": {
      "count": 120,
      "p95_ms": 2.9555799992522225
    },
    "embedding": {
      "count": 120,
      "p95_ms": 0.0
    },
    "chat": {
      "count": 120,
      "p95_ms": 0.0
    },
    "total": {
      "count": 120,
      "p95_ms": 9.99688999945647
    }
  },
  "required_reviews_incomplete": [
    {
      "case_id": "answer-01",
      "mode": "ask"
    },
    {
      "case_id": "answer-02",
      "mode": "ask"
    },
    {
      "case_id": "answer-03",
      "mode": "ask"
    },
    {
      "case_id": "answer-04",
      "mode": "ask"
    },
    {
      "case_id": "answer-05",
      "mode": "ask"
    },
    {
      "case_id": "answer-06",
      "mode": "ask"
    },
    {
      "case_id": "answer-07",
      "mode": "ask"
    },
    {
      "case_id": "answer-08",
      "mode": "ask"
    },
    {
      "case_id": "answer-09",
      "mode": "ask"
    },
    {
      "case_id": "answer-10",
      "mode": "ask"
    },
    {
      "case_id": "answer-11",
      "mode": "ask"
    },
    {
      "case_id": "answer-12",
      "mode": "ask"
    },
    {
      "case_id": "answer-13",
      "mode": "ask"
    },
    {
      "case_id": "answer-14",
      "mode": "ask"
    },
    {
      "case_id": "answer-15",
      "mode": "ask"
    },
    {
      "case_id": "answer-16",
      "mode": "ask"
    },
    {
      "case_id": "answer-17",
      "mode": "ask"
    },
    {
      "case_id": "answer-18",
      "mode": "ask"
    },
    {
      "case_id": "answer-19",
      "mode": "ask"
    },
    {
      "case_id": "answer-20",
      "mode": "ask"
    },
    {
      "case_id": "answer-21",
      "mode": "ask"
    },
    {
      "case_id": "answer-22",
      "mode": "ask"
    },
    {
      "case_id": "answer-23",
      "mode": "ask"
    },
    {
      "case_id": "answer-24",
      "mode": "ask"
    },
    {
      "case_id": "answer-25",
      "mode": "ask"
    },
    {
      "case_id": "answer-26",
      "mode": "ask"
    },
    {
      "case_id": "answer-27",
      "mode": "ask"
    },
    {
      "case_id": "answer-28",
      "mode": "ask"
    },
    {
      "case_id": "answer-29",
      "mode": "ask"
    },
    {
      "case_id": "answer-30",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-01",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-02",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-03",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-04",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-05",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-06",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-07",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-08",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-09",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-10",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-11",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-12",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-13",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-14",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-15",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-16",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-17",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-18",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-19",
      "mode": "ask"
    },
    {
      "case_id": "adversarial-20",
      "mode": "ask"
    },
    {
      "case_id": "permission-01",
      "mode": "keyword"
    },
    {
      "case_id": "permission-01",
      "mode": "vector"
    },
    {
      "case_id": "permission-01",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-01",
      "mode": "ask"
    },
    {
      "case_id": "permission-01",
      "mode": "detail"
    },
    {
      "case_id": "permission-01",
      "mode": "preview"
    },
    {
      "case_id": "permission-01",
      "mode": "retry"
    },
    {
      "case_id": "permission-02",
      "mode": "keyword"
    },
    {
      "case_id": "permission-02",
      "mode": "vector"
    },
    {
      "case_id": "permission-02",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-02",
      "mode": "ask"
    },
    {
      "case_id": "permission-02",
      "mode": "detail"
    },
    {
      "case_id": "permission-02",
      "mode": "preview"
    },
    {
      "case_id": "permission-02",
      "mode": "retry"
    },
    {
      "case_id": "permission-03",
      "mode": "keyword"
    },
    {
      "case_id": "permission-03",
      "mode": "vector"
    },
    {
      "case_id": "permission-03",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-03",
      "mode": "ask"
    },
    {
      "case_id": "permission-03",
      "mode": "detail"
    },
    {
      "case_id": "permission-03",
      "mode": "preview"
    },
    {
      "case_id": "permission-03",
      "mode": "retry"
    },
    {
      "case_id": "permission-04",
      "mode": "keyword"
    },
    {
      "case_id": "permission-04",
      "mode": "vector"
    },
    {
      "case_id": "permission-04",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-04",
      "mode": "ask"
    },
    {
      "case_id": "permission-04",
      "mode": "detail"
    },
    {
      "case_id": "permission-04",
      "mode": "preview"
    },
    {
      "case_id": "permission-04",
      "mode": "retry"
    },
    {
      "case_id": "permission-05",
      "mode": "keyword"
    },
    {
      "case_id": "permission-05",
      "mode": "vector"
    },
    {
      "case_id": "permission-05",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-05",
      "mode": "ask"
    },
    {
      "case_id": "permission-05",
      "mode": "detail"
    },
    {
      "case_id": "permission-05",
      "mode": "preview"
    },
    {
      "case_id": "permission-05",
      "mode": "retry"
    },
    {
      "case_id": "permission-06",
      "mode": "keyword"
    },
    {
      "case_id": "permission-06",
      "mode": "vector"
    },
    {
      "case_id": "permission-06",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-06",
      "mode": "ask"
    },
    {
      "case_id": "permission-06",
      "mode": "detail"
    },
    {
      "case_id": "permission-06",
      "mode": "preview"
    },
    {
      "case_id": "permission-06",
      "mode": "retry"
    },
    {
      "case_id": "permission-07",
      "mode": "keyword"
    },
    {
      "case_id": "permission-07",
      "mode": "vector"
    },
    {
      "case_id": "permission-07",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-07",
      "mode": "ask"
    },
    {
      "case_id": "permission-07",
      "mode": "detail"
    },
    {
      "case_id": "permission-07",
      "mode": "preview"
    },
    {
      "case_id": "permission-07",
      "mode": "retry"
    },
    {
      "case_id": "permission-08",
      "mode": "keyword"
    },
    {
      "case_id": "permission-08",
      "mode": "vector"
    },
    {
      "case_id": "permission-08",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-08",
      "mode": "ask"
    },
    {
      "case_id": "permission-08",
      "mode": "detail"
    },
    {
      "case_id": "permission-08",
      "mode": "preview"
    },
    {
      "case_id": "permission-08",
      "mode": "retry"
    },
    {
      "case_id": "permission-09",
      "mode": "keyword"
    },
    {
      "case_id": "permission-09",
      "mode": "vector"
    },
    {
      "case_id": "permission-09",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-09",
      "mode": "ask"
    },
    {
      "case_id": "permission-09",
      "mode": "detail"
    },
    {
      "case_id": "permission-09",
      "mode": "preview"
    },
    {
      "case_id": "permission-09",
      "mode": "retry"
    },
    {
      "case_id": "permission-10",
      "mode": "keyword"
    },
    {
      "case_id": "permission-10",
      "mode": "vector"
    },
    {
      "case_id": "permission-10",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-10",
      "mode": "ask"
    },
    {
      "case_id": "permission-10",
      "mode": "detail"
    },
    {
      "case_id": "permission-10",
      "mode": "preview"
    },
    {
      "case_id": "permission-10",
      "mode": "retry"
    },
    {
      "case_id": "permission-11",
      "mode": "keyword"
    },
    {
      "case_id": "permission-11",
      "mode": "vector"
    },
    {
      "case_id": "permission-11",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-11",
      "mode": "ask"
    },
    {
      "case_id": "permission-11",
      "mode": "detail"
    },
    {
      "case_id": "permission-11",
      "mode": "preview"
    },
    {
      "case_id": "permission-11",
      "mode": "retry"
    },
    {
      "case_id": "permission-12",
      "mode": "keyword"
    },
    {
      "case_id": "permission-12",
      "mode": "vector"
    },
    {
      "case_id": "permission-12",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-12",
      "mode": "ask"
    },
    {
      "case_id": "permission-12",
      "mode": "detail"
    },
    {
      "case_id": "permission-12",
      "mode": "preview"
    },
    {
      "case_id": "permission-12",
      "mode": "retry"
    },
    {
      "case_id": "permission-13",
      "mode": "keyword"
    },
    {
      "case_id": "permission-13",
      "mode": "vector"
    },
    {
      "case_id": "permission-13",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-13",
      "mode": "ask"
    },
    {
      "case_id": "permission-13",
      "mode": "detail"
    },
    {
      "case_id": "permission-13",
      "mode": "preview"
    },
    {
      "case_id": "permission-13",
      "mode": "retry"
    },
    {
      "case_id": "permission-14",
      "mode": "keyword"
    },
    {
      "case_id": "permission-14",
      "mode": "vector"
    },
    {
      "case_id": "permission-14",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-14",
      "mode": "ask"
    },
    {
      "case_id": "permission-14",
      "mode": "detail"
    },
    {
      "case_id": "permission-14",
      "mode": "preview"
    },
    {
      "case_id": "permission-14",
      "mode": "retry"
    },
    {
      "case_id": "permission-15",
      "mode": "keyword"
    },
    {
      "case_id": "permission-15",
      "mode": "vector"
    },
    {
      "case_id": "permission-15",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-15",
      "mode": "ask"
    },
    {
      "case_id": "permission-15",
      "mode": "detail"
    },
    {
      "case_id": "permission-15",
      "mode": "preview"
    },
    {
      "case_id": "permission-15",
      "mode": "retry"
    },
    {
      "case_id": "permission-16",
      "mode": "keyword"
    },
    {
      "case_id": "permission-16",
      "mode": "vector"
    },
    {
      "case_id": "permission-16",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-16",
      "mode": "ask"
    },
    {
      "case_id": "permission-16",
      "mode": "detail"
    },
    {
      "case_id": "permission-16",
      "mode": "preview"
    },
    {
      "case_id": "permission-16",
      "mode": "retry"
    },
    {
      "case_id": "permission-17",
      "mode": "keyword"
    },
    {
      "case_id": "permission-17",
      "mode": "vector"
    },
    {
      "case_id": "permission-17",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-17",
      "mode": "ask"
    },
    {
      "case_id": "permission-17",
      "mode": "detail"
    },
    {
      "case_id": "permission-17",
      "mode": "preview"
    },
    {
      "case_id": "permission-17",
      "mode": "retry"
    },
    {
      "case_id": "permission-18",
      "mode": "keyword"
    },
    {
      "case_id": "permission-18",
      "mode": "vector"
    },
    {
      "case_id": "permission-18",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-18",
      "mode": "ask"
    },
    {
      "case_id": "permission-18",
      "mode": "detail"
    },
    {
      "case_id": "permission-18",
      "mode": "preview"
    },
    {
      "case_id": "permission-18",
      "mode": "retry"
    },
    {
      "case_id": "permission-19",
      "mode": "keyword"
    },
    {
      "case_id": "permission-19",
      "mode": "vector"
    },
    {
      "case_id": "permission-19",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-19",
      "mode": "ask"
    },
    {
      "case_id": "permission-19",
      "mode": "detail"
    },
    {
      "case_id": "permission-19",
      "mode": "preview"
    },
    {
      "case_id": "permission-19",
      "mode": "retry"
    },
    {
      "case_id": "permission-20",
      "mode": "keyword"
    },
    {
      "case_id": "permission-20",
      "mode": "vector"
    },
    {
      "case_id": "permission-20",
      "mode": "hybrid"
    },
    {
      "case_id": "permission-20",
      "mode": "ask"
    },
    {
      "case_id": "permission-20",
      "mode": "detail"
    },
    {
      "case_id": "permission-20",
      "mode": "preview"
    },
    {
      "case_id": "permission-20",
      "mode": "retry"
    }
  ],
  "exact_comparisons": []
}
```
