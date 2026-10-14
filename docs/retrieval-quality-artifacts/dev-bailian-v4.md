# Retrieval evaluation

Corpus: 1.0.1; split: dev

Semantic release passed: False

| Category | Mode | Metric | Passed / total | Required | Incomplete |
| --- | --- | --- | --- | --- | --- |
| exact | keyword | top1 | 8/8 | 8 | 0 |

Failures exact/keyword: none; incomplete: none

| distributed | keyword | recall5 | 8/8 | 8 | 0 |

Failures distributed/keyword: none; incomplete: none

| paraphrase | vector | recall5 | 8/8 | 8 | 0 |

Failures paraphrase/vector: none; incomplete: none

| paraphrase | hybrid | recall5 | 8/8 | 8 | 0 |

Failures paraphrase/hybrid: none; incomplete: none

| unrelated | hybrid | empty | 0/0 | 0 | 0 |

Failures unrelated/hybrid: none; incomplete: none


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
      "count": 72,
      "p95_ms": 7.548805020633154
    },
    "embedding": {
      "count": 72,
      "p95_ms": 160.8735570043791
    },
    "chat": {
      "count": 72,
      "p95_ms": 0.0
    },
    "total": {
      "count": 72,
      "p95_ms": 172.52457599533955
    }
  },
  "required_reviews_incomplete": [],
  "exact_comparisons": []
}
```
