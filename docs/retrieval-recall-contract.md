# 中文召回与来源窗口

源文/query共用固定jieba 0.42.1及默认词典（SHA256 `7197c3211ddd98962b036cdf40324d1ea2bfaa12bd028e68faa70111a88e12a8`），领域词与停用词在`app/lexical.py`版本化。空格划定词项边界，边界内的组合词仍与正文使用相同词典分词；英语大小写归一化，数字与“不/不能”等否定保留，未知连续单字提供受控二字词项。terms-v2修复了空格组合词与正文切分不一致的问题。改变词典/规则须升级tokenizer处理版本并重建，不能混用旧profile。

PostgreSQL词项字段使用`to_tsvector('simple', lexical_terms)`及current ready部分GIN。精确短语（转义LIKE）优先，OR词项取候选；n=1要求1词命中，n>=2要求至少max(2,ceil(0.6*n))。空格分隔的明确词项保留为coverage单位，其内部按共享词典展开，全部子词命中才计该单位；连续查询按分词后的词项计数。这样“B 班示例材料内容”不会因后一词项展开为多个通用词而掩盖B缺失。随后按coverage、ts_rank_cd和稳定ID排序，候选上限100。legacy仍可对current正文执行有界转义词项检索，不能假称已有精确mapping。

query必须是非空、最多2000 code-point字符串，有效词项最多64；mode为keyword/vector/hybrid，limit为1–20整数，subject_id为正整数，错误类型400。空有效词/空授权范围返回无证据且不调用模型。keyword不调用embedding/chat；通配符只按字面解释。

新vector仅比较配置profile（provider/endpoint身份、model、revision、dimensions和处理版本均一致）、授权范围、current ready active向量。最低cosine 0.35，profile校准可以提高阈值。当前生产计划保持精确计算，HNSW未启用。两路先各自过滤，RRF k=60只融合排名，分数不是置信度概率。provider故障503；范围中的不兼容索引503且code=reindex_required；先处理空授权scope，不泄漏别的scope诊断。

重建缓存归属generation/profile的句子向量，长句分为最多160字的重叠证据窗口，以便纯语义命中选择片尾。搜索只生成一次query向量，不为材料逐句请求provider。batch最多配置数量（默认32），响应必须逐项index齐全、无重复、维度一致、finite/nonzero；句子/块不完整的attempt不发布。

默认excerpt改为相关原文连续子串，最多160 Unicode code points，`chunk_text`仍为完整工作文本。excerpt自身起止与chunk工作区间分开，UI的省略提示不得写入quote。返回generation/source hash、mapping spans、provenance和offset_unit；legacy/source_changed不提供精确highlight位置。删除长URL后不能把左右文本拼成假原文。重叠去重键为material/generation/命中原文句范围，同材料不同有用句仍保留。

本组结构测试（含可控向量）不代表真实语义模型验收。真实provider尚未确定，开发集阈值校准任务4.8保持未完成，semantic release不启用。语料1.0.1补齐了反例参考来源与可回答性标注；未改变任何查询或原文fact，且尚未进行真实模型调参/发布保留集验收。
