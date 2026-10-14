# 摘录、原文与问答契约

检索 hit 的 `excerpt` 为查询相关的原文窗口，最多160 Unicode code points；不再等同整片正文。完整正文保留在 `chunk_text`，页面默认仅显示 excerpt，每次展开会重新请求授权详情。学科筛选在材料、检索和问答视图共用，并始终可见。

`GET /api/classes/<class_id>/knowledge/chunks/<chunk_id>?source_hash=<hash>&query=<query>` 返回完整证据、章节上下文、映射和切片设置。每次打开重新检查班级/学科权限：不可访问或已删除404，原文hash变化409。打开原文先校验证据，再取材料当前正文并比较hash。`source_spans` 和 excerpt offsets 都是原文 Unicode code-point 半开区间。前端用 `Array.from` 和纯文字节点/mark 展示多段高亮，不解释原文HTML；legacy来源不高亮。

上传和重建支持完整 `chunking` options；预览只切片，最多10个样本，返回总数，不保存、不调用模型。上传201只代表已接受原文，应检查 `indexing.status` 和 material 的 `source_saved`、`searchable_status`、`latest_attempt_status`、`index_compatibility`。失败时原文保留，此前current索引仍保留；“按原设置重试”发送空JSON，服务器使用最近保存的options。

`POST /api/classes/<class_id>/knowledge/ask` 接收 question、可选subject_id/history。检索只取授权且去重的top4；无证据不调用chat。history只保留最后6项中的user/assistant，各最多1000字符，client system丢弃。模型需输出JSON的answered/insufficient、claims和每项的evidence index/exact quote。服务端检查所有引用、原文substring和200字符正文上限；无效输出只修复一次，仍无效返回502。绝不补引用或截断事实；provider异常503，需重建503/code=reindex_required。

响应含 `answer`、`citations`、`status`、`demo_mode`：no_evidence为“资料中未找到相关内容”，insufficient为“资料不足以回答该问题”，二者均无citations；answered只附实际使用的来源，按正文首次使用顺序重新编号，引用含quotes及其原文span。来源在模型请求期间变化会拒绝旧引用。页面开始新请求或更换学科时清空旧证据/回答，故障文案与未命中不同。

演示回答明确标为演示摘录。引用结构与substring校验只能证明引用存在，不能证明事实得到支持；真实30问答和20反例的逐claim人工审阅仍是发布要求。独立浏览器fixture中的故障/insufficient是可控模拟，不计真实语义验收。
