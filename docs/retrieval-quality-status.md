# 可追溯检索实施与验收状态

2026-10-14，OpenSpec `improve-traceable-retrieval-quality` 的 44/44 项任务完成。最终[验收报告](retrieval-quality-artifacts/release-acceptance.md)通过；项目运行于[本地工作区](http://localhost:5174/materials)，使用百炼 text-embedding-v4（1024 维）及 DeepSeek deepseek-flash，已启用 semantic release。

## 修复结果

- 默认返回最多 160 Unicode 字符的相关原文摘录，可展开完整证据、点击定位安全高亮；原文区间可追溯。
- PostgreSQL 词项候选、精确句子优先、scoped exact vector 与 RRF 混合检索支持改写。语义候选同时要求 chunk 与至少一个缓存句子达到 0.35 cosine，避免章节均值把无关问题填入结果。
- 问答最多 200 字，逐 claim 绑定引用；缺少所问关系、数量或条件时返回资料不足，相关定义不能代替回答。无检索证据不调用 chat。
- 完整参数保存、失败保留旧 current、重试、增量回填、generation 恢复和权限撤销已验证。

## 验收证据

| 项目 | 实际结果 | 证据 |
| --- | --- | --- |
| 真实发布集 | 原句 30/30；分散词项 30/30；vector/hybrid 改写各 40/40；无关问题 20/20 为空且无 chat 调用 | [最终报告](retrieval-quality-artifacts/release-acceptance.md) |
| 真实问答及反例 | 50 条期望状态匹配；用户确认全部支持。最终 37 条输出完全相同沿用审阅，13 条变化项再次由用户确认 | [审阅比较](retrieval-quality-artifacts/release-final-review-comparison.json)、[最终审阅](retrieval-quality-artifacts/release-final-review.completed.json) |
| PostgreSQL 回归 | 157 passed，2 skipped；另有恢复专项 14 passed | skip 为可选旧认证 cutover 与默认关闭的性能测试；性能已单独实际执行 |
| 权限 | 20 cases、140 HTTP 路径、0 泄漏；结构性 fixture 使用演示提供方 | [权限结果](retrieval-quality-artifacts/permission-results.json) |
| 真实性能 | 10,000 active chunks / 20 scopes；每路径预热 20 次后计时 100 次；DB p95 keyword 44.26ms、vector 26.30ms、hybrid 68.41ms、ask 74.52ms | [性能结果](retrieval-quality-artifacts/performance-real-sentence-gated.json) |
| 精确对照 | 50 次 scoped exact Top10 对照 100%；未启用 ANN | 同上，含硬件、provider/total 耗时及 EXPLAIN |
| 浏览器 | 真实改写→短摘录→展开→原文高亮→问答引用；资料不足、重建、retry、撤销权限；另保留受控故障场景 | [场景与截图](retrieval-quality-artifacts/browser-results.md) |
| schema 副本 | 真实 force/resume、故障保留 current、真实 retry、全部 legacy current 恢复后实际旧应用可用，hash 不变 | [迁移演练](retrieval-quality-artifacts/migration-real-v2.json) |
| 主项目部署 | 4 条材料真实重建成功，0 失败；原文、5 份物理文件、全部 31 条原有向量记录 hash 不变 | [部署核验](retrieval-quality-artifacts/deployment-verification.json) |

性能报告记录 prompt v2；最终 50 条质量/人工审阅使用 prompt v3。两者使用相同 sentence-gated-v1 检索版本；不把 v2 的 100 次 ask 性能宣称为 v3 的计时结果。最终报告明确记录该差异。

## 运行与恢复

当前 profile fingerprint：`340c5e8586b85a9473c8f940bee385108cf146f8522480315c1a98ddca5a8bbe`。阈值 0.35、batch 10、revision `local-bailian-v4-v1`。配置凭据只在忽略的 `.env`；验收报告只读挂载至 `/app/acceptance/release-acceptance.json`。

本次部署前的数据库、uploads、前后 hash 及旧 current 记录位于忽略目录 `.retrieval-backups/20261014-final-deploy`。旧 generation 保留。回滚先关闭 semantic release，再根据该目录 before.json 恢复此前完整 generation，随后回滚应用/模型配置。回到 64 维旧应用前还须选择完整 legacy generation；不能仅退镜像。

[评测手册](retrieval-quality-evaluation.md)、[服务配置](retrieval-provider-setup.md)、[索引操作](retrieval-indexing-operations.md)、[迁移回滚](retrieval-quality-migration.md)提供复现命令。未提交 Git，也未归档提案。
