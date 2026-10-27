# Spec Delta

## Purpose

提供可重复的知识库检索质量验收方法，区分代码逻辑测试与真实模型、真实 PostgreSQL 和浏览器体验验证。使用版本化语料、来源标签及固定指标检查准确召回、无关内容拒绝、原文追溯和权限隔离，让发布结论有证据可复核。

## ADDED Requirements

### Requirement: Evaluation uses a versioned labelled corpus
The evaluation suite SHALL contain at least 120 labelled questions: 30 exact phrases, 30 distributed-term queries, 40 semantic paraphrases and 20 unrelated questions. It SHALL also contain at least 20 negation/reversed-relation/number adversarial cases and 20 scope-isolation cases. Each case SHALL identify permitted scope, relevant source spans or no-evidence expectation and its category.

#### Scenario: Quality report is reproduced
- **WHEN** an evaluator reruns the same corpus version and model configuration
- **THEN** the report identifies corpus hash, model/profile, processing versions, thresholds, retrieval mode and aggregate/per-case results

### Requirement: Retrieval quality has explicit release gates
Release acceptance SHALL require exact-phrase Top-1 accuracy 100 percent, distributed-term Recall@5 at least 95 percent and semantic-paraphrase Recall@5 at least 90 percent in the appropriate modes. Hybrid unrelated-query empty-result rate SHALL be at least 95 percent. Scope leakage SHALL be zero. Recall@5 here SHALL mean the fraction of answerable cases with at least one labelled source span in the first five hits.

#### Scenario: Semantic recall passes using a real model
- **WHEN** vector and hybrid are evaluated on the 40 paraphrase cases
- **THEN** each mode passes only if at least 36 cases retrieve labelled evidence in the first five hits

#### Scenario: Unrelated questions are used to tune thresholds
- **WHEN** hybrid is evaluated on the 20 unrelated cases
- **THEN** at least 19 return empty hits and no chat call is made for empty results

### Requirement: Source and excerpt acceptance is exact
Acceptance SHALL require all returned excerpts to be at most 160 Unicode code points and equal their declared original-source substring. All supported fixture offsets and mappings SHALL be exact. Every source-opening acceptance case SHALL navigate to permitted material and highlight the correct span. Overlap fixtures SHALL return no duplicate representative evidence for the same source sentence.

#### Scenario: Excerpt and source are checked automatically
- **WHEN** the suite evaluates a hit containing emoji, trailing whitespace or preprocessing
- **THEN** substring equality, offset basis, mapping validity and excerpt length all pass without approximate text matching

### Requirement: Answer semantics are independently reviewed
Acceptance SHALL include at least 30 labelled factual/insufficient-evidence questions and all 20 adversarial cases. All accepted factual claims SHALL be supported by labelled evidence, all citations SHALL reconcile, and no reviewed claim SHALL contradict or invent a fact. A human SHALL review failed or ambiguous support judgements; an automated model grader alone SHALL NOT establish release success.

#### Scenario: Reversed relation has high vector similarity
- **WHEN** a related source is retrieved for an adversarial question
- **THEN** retrieval alone is not treated as a failure, but an answer repeating an unsupported reversed relation fails answer acceptance

### Requirement: PostgreSQL acceptance runs on an isolated real database
Database acceptance SHALL use a disposable PostgreSQL instance with the required extensions and SHALL test migration, compatible vectors, lexical ranking, atomic cutover and rollback. SQLite or mocked providers SHALL NOT substitute for PostgreSQL or real-model quality acceptance. Required suites skipped for absent configuration SHALL be reported as incomplete, not passed.

#### Scenario: Provider settings are not available
- **WHEN** only deterministic providers can run
- **THEN** unit and database structural checks can complete, but semantic and real-answer gates remain incomplete

#### Scenario: Integration database is not configured
- **WHEN** the PostgreSQL suite is skipped
- **THEN** the release report explicitly lists the missing database gate and does not claim PostgreSQL acceptance

### Requirement: Filtered approximate search is compared with exact search
On a documented fixture of at least 10000 active chunks across at least 20 class/subject scopes, acceptance SHALL compare the selected vector plan with exact scoped cosine retrieval. Approximate mode SHALL achieve at least 95 percent Recall@10 against exact results for at least 50 labelled eligible queries, after relevance filtering. Semantic corpus gates SHALL also pass for the selected production plan.

#### Scenario: Scope filters remove most approximate candidates
- **WHEN** approximate retrieval returns too few relevant authorized hits compared with exact retrieval
- **THEN** the configuration fails until scanning or the query strategy is corrected, without weakening scope predicates

### Requirement: Performance and UI acceptance are recorded
The report SHALL record hardware, versions, dataset size, database plan, warmup and per-stage timings. On the declared release reference environment, database candidate selection and ranking SHALL have p95 at most 300 ms over at least 100 warmed requests on the 10000-chunk fixture; provider/network latency SHALL be measured separately. Browser acceptance SHALL cover results, source opening, filters, retry and failure states.

#### Scenario: End-to-end latency is reported
- **WHEN** the suite measures real embedding and chat calls
- **THEN** database, embedding, answer and total durations are separated and provider latency is not hidden inside a claimed database performance pass
