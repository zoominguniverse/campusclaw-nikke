# 检索验收运行手册

## 数据与门槛

`backend/evaluation/corpus-v1.json` 是版本1.0.1语料，含30原句、30分散词项、40改写、20无关、20反例、20权限、30问答。另有8篇独立开发材料及24条开发查询，不能通过调整发布集掩盖失败。标签使用解码后原文的 Unicode code-point 半开区间 `[start,end)`。反例需要人工复核支持关系，允许正确纠错或证据不足，不能按关键词命中自动视为回答正确。

每个 `(case_id,mode)` 独立记录，case Recall@5是前5条中至少一个命中标注原文span的案例比例；不是所有相关材料的召回率。门槛采用整数计数：30/30原句Top1，29/30词项Recall5，vector和hybrid分别36/40改写Recall5，19/20无关问题hybrid为空且chat调用0。必需case缺失或skip算未完成；provider/demo、人工review、迁移、浏览器和性能证据都未完成时不允许semantic release。

## 本地单元与基线

在 backend 目录运行：

```powershell
python -m pytest tests/test_quality_evaluation.py -q -p no:cacheprovider
python -m pytest tests/test_retrieval_quality_regressions.py -q -p no:cacheprovider
```

初始旧行为见 `retrieval-quality-baseline.md`。回归用例在修复前故意失败，不能计为质量通过。

## 一次性 PostgreSQL

在项目根目录执行；独立compose项目、tmpfs、无host端口、无生产volume，不加载业务.env的数据库地址：

```powershell
docker compose -p campusclaw-quality -f docker-compose.retrieval-test.yml up -d --wait quality-postgres
docker compose -p campusclaw-quality -f docker-compose.retrieval-test.yml run --build --rm quality-tests
docker compose -p campusclaw-quality -f docker-compose.retrieval-test.yml down
```

fixture在每次运行创建自己的schema/演示资料，测试结束清理。仅允许数据库名 `quality_*` 且设置 `QUALITY_DISPOSABLE_DATABASE=true` 的目标。常规pytest缺少`POSTGRES_INTEGRATION_URL`会skip：这表示PostgreSQL验收未完成，不能视为发布通过。

## 报告

运行器输出格式：`{"metadata": {...}, "results": [{"case_id":"...", "mode":"keyword", "status":"ok", "hits":[{"material":"release-01", "chunk_id":1, "source_spans":[{"start":8,"end":26}]}], "chat_calls":0, "latency_ms":{"db":12,"embedding":100,"chat":0,"total":115}}]}`。

metadata只存provider、model、revision、dimensions、硬件与版本等非秘密信息。禁止把配置字典或请求Authorization头写入报告。ask结果必须经逐claim人工review；报告还要求审阅人、每条claim的说明及整体响应审阅，单独填写`human_review=supported`、`unsupported_claims=0`不足以通过。权限路径必须记录`leak_count=0`；不能把没有执行的路径默认算0。

在 backend 目录执行：

```powershell
python -m evaluation.report --results <results.json> --output <report-path> --split release
```

同时输出JSON/Markdown，退出2表示未达到完整发布门槛。报告记录passed/total/required、逐case失败和未完成列表、各stage p95以及exact Top10对照；预设数据测试仅验证指标计算，不能用于模型验收。

执行框架会在明确标为一次性的数据库中幂等装载上述语料、按scope检索，并产出`.results.json`和报告。运行示例（容器内`/tmp`报告为临时文件，可按需要增加工作区目录bind mount保存）：

```powershell
docker compose -p campusclaw-quality -f docker-compose.retrieval-test.yml run --build --rm --entrypoint python quality-tests -m evaluation.run --split release --output /quality-results/release-demo
```

目前测试服务刻意固定为demo；此命令的真实vector/hybrid/ask记录为`incomplete`，退出2。真实验收须用服务端环境覆盖真实provider及已冻结profile；不要使用生产数据库或把密钥作为可见的命令参数。

## 当前真实服务状态

2026-10-14：百炼 text-embedding-v4 / 1024维与 DeepSeek deepseek-flash 已完成真实验收。最终冻结发布集、50 条人工审阅、真实一万片性能、浏览器及现有 schema 副本回滚全部通过；主项目已备份并完成 4 条真实重建。见[最终报告](retrieval-quality-artifacts/release-acceptance.md)与[当前状态](retrieval-quality-status.md)。

## 服务契约、逐claim审阅与真实性能

根目录`.env`配置方法见[服务接入说明](retrieval-provider-setup.md)。先执行受控请求，不装载业务资料或写入业务库：

```powershell
docker compose -p campusclaw-quality-real -f docker-compose.retrieval-test.yml -f docker-compose.retrieval-real.yml run --build --rm --entrypoint python quality-tests -m evaluation.preflight --output /quality-results/provider-preflight.json
```

检查两个embedding文本的批量响应与一个查询响应、维度/finite/nonzero及chat结构化引用。此命令即使契约通过也不代表语义质量通过。演示或配置缺失返回未完成；错误记录不包含服务响应正文或密钥。旧[演示契约报告](retrieval-quality-artifacts/provider-preflight.json)保留用于工具对照；实际通过证据以[最终验收报告](retrieval-quality-artifacts/release-acceptance.md)为准。

真实发布集完成后导出待人工审阅文件：

```powershell
docker compose -p campusclaw-quality-real -f docker-compose.retrieval-test.yml -f docker-compose.retrieval-real.yml run --rm --entrypoint python quality-tests -m evaluation.review --results /quality-results/release-real.results.json --output /quality-results/release-real-review.pending.json
```

复制文件为`release-real-review.completed.json`，填写`reviewer`，逐条检查claim与quote、原文区间、reference_fact的支持关系，并填写每条`claim_reviews`和整体`response_review`的status/note。status可为pending/supported/unsupported/ambiguous，已审阅项必须写说明；资料不足也需要整体审阅。不要修改绑定的查询、回答、引用或hash。模型/profile/回答变化后重新导出审阅，不复用旧结论。演示[50条待审阅清单](retrieval-quality-artifacts/release-demo-review.pending.json)仅展示格式。

```powershell
docker compose -p campusclaw-quality-real -f docker-compose.retrieval-test.yml -f docker-compose.retrieval-real.yml run --rm --entrypoint python quality-tests -m evaluation.review --results /quality-results/release-real.results.json --reviews /quality-results/release-real-review.completed.json --output /quality-results/release-real.reviewed.results.json
docker compose -p campusclaw-quality-real -f docker-compose.retrieval-test.yml -f docker-compose.retrieval-real.yml run --rm --entrypoint python quality-tests -m evaluation.report --results /quality-results/release-real.reviewed.results.json --output /quality-results/release-real-reviewed --split release
```

真实性能使用专属一次性项目，装载20 scopes/10,000片；会调用真实embedding/chat并产生服务费用。不要与语料评测或业务库共用数据库。工具使用当前配置维度及同一次查询向量做50次精确Top10对照，记录每路径20次预热后100次请求、DB/provider/total p95、硬件与EXPLAIN。未启用ANN；性能通过仍不能单独启用semantic release。

```powershell
docker compose -p campusclaw-quality-performance -f docker-compose.retrieval-test.yml -f docker-compose.retrieval-real.yml run --build --rm --entrypoint python quality-tests -m evaluation.performance --output /quality-results/performance-real.json
```

重新运行前用相同project/files执行`down`清理该一次性tmpfs数据库。禁止对业务项目执行此清理。非真实provider默认退出未完成且不装载性能fixture；`--allow-demo`仅用于工具回归。
