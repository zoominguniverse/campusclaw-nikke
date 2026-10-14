# PostgreSQL检索数据契约升级

## 已验证的数据层

在独立`quality_test`库运行12项契约/评测测试通过（2026-10-13）。测试将临时库检索表恢复为旧列结构，再执行增量迁移两次；确认原文、测试原文件hash、旧64维向量不变。新表允许64维与8维测试profile共存；错向量长度、profile/dimensions不一致、重复(chunk,profile)、错误句子generation和两个current都由PostgreSQL拒绝。8维profile仅为结构fixture，不是已选择的真实模型。

旧`knowledge_chunks.embedding VECTOR(64)`保留。新chunk/sentence向量为无typmod的VECTOR，维度由profile复合外键和`vector_dims`check共同约束。新增mapping、heading、lexical、active和generation版本字段；旧记录明确标为legacy，不推测真实模型或精确来源。

词项GIN在10000条候选fixture上的`EXPLAIN (ANALYZE, BUFFERS)`实际使用`ix_chunks_active_terms`。这仅验证索引契约，不代表第7组性能或真实语义门槛通过。生产策略仍为scoped exact；可选HNSW工具只接受已注册正整数profile及1–2000维，超出范围必须用精确方案。

## 升级前置条件与命令

先备份数据库和uploads，记录文件hash与current generation。在现有schema的隔离副本重复运行：

```powershell
docker compose -p campusclaw-quality -f docker-compose.retrieval-test.yml run --build --rm quality-tests
```

应用增量入口仍是`python init_db.py`。启动仅允许本地demo补建；配置真实embedding不会在启动自动触发付费全量重建。force/resume与恢复工具已通过结构fixture测试；真实 profile 在当前 schema 隔离副本的完整演练已通过，见[真实演练报告](retrieval-quality-artifacts/migration-real-v2.json)。

若旧库存在双current，迁移会停下并要求人工核对完整generation，不删除或自动猜选记录。可在数据库副本诊断：

```sql
SELECT knowledge_entry_id, array_agg(id ORDER BY generation)
FROM knowledge_index_generations
WHERE is_current
GROUP BY knowledge_entry_id HAVING count(*) > 1;
```

修复后再运行迁移。DDL为可重试增量；未完成步骤不代表已经可检索。大库索引创建须在维护窗口单独评估锁与空间，本项目副本演练已通过；更大业务库仍须按实际规模评估。

## 配置与回滚边界

新增`EMBEDDING_REVISION`、batch/timeout、最低0.35向量阈值和`SEMANTIC_RELEASE`，真实服务必须显式记录revision。能力接口受Bearer和学科scope保护，只返回非秘密模型标签。legacy结果无精确source spans；材料DTO分别返回source-save、searchable、latest attempt和compatibility。

`SEMANTIC_RELEASE=false`为默认。启用需要真实embedding/chat及与profile和chat模型匹配的通过报告，不能靠演示测试宣称质量通过。正式部署在所有任务验收后进行。

回滚前必须关semantic release，重新激活此前完整legacy generation，再回滚应用与配置；保留所有新增表和向量。仅将新应用退回旧镜像而不恢复旧64维current，会使旧检索不可用。

恢复命令如下（先在隔离副本执行，并使用备份记录的真实entry/generation ID）：

```powershell
python retrieval_admin.py restore --entry-id <entry-id> --generation-id <old-generation-id> --legacy-only --dry-run
python retrieval_admin.py restore --entry-id <entry-id> --generation-id <old-generation-id> --legacy-only
```

在backend/API容器服务端环境运行；工具验证原文hash、完整旧64维向量并事务切换，不删除原始资料。`dry-run`不改变current。现有业务 schema 隔离副本已实际完成真实 force/resume、失败保留 current、retry、全部 legacy 恢复及 Git HEAD 旧应用 keyword/vector/hybrid 核验。主项目已备份并真实重建 4 条材料；本次 5 份文件与 31 条原有向量记录、全部原文 hash 不变，见[部署核验](retrieval-quality-artifacts/deployment-verification.json)。本地部署不等同其他生产环境上线。
