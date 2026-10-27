# Design

## Context

动机见 proposal.md。已检查 Flask 检索、切分、提供方、索引、材料接口、PostgreSQL bootstrap、前端及测试，确认：

- `_keyword_ranked` 用整个查询的 ILIKE 筛选，pg_trgm similarity 只参与排序；没有中文词项召回。
- `_hit_payload` 返回整段 `excerpt`；页面不显示切片位置、不链接来源，检索页的学科筛选实际继承隐藏的材料页选择。
- 本地配置使用 deterministic；该提供方以字符哈希计数。反转“力/质量正反比”的句子仍可得到约 1.0 的余弦相似度。
- `KnowledgeChunk.embedding` 和应用启动均固定 64 维，generation 未记录模型身份或完整切分参数。
- hierarchy 丢弃首标题前正文；strip 未修正尾偏移；重复补标题破坏原文区间；分隔符实际按最靠后的位置选择而非段落优先。
- 索引失败会返回 failed，但页面只检查 HTTP；材料列表只看 current，失败尝试被隐藏。backfill 在过滤前 limit 100，并把返回 failed 的调用计为 completed。
- 原有 generation 切换保护是合适基础，但缺少 current 唯一约束与并发控制。retired generation 的 ready chunks 仍进入 ready 部分索引。
- 原问答仅校验方括号编号；演示回答截取切片开头。已有测试主要覆盖结构与权限，未证明真实语义质量。
- 2026-10-13 已启动项目，网页端口 5174，后端和数据库健康；本提案不更改运行配置、数据或服务。

主规约清单为空，历史能力留在完成但未归档变更中。本次沿用能力路径建立 ADDED 基线；以后归档时不能将旧变更中冲突的 requirement 覆盖回来，应先按本变更最终语义协调历史归档。此次不自动处理归档。

## Goals / Non-Goals

**Goals:**

- 将字面召回、语义召回、摘录展示、生成回答、来源定位拆成可独立验证的契约。
- 以 PostgreSQL 内的版本化增量结构支持模型维度变化和回滚，不丢文件和 `body_text`。
- 先建立回归案例和评测标签，再实施修复；演示测试与真实质量结果分别报告。
- 保留 `/api/classes/<class_id>/knowledge/{retrieve,ask}` 和材料端点，新增 DTO 字段；前后端同步升级摘录语义。

**Non-Goals:**

- 不迁移到 MySQL/Qdrant，不引入 LangChain、对话工具调用、流式输出或独立任务队列。
- 不将关键词模式变成模型改写通道，不把余弦分数或 RRF 分数表示成可信概率。
- 不承诺用引用字符串校验解决所有事实正确性问题；结构校验和语义验收各自承担不同责任。
- 第一版不接独立收费 reranker 服务；先用真实模型、词项召回、窗口证据选择和去重达到门槛。未达标则继续优化、换合格 profile，不能宣告验收完成。

## Decisions

### 1. 冻结质量基线与模型身份

实现前创建公开或项目内人工构造语料，至少 120 个检索问题、20 个关系/否定/数值反例和20个范围案例，以及30个问答案例。每项包含 scope、预期 material/source span、分类、是否可回答和参考事实。固定一个发布保留集，模型/阈值选择使用独立开发集，不能只调到发布集通过。

基线保存现有短句返回长片段、多关键词空结果、反向关系哈希向量相同、前言遗漏、偏移不等、失败计数错误等回归。真实模型由服务端 OpenAI-compatible 接口接入，配置明确 model revision（服务仅有可变别名时由部署维护 revision 标签）、dimensions 和处理版本。不预设尚未提供的供应商、模型或密钥。

接受真实向量前校验列表长度、数值类型、finite/nonzero；query 同样校验。deterministic 只用于本地结构测试，并通过受保护的 capability DTO 提供 `demo_mode` 和 `semantic_ready`。semantic release 配置拒绝 deterministic；开发演示允许保留但显示提示。chat 和 embedding 配置独立。

选择理由：接入代码已经存在，缺的是兼容契约和真实质量验证。仅换环境变量会混用向量或触发64维启动失败；新平台不会自动修复这些问题。

### 2. 增量向量存储支持多维 profile

新增 `embedding_profiles`（provider/model/revision/dimensions/processing_version/fingerprint），fingerprint 唯一；generation 记录 profile_id、chunker_version、tokenizer_version、normalized_options、source_hash 和 latest attempt error code。旧 generation 标为 legacy/demo，不推测其来源模型。

新增 `knowledge_embeddings`：chunk_id、profile_id、dimensions、embedding（无 typmod 的 PostgreSQL VECTOR）、is_active、state。建立 `(chunk_id, profile_id)` 唯一约束、`CHECK(vector_dims(embedding)=dimensions)` 和指向 profile 的 `(profile_id, dimensions)` 复合外键；finite/zero 在服务边界检查。保留旧 `knowledge_chunks.embedding VECTOR(64)` 不改写，支持回滚期间读取。

chunk增加显式 `searchable_active`，由generation切换事务维护，供仅current ready的词项部分索引使用，避免跨表谓词无法用于部分索引。新增 `knowledge_chunk_sentences`（chunk/generation、句序号、working/source ranges、正文）及 `knowledge_sentence_embeddings`（sentence/profile、dimensions、vector），使用与chunk向量一致的维度约束和profile外键。同原文句可用source_hash+span+profile缓存计算，但引用始终绑定当前授权generation。

初期每个部署有一个 active semantic profile。小规模查询优先使用按授权范围和profile筛选后的精确余弦查询。需要 HNSW 时，迁移工具为已注册且支持的维度 D 创建表达式索引：`(embedding::vector(D)) vector_cosine_ops`，部分条件限定具体 profile、ready、is_active；查询使用相同 cast 与 predicate。D/profile ID 只来自校验过的数值元数据，不拼接用户字符串。超过已部署扩展索引维度限制时保留精确检索，不能冒充已支持 HNSW。

current generation 使用部分唯一索引 `(knowledge_entry_id) WHERE is_current`，数据库和DTO都携带generation ID。旧记录在激活新generation时退出active embedding/lexical索引，历史正文与向量保留以便回滚。API针对检索范围中的不兼容索引报告 `reindex_required`；keyword仍可使用完整current正文，vector/hybrid不得将异构向量比较或将未完成迁移说成无命中。

先计算有效授权scope并处理空scope，再查询兼容状态；请求未授权subject时直接返回空结果，不能通过profile诊断泄漏其他scope的索引状态。索引compatibility包括句子定位数据、chunker/tokenizer版本，而不仅是向量维度。

选择理由：直接 ALTER 旧 VECTOR(64) 会破坏回滚，并不能在迁移期容纳两个维度；单一无维度列加受约束 profile 及表达式索引保持一个 PostgreSQL部署。数据清理不是本次自动操作。

### 3. 原文、工作文本和标题上下文分离

定位原文定义为材料预览返回的 Unicode `knowledge_entries.body_text`，不是原始文件字节下标。文件下载保持原字节；既有解码/NUL处理规则不变。所有偏移使用 Unicode code point 的 `[start,end)`。

chunk_text 始终是待切分工作文本中的真实连续子串，trim 同时调整两端；chapter标题保留在原来位置，在子块需要标题增强时另存 heading_context，仅组合为 embedding_input，不能修改 chunk_text。首标题前内容独立切块。边界策略按段落、换行、句末依次选择合法断点，保留800/80自动默认与自定义范围。

预处理输出工作文本及映射 segments，每段记录 working/source范围和操作类型（保留、空白折叠）；删URL/邮箱产生工作位置间断。generation保存完整normalized options。chunk持有相关source spans与映射。映射只追踪真实来源，合成标题不能产生伪span。来源定位高亮多个span，绝不把预处理offset直接当原文offset。

必须满足：无移除预处理时，非空白原文字符覆盖率100%；`working[start:end]==chunk_text`；映射source范围有序、界内。新的quote/excerpt从原文切取，展示文本不含合成标题。旧块未重建前DTO将不可靠映射标为legacy，提供打开原文但不假装精确高亮。

### 4. 中文词项召回留在 PostgreSQL

使用版本固定的中文分词器（实施采用 jieba 并固定依赖/词典版本），源文和query共享规则；中英文大小写与空白规范化只用于索引，不改变原文。空格分隔的明确词项先保留，中文连续查询再分词；数字、否定词、专业名词不作为停用词移除，未知长词采用受控二字词项补充。停用词表与覆盖规则版本化。

新增词项检索字段：将预分词后的词串生成 `to_tsvector('simple', ...)`，建立仅current ready块的GIN索引；保留pg_trgm供转义后的精确短语检索。词项召回以OR取候选，再按有效词覆盖率过滤：一个有效词必须命中；n>=2要求至少max(2,ceil(0.6*n))个词命中。精确短语匹配优先，然后coverage、`ts_rank_cd`、稳定ID。候选最多100条；keyword不访问任何模型。

这是一条可测初始规则，开发集调优后冻结配置，最终是否可发布由保留集门槛决定。查询输入、limit和subject类型验证返回400；SQL参数化，LIKE `%/_/escape`字面转义，空有效词返回空。不直接对未分词中文使用默认全文配置，不把LIKE相似度声称为语义召回。

### 5. 语义召回、过滤、融合与去重

向量只读取current/ready、授权class/subject和匹配profile的数据；始终保留最低cosine 0.35，新增模型profile相关的更严格相关性门槛可以在开发集校准，不能低于该最低值。RRF k=60不变，两路先独立筛选再融合；保留分路命中和原始分数供授权调试，不向页面声称置信度百分比。

精确短语在keyword内优先，不保证它在hybrid中绝对盖过双路证据。融合后按matched source spans进行重叠去重：相同material/generation中相同命中句的代表项只保留一次；采用显式来源span/匹配证据键，不用只按material去重。两个不同有用句子仍可返回。问答最多取4个非重复证据。

pgvector HNSW过滤行为必须与 scoped精确查询对比。对小scope采用精确查询；对大scope仅在实测合格后启用支持版本的iterative scan及ef_search，或维持精确方案。测试fixture使查询自然走候选索引，不以存在索引就算验收；保留 `EXPLAIN (ANALYZE, BUFFERS)`。不得为了命中率减少class/subject/generation/profile过滤。

语义相似表示话题相关，不能保证两个陈述等价。相反关系的资料可以作为纠错证据；只有回答复述错误关系才构成对应语义问答失败，不能简单规定所有反向提问必须无检索结果。

### 6. 短摘录、来源接口和UI

关键词/精确查询用匹配词源span挑选句子窗口；vector/hybrid无词面命中时，对候选chunk内部句子使用同profile嵌入做有界批量评分，重建时缓存句子向量，不在每次搜索为整篇材料逐句调用模型。句子结果仅用于证据窗口选择、不能引入候选之外或越权的证据。embedding provider 增加batch能力和逐项输出验证，句子元数据/向量也归属generation/profile。

以最佳匹配句所在原文位置选一个最多160 code point的连续raw source窗口，尽量句边界；超长句保留最相关部分。原文含被移除的长URL时优先围绕有效source span，不试图把被删除后的不连续文本拼成原文。省略号放在UI，不放进excerpt。`chunk_text`保持完整正文。

DTO保留已有字段，增加 `generation_id`、`source_hash`、`source_spans`、`excerpt_start_offset`、`excerpt_end_offset`、`excerpt_truncated`、`offset_unit=unicode_code_point`、`provenance_version`。旧start/end仍指chunk工作文本，不换成excerpt范围；模型身份仅返回必要的非秘密标签。新增受保护的chunk evidence detail可承载完整正文、heading context和映射，复用材料授权，返回404掩盖不存在/越权。

页面默认显示短摘录、学科、标题、切片编号、原文区间、展开和打开原文。source preview按code points映射到DOM：使用 `Array.from(text)` 或对应code-point到UTF-16转换，文本节点加mark，禁止innerHTML拼原文。重新打开时校验source_hash/权限，资料已变或失效提示重新检索。学科选择在检索/问答视图内可见且同步，不继承不可见筛选。失败清理旧hits/answer/citations。

上传/重建增加策略参数、预览（最多10块但返回总数，不写库不调用模型）、状态与retry。材料DTO提供 `searchable_status`、`latest_attempt_status`、`index_compatibility` 和safe error code；初始失败显示“材料已保存，索引失败”，重建失败显示“保留旧索引，本次失败”。

### 7. 索引事务、补建与恢复

文件与source保存完成后提交，随后构建generation；provider失败不会回滚已经接受的source。创建attempt时短时锁定entry分配generation序号和base_current_id，外部调用不长期持有该锁；building块不可搜索。成功publish时再次锁定entry，比较base_current_id并在一个事务中退休旧generation/active向量、激活新generation/active向量。冲突返回409或序列化结果；部分唯一索引最终防止两个current。失败记录commit且保留旧current。

backfill查询先筛缺失/failed/incompatible（force覆盖ready），按entry ID keyset分页；每材料独立事务/错误记录，批次输出completed/failed/skipped/cursor及sanitized原因。支持dry-run、resume、force、target profile，不会因前100项已有索引而停止扫描。返回failed和异常均计失败，失败不回滚前项成功。retry按已保存策略重建，不未经用户操作改回默认。启动不自动进行付费全量重建。

### 8. 回答输出与校验

真实chat接收最多4个合格证据、subject/material、原文span和有限history；强制结构化返回 `status=answered|insufficient`、claims列表、每claim的evidence index与exact quote。服务端从结构化claims生成最多200 code point正文和 `[n]`，核对quote membership、源映射、引用范围和每claim都有引用；仅返回实际使用来源，并重排编号。越界、篡改quote或长度错误至多重试一次，仍失败502，不截断事实或补假编号。

无hits完全跳过chat；有hits但无足够支持可返回“资料不足以回答该问题”且无引用。模型故障503，不冒充无资料。演示chat明确标识，也使用相关摘录而不是固定chunk开头。

quote membership不能证明entailment。语义门槛依靠有标签问答集和人工复核，特别是反向关系、数字、否定和缺信息；不在代码中宣称字符串验证能证明所有事实正确。

### 9. 实施顺序和阶段出口

| 阶段 | 依赖与工作 | 出口 |
| --- | --- | --- |
| 0 基线 | 故障回归、标签语料、隔离数据库、真实provider/profile选择 | 不再缺验收定义；记录demo基线，不宣称质量通过 |
| 1 数据契约 | 增量schema、profile/映射/词项字段、兼容DTO、current约束 | 旧库升级/重复升级/回滚演练通过，source/file不变 |
| 2 切片与生命周期 | source覆盖、映射、参数、attempt、并发发布、分页重建 | 所有位置与故障回归通过，>100条任务无遗漏 |
| 3 两路召回 | 中文keyword、真实vector、独立过滤、RRF、去重、句子向量 | 原句/词项测试通过，真实改写评测可运行 |
| 4 用户体验 | 160字excerpt、展开、定位、可见筛选、配置/状态/retry | 浏览器完成检索到原文闭环和失败反馈 |
| 5 简短问答 | structured claims、quote/citation、insufficient和demo区分 | 固定问答集、反例、长度、引用与权限通过 |
| 6 质量与上线 | 真实PostgreSQL/模型保留集、HNSW对照、性能、迁移/回滚 | 所有发布门槛通过后才启用semantic release |

阶段1–5可以在无真实凭据时完成结构实现与fake测试，但阶段3真实评测和阶段6上线门槛不能勾为完成。实施任务逐项验收，不把schema status=done当作代码实现完成。

### 10. 验收矩阵

指标定义及最低样本量见 `specs/retrieval-quality-evaluation/spec.md`。Top-1/Recall按原文span标签判定，不能仅按material相同；重复窗口不能增加正确次数。这里的Recall@5为“至少一个正确span在前5的用例比例”，不是所有相关文档召回比例。

| 指标 | 发布门槛 | 检查层 |
| --- | --- | --- |
| 原句 | keyword Top-1 100%（30例） | 真实PostgreSQL |
| 分散词项 | keyword Recall@5 >=95%（30例，即至少29例） | 真实PostgreSQL |
| 同义改写 | vector和hybrid各Recall@5 >=90%（各40例，至少36例） | 真实provider，保留集 |
| 无关问题 | hybrid空结果 >=95%（20例，至少19例），空结果chat调用0 | 真实provider+调用计数 |
| 权限 | 20例跨班/未分配学科泄漏0 | keyword/vector/hybrid/ask/detail/preview |
| 原文与摘录 | 所有fixture映射和excerpt substring100%，<=160，来源打开全部正确 | 单元+PostgreSQL+浏览器 |
| 索引恢复 | 初始失败、重建失败、并发、>100条/resume/force全部通过 | PostgreSQL故障注入 |
| 问答 | >=30例+20反例中无unsupported factual claim，引用合法100%，正文<=200 | 真实chat+人工复核 |
| ANN | 使用HNSW时50查询Recall@10 >=95%对照scoped exact | >=10000 active chunks/20 scopes |
| 数据库性能 | 同fixture至少100次预热后请求DB部分p95<=300ms | 声明硬件/版本，另报provider延迟 |

报告包含profile、版本、数据hash、阈值、硬件、每类分数、每case失败原因、执行计划和latency分解。配置缺失或必需套件skip只能标为未完成。

## Risks / Trade-offs

- [Risk] 模型供应方只提供可变model alias → 记录显式revision标签；版本变动走profile重建和保留集重验。
- [Risk] 新向量/句子向量及mapping增加存储与调用费用 → 有界批量嵌入、缓存、dry-run预估数量；暂不自动删除旧profile。
- [Risk] 字面coverage会漏未知词或误召回常见词 → 固定词典和停用表，保留精确phrase及真实semantic双路，使用独立开发集调优。
- [Risk] HNSW多条件过滤损失召回或表达式索引没有命中 → 优先scoped exact，小scope精确，大scope实测启用ANN；保存计划和对照报告。
- [Risk] 部分材料迁移时有未兼容generation → keyword可用，semantic显示reindex-required；不静默忽略旧材料而声称正常无证据。
- [Risk] quote合法但claim不成立 → 结构校验与语义人工复核分开，不用LLM grader的单一结论作为发布依据。
- [Risk] 旧变更后归档覆盖新行为 → 本次不归档旧变更，归档协调记录冲突能力和新契约优先级。

## Migration Plan

1. 在一次性数据库复现旧schema并备份现有数据库/上传文件；记录current generation、source hash、配置与扩展版本。规划阶段不执行这些操作。
2. 在隔离库执行可重复的增量migration并验证旧API/原文访问；旧64维列、旧generation和向量保留。大数据索引创建采用可重试的独立migration步骤，不假设create_all能修改现有结构。
3. 部署兼容读路径与新的UI/DTO，保持semantic release禁用或明确demo；profile不匹配时提供reindex-required，不触发启动付费回填。
4. 用真实provider运行受控样本并通过维度/模型契约；dry-run计算待重建项和调用量，执行有界force/resume重建。重建以material为单位发布，持续检查失败计数与source hash。
5. 完成全部授权材料兼容性检查及阶段6门槛，才启用semantic release。现有模式参数和无证据/503边界保留。
6. 回滚时先停semantic release；在事务中重新激活此前完整legacy generation及对应active向量，再回滚API/UI和配置。新schema/新向量暂留，禁止回滚脚本删除source/file。若旧generation无法恢复，使用备份恢复；记录影响材料，不能将new chunk空旧embedding交给旧代码假称可用。

## Open Questions

- 实施时提供方的base URL、凭据、具体中文embedding/chat模型及revision标签尚未提供；不影响规约与profile架构，但真实质量验收必须取得配置。先以选定profile通过保留集再冻结模型，不在提案中虚构选择或结果。
- 发布参考硬件配置与实际语料规模在性能任务开始前记录；300ms门槛保持不变，不以换机器或缺少provider为由把未测标成通过。
