# 切片与索引生命周期

上传/重建统一接受完整`chunking`对象：`strategy`（auto/custom/hierarchy）、`max_length`（custom 100–2000）、`overlap_percent`（custom 0–50）、`separators`（blank_line/line/sentence）、`preprocess`（remove_urls/remove_emails/collapse_whitespace布尔值）。auto/hierarchy使用800/80；记录归一化的所有参数与处理版本，不再只记录strategy。参数无效返回400且不替换索引。

教师可调用`POST /api/classes/{class_id}/materials/chunk-preview`，JSON含授权`subject_id`、`text`及`chunking`；或`POST /api/classes/{class_id}/materials/{id}/chunk-preview`预览现有材料。返回总数和至多10个样本，包含working范围和source mapping；预览不写库、不调用模型，学生403，越权材料/学科404。

上传multipart支持JSON字符串`chunking`，保留旧strategy/length/overlap等字段兼容。原文/文件先保存并提交，随后创建building generation。HTTP201表示source接受成功；必须另检查`indexing.status`和material的`searchable_status/latest_attempt_status`。provider失败保留原文文件、返回failed和安全错误码；旧索引重建失败继续可搜索。预处理得到空文本时记录`empty_index`，需要调整参数重试。

短时entry锁分配generation序号并记录base-current；调用provider前释放锁。chunk、sentence和向量完全就绪后再次锁entry并比较base/source hash，事务切换active/current。竞争失败返回409和`index_conflict`；不会发布部分数据。旧向量和generation保留用于恢复。

## 重试与回填

授权教师的`POST .../materials/{id}/reindex`传`{}`会重用最近attempt的完整options；传`{"chunking":{...}}`可换策略。旧custom generation缺失历史长度/重叠时要求显式参数，不冒充可重现。遇provider_unavailable检查服务端URL/key/model/revision/dimensions、网络和配额，修复后重试；页面不得显示密钥或provider响应。

服务端运维命令（在backend目录/API环境）：

```powershell
python retrieval_admin.py backfill --limit 100 --dry-run
python retrieval_admin.py backfill --limit 100
python retrieval_admin.py backfill --limit 100 --after <上批cursor>
python retrieval_admin.py backfill --limit 100 --force --profile-id <当前配置profile-id> --dry-run
python retrieval_admin.py backfill --limit 100 --force --profile-id <当前配置profile-id>
```

仅当前配置的服务可生成target profile向量；更换模型先配置服务端真实模型/revision/dimensions。候选先筛缺失、failed或不兼容，再limit并用entry ID keyset续跑。每材料独立事务，failed不计completed，失败不会回滚前项成功。dry-run输出数量和保守向量/请求估算，不写generation或请求provider；返回`has_more`决定是否继续。cursor越过的失败项在下一轮从头扫描时重试；force续跑仍应使用上一批cursor，避免重复重建ready材料。真实provider不在启动自动全量补建。

## 恢复

授权教师可`POST .../materials/{id}/restore`，JSON为`{"generation_id":旧完整generation编号}`。服务核验材料/学科、原文hash、chunk/sentence向量完整性并事务切换；学生403，越权404。building/failed、不完整或原文已变的generation无法恢复。服务端旧应用回滚前的`--legacy-only`命令及备份前置条件见`retrieval-quality-migration.md`。

旧generation暂不清理。遇冲突可刷新状态后同参数重试；异常退出留下building时也可重试或显式回填，不删除原文。真实提供方、现有 schema 副本 force/resume/回滚以及发布门槛已独立通过，主项目已完成备份与真实重建，见[当前状态](retrieval-quality-status.md)。
