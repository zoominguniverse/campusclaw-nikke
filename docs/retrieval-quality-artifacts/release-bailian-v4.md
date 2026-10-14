# Retrieval evaluation

Corpus: 1.0.1; split: release

Semantic release passed: False

| Category | Mode | Metric | Passed / total | Required | Incomplete |
| --- | --- | --- | --- | --- | --- |
| exact | keyword | top1 | 30/30 | 30 | 0 |

Failures exact/keyword: none; incomplete: none

| distributed | keyword | recall5 | 30/30 | 29 | 0 |

Failures distributed/keyword: none; incomplete: none

| paraphrase | vector | recall5 | 40/40 | 36 | 0 |

Failures paraphrase/vector: none; incomplete: none

| paraphrase | hybrid | recall5 | 40/40 | 36 | 0 |

Failures paraphrase/hybrid: none; incomplete: none

| unrelated | hybrid | empty | 19/20 | 19 | 0 |

Failures unrelated/hybrid: unrelated-11; incomplete: none


```json
{
  "metadata": {
    "embedding_provider": "openai-compatible",
    "embedding_model": "text-embedding-v4",
    "embedding_revision": "local-bailian-v4-v1",
    "dimensions": 1024,
    "chat_provider": "deterministic",
    "chat_model": "campusclaw-deterministic",
    "hardware": "Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.41",
    "structural_browser_performance_gates": "incomplete",
    "profile_fingerprint": "340c5e8586b85a9473c8f940bee385108cf146f8522480315c1a98ddca5a8bbe",
    "processing_version": "source-map-v1;chunker-v2;jieba-0.42.1/default-dict+terms-v2",
    "vector_threshold": 0.35,
    "corpus_hash": "0f03c5350422abb8df916827d5a466a4e9961f6683c1b81c3f7138ae5851ce19"
  },
  "stage_latency": {
    "db": {
      "count": 360,
      "p95_ms": 7.894550013588741
    },
    "embedding": {
      "count": 360,
      "p95_ms": 166.52223100390984
    },
    "chat": {
      "count": 360,
      "p95_ms": 0.0
    },
    "total": {
      "count": 360,
      "p95_ms": 180.35292899730848
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
