# 浏览器结构验收记录（2026-10-13）

目标为隔离`campusclaw-quality-browser`、PostgreSQL `quality_browser`、Chrome `http://localhost:5175/materials`。全部使用确定性演示向量与可控chat/fault fixture，不代表真实语义服务通过。原文与账号均为测试fixture。来源渲染和状态交互在terms-v1完成；后续terms-v2只更改词项覆盖逻辑，核心回归与冻结词项集另有报告。

| 场景 | 实际观察 | 证据 |
| --- | --- | --- |
| 检索→摘录→展开→原文 | 摘录为命中句，展开完整证据；打开原文后准确标记细胞句；terms-v2更新后再查“结构 功能 基本单位”，得到两个不同材料的精确短句 | source-highlight.jpg、keyword-terms-v2.jpg |
| emoji/Markdown/HTML文本 | 原文前置emoji不影响定位；Markdown前言存在；script以文字显示，预览script节点0、无JS弹窗 | source-highlight.jpg |
| 预处理 | 工作片移除URL/邮箱，但原文仍保留，映射不拼接成虚构quote | source-highlight.jpg、upload-fixture.md |
| 多span | 一条引用含两个原文quote，渲染两个独立mark，未引用的换行与emoji保留 | multiple-source-spans.jpg |
| legacy | 标为需重建；关键词可查；原文零mark，未推测精确偏移 | legacy-no-highlight.jpg |
| scope | 三视图始终显示同一学科选择；学生从数学改到化学立即清空旧结果；教师可选范围未扩大 | 现场AX/DOM记录；自动权限报告permission-results.json |
| 演示问答/引用 | “演示摘录”标签；引用按钮指向正确材料并精确定位 | answer-citation.jpg |
| 资料不足 | 检索有证据但受控chat返回insufficient，固定文案、无引用 | insufficient.jpg |
| 服务失败 | 注入503后显示模型不可用；先前回答与引用清空，区别于未命中 | 现场AX记录（服务失败验收查询） |
| 权限撤销 | 返回404后清空旧引用、原文预览与回答，不继续展示过期证据；随后恢复测试membership | revoked-evidence.jpg |
| 改策略与重建失败 | 选择custom=100/25及预处理；failed仍保留旧current，提示原文已保存/重建失败 | rebuild-failed.jpg |
| 重试/参数保留 | 关闭注入故障后按原设置重试ready；重新打开表单100/25保留 | 现场AX记录 |
| 参数错误 | 长度99被拒绝且有中文反馈 | invalid-options.jpg |
| 上传成功、索引失败 | 文件实际上传，source保留；provider故障使索引failed，界面未显示索引成功 | upload-failed.jpg |
| 上传重试与原文 | 恢复provider后ready，文件仍可预览；重建表单保留custom=100/20、三个分隔符与URL/email移除 | upload-retried.jpg |
| 预览上限 | 大文件预览共89片，只展示10片；未提交第二份材料 | upload-preview-limit.jpg、upload-preview-large.md |

截图均在本目录。没有重复同材料/generation/原文句证据；不同材料出现相同事实仍保留独立来源。真实chat标签分支、真实问答支持关系、真实改写闭环尚未验收；6.4/7.5保持未完成。

## 2026-10-14真实服务追加验收

独立5175/tmpfs栈加载百炼text-embedding-v4（1024维）及DeepSeek deepseek-flash；业务5174/数据库没有切换或重建。页面显示“语义检索尚未完成质量验收。问答使用真实模型。”，没有冒充semantic release通过。

| 场景 | 实际观察 | 证据 |
| --- | --- | --- |
| 改写→短摘录 | “生物体由什么基本单位构成”混合检索返回1条细胞句，摘录18 code points，原文[556,574) | real-paraphrase.jpg |
| 完整证据→原文 | 展开完整章节/背景/原文句；打开原文只有一个mark，含前置emoji；script节点0 | real-source-highlight.jpg |
| 真实问答→引用 | DeepSeek回答“细胞是生物体结构和功能的基本单位。[1]”；点击引用定位实际quote，重建后引用切片10仍正确 | real-answer-citation.jpg |
| 真实资料不足 | “细胞膜每天允许多少个分子进出？”返回固定资料不足文案，无引用；先前回答/引用清空 | real-insufficient.jpg |
| 真实改策略/重试 | hierarchy改custom=100/20成功；按原设置重试成功，原文不变 | real-rebuild.jpg及现场AX记录 |
| 撤销权限 | 临时撤销构造教师数学分配后，旧引用打开被拒绝，回答/引用清空；已恢复原分配 | real-revoked-evidence.jpg |

真实浏览器闭环已补齐；上传故障、参数错误、preview上限、legacy及scope变化沿用前述独立演示故障验收。真实问答语义支持关系另由50条逐claim人工清单验收，浏览器截图不替代人工结论。
