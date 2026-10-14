# Tasks

按 1→2→3→4→5→6→7 的依赖顺序实施，对应 design 的阶段0–6。每项包含本项验证；第7组只承担跨模块集成与发布门槛。所有checkbox代表未实施工作，不代表本次propose应执行的动作。真实provider未配置时可以完成独立结构工作，但不能将真实模型验收标为完成。

## 1. 故障基线与验收数据（阶段0）

- [x] 1.1 将整段excerpt、多词空结果、反向关系哈希等价、Markdown前言遗漏、trim/标题偏移和failed统计错误转为明确的回归用例；验证每项在旧实现失败或准确记录旧行为，在修复后有明确预期。
- [x] 1.2 建立版本化语料和标签：30原句、30分散关键词、40改写、20无关、20反例、20权限、30问答；验证category数量、scope和source span标签合法，并区分开发集与发布保留集。
- [x] 1.3 增加评测执行与JSON/Markdown报告框架，定义Top-1、case Recall@5、exact对照Recall@10、空结果率与stage latency；用预设结果验证指标计算、整数通过数量和失败项列表正确。
- [x] 1.4 建立一次性PostgreSQL测试目标和fixture装载方式，不复用运行中的项目数据库；验证vector/pg_trgm可用、fixture可复现、测试缺配置被标为未完成，并在本组文档写出运行命令。
- [x] 1.5 记录将使用的真实embedding/chat endpoint、非秘密model/revision/dimensions及参考硬件；验证受控provider响应契约，凭据只在服务端。配置缺失时明确标记真实评测未完成，不写虚构模型或通过结果。

## 2. PostgreSQL兼容数据契约（阶段1；依赖1.1、1.4）

- [x] 2.1 增加embedding_profiles及generation的profile、完整options、处理版本、source_hash和attempt错误元数据；对旧库运行增量migration两次，验证幂等、原文/文件hash和旧64维数据不变。
- [x] 2.2 增加多维knowledge_embeddings及profile/维度外键、向量维度check和唯一键；验证64维与另一测试维度共存、错维度被拒绝且旧列不被改写。
- [x] 2.3 增加原文映射、heading context、词项检索字段、句子元数据/向量存储和显式active检索状态；验证字段迁移、scope关联和新旧generation读取兼容。
- [x] 2.4 增加current generation部分唯一约束及active/profile候选索引；验证双current被数据库拒绝、profile索引维度安全校验和词项GIN实际查询计划，并记录旧库脏状态的修复前置条件。
- [x] 2.5 增加必要的capability、provenance、index状态DTO及服务端配置验证；测试无密钥泄漏、legacy无法伪装精确来源、语义release拒绝demo及API字段兼容，并同步说明迁移/回滚命令。

## 3. 切片完整性与可恢复索引（阶段2；依赖2）

- [x] 3.1 修复Markdown前言覆盖、标题上下文分离和段落/换行/句末断点优先级；验证长章节、无标题文本、短段落和重叠窗口的非空白覆盖100%。
- [x] 3.2 修复首尾trim偏移并实现预处理映射与Unicode code-point区间；用emoji、CRLF、URL/邮箱删除、空白折叠fixture验证working slice相等、source spans有序且界内。
- [x] 3.3 统一上传/重建的完整options解析、保存和纯切片预览接口；验证custom所有参数、生效结果、无效输入400、预览不写库不调用provider及教师学科授权。
- [x] 3.4 将已接受source/file保存与provider索引失败隔离，记录latest attempt；故障注入验证初始失败保留原文文件、部分块不可检索、返回真实failed状态，并记录新响应契约。
- [x] 3.5 实现短时entry锁、generation序号分配、base-current比较和原子active/current切换；真实PostgreSQL并发与中途失败测试验证一个current、旧索引保留、冲突409或安全串行。
- [x] 3.6 修复backfill筛选前limit、错误统计和跨材料事务，增加dry-run/keyset/resume/force/profile参数；用至少205条含ready/failed/缺失项的fixture验证后续材料全部被扫描、failed不计completed、resume不重复发布。
- [x] 3.7 增加同策略retry及可恢复generation操作；验证重试使用已保存options、旧generation可事务恢复、未授权用户不可操作；在本组文档给出故障排查和恢复步骤。

## 4. 中文与真实语义召回（阶段3；依赖3）

- [x] 4.1 引入固定版本中文分词与词典、受控未知词补充和停用词规则；用中英混排、数字、否定、空格词项和专业词fixture验证一致分词，并记录tokenizer版本变更需要重建。
- [x] 4.2 实现精确短语优先、词项OR候选、coverage过滤和ts_rank_cd排序；真实PostgreSQL测试验证“结构 功能 基本单位”命中、精确原句优先和稳定排序。
- [x] 4.3 转义LIKE通配符并验证query/mode/limit/subject输入；测试百分号、下划线、反斜线、空有效词与错误类型返回正确结果/400，keyword embedding/chat调用次数均为0。
- [x] 4.4 实现真实embedding单条/有界batch契约和profile兼容查询；测试错维度、NaN/Inf、零向量、响应项缺失及同维不同模型不得混用，profile不匹配返回reindex-required。
- [x] 4.5 在重建时生成并缓存归属profile/generation的句子向量与source映射；验证句子来源不含合成标题、批量响应逐项对应、失败不会发布缺少必需证据定位数据的generation。
- [x] 4.6 实现scoped精确vector召回、0.35最低阈值、独立路径过滤和RRF k=60；测试门槛边界、单路贡献、无关输入不凑数、provider故障503及班级/学科隔离。
- [x] 4.7 实现按匹配原文句span的重叠去重；测试同句跨窗口只保留一个代表、同材料不同相关句仍保留、top4问答证据无冗余且来源不拼接造句。
- [x] 4.8 在开发集运行真实vector/hybrid改写及无关问题评测，校准profile门槛并冻结配置；验证所有预期输出有逐项报告，未达标继续优化，不用demo、降低0.35或改发布保留集掩盖失败；更新本组配置说明。

## 5. 摘录、来源定位与教师操作（阶段4；依赖4）

- [x] 5.1 实现query相关句子窗口选择与最多160 code-point原文excerpt，保留完整chunk_text及独立excerpt offsets；验证片尾命中、超长句、无词面语义命中和移除长URL场景，不直接截片头。
- [x] 5.2 增加授权chunk证据详情和来源hash校验；测试返回完整证据/heading/映射、跨班和未授权学科404、删除/权限撤销/旧来源变化的处理。
- [x] 5.3 更新结果与citation组件，默认短摘录、显示学科/标题/编号/区间，增加展开和打开原文；浏览器验证160字上限、完整证据可见、操作指向正确材料，文档说明excerpt语义变更。
- [x] 5.4 实现预览滚动与safe DOM多span高亮，统一code-point/UTF-16转换；浏览器验证emoji、预处理、Markdown、HTML样式文本不执行以及旧legacy来源不会错误高亮。
- [x] 5.5 在检索/问答视图显式显示可访问学科筛选及demo/reindex状态；浏览器验证视图切换后scope可见、修改选择生效且不能扩大权限。
- [x] 5.6 增加上传/重建的策略、长度、重叠、分隔符、预处理和预览控件；浏览器验证提交实际参数、预览样本/总数及无效输入反馈。
- [x] 5.7 展示source-save、searchable、latest attempt、compatibility及retry；浏览器故障测试验证HTTP成功但failed不显示索引成功、旧索引保留提示正确、失败清理旧结果且无证据/503文案不同。

## 6. 简短证据问答（阶段5；依赖5）

- [x] 6.1 更新chat输入为授权非重复top4证据、subject/material/source spans和bounded history；测试无hits不调用chat、丢弃client system、history边界及无向量/越权证据泄漏。
- [x] 6.2 实现answered/insufficient结构化输出、claims/evidence index/exact quote校验和一次有界修复重试；测试无引用、越界、篡改quote、长度超限、空claims及仍失败502，不补造引用或截断事实。
- [x] 6.3 从有效claims生成<=200 code-point回答及仅实际使用的有序citations；测试引用重排、unused来源剔除、句尾事实保留、insufficient固定文案与无citations、demo标签及503状态。
- [x] 6.4 更新问答页面使用来源组件并清理失败旧回答；浏览器验证真实/演示区分、证据不足、引用点击定位和权限撤销，补充问答API/状态文档。
- [x] 6.5 对30问答案例和20反例运行真实chat验收并人工复核支持关系；交付逐claim证据审阅结果，确认无无依据事实或反向关系复述，不能把substring/citation校验当成语义证明。

## 7. 集成质量、性能与部署（阶段6；依赖1–6）

- [x] 7.1 在隔离PostgreSQL和冻结真实profile上运行发布保留集；报告原句Top-1=100%、词项Recall@5>=95%、vector/hybrid改写各>=90%、无关hybrid空率>=95%，所有fail逐项修复，required skip不得计通过。
- [x] 7.2 运行20权限场景及已有认证/材料回归，覆盖keyword/vector/hybrid/ask/detail/preview/retry；报告跨班/未分配学科内容、metadata和诊断泄漏均为0。
- [x] 7.3 建立>=10000 active chunks/20 scopes性能fixture，记录硬件、扩展版本、至少100次预热后请求及EXPLAIN；验证DB部分p95<=300ms并分别报告embedding/chat/总耗时。
- [x] 7.4 对生产计划执行>=50查询的scoped exact对照；若启用HNSW，校准profile表达式索引、ef_search/iterative scan并验证Recall@10>=95%和语义门槛同时通过；若保留精确计划，记录未启用ANN及性能通过证据，不虚构ANN通过。
- [x] 7.5 完成检索→短摘录→展开→原文高亮→问答引用的浏览器闭环，以及上传失败/retry/改策略/rebuild/scope变化场景；保存可复核截图和场景结果，确认来源精确与无重复证据。
- [x] 7.6 在现有schema副本上演练升级、dry-run、force/resume真实重建、失败恢复和旧profile回滚；比较source/file hash、current唯一性和模型兼容覆盖率，验证不删除原始数据且旧应用回滚前已恢复legacy current。
- [x] 7.7 汇总各组报告和部署说明、修正README中过时的“非目标/账号/固定64维”等描述；检查命令可运行、secret不入文档和所有门槛实际通过后再启用semantic release，缺真实配置时交付明确未完成清单。

## Workflow follow-up

- 本次propose仅完成规划；用户后续请求apply时，按本任务清单实施。
- 实施与质量验收通过后，再根据用户请求协调旧完成变更的冲突规约归档，确保旧关键词/标题偏移行为不覆盖本变更的新契约。
- 归档前复核主规约的来源和能力路径；此次不修改、同步或归档其他变更。
