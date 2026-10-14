# 检索质量基线（2026-10-13）

命令：在 backend 运行 `python -m pytest tests/test_retrieval_quality_regressions.py -q -p no:cacheprovider`。

旧实现结果：5 failed，1 passed（演示哈希的反例记录）。测试未设 xfail，不得把失败当作发布通过。

| 回归 | 旧行为 | 修复后契约 |
| --- | --- | --- |
| 片尾命中 | excerpt 返回整块467字符 | 至多160 code points，原文区间相等，仍包含命中句 |
| 分散关键词 | “结构 功能 基本单位”返回空 | 词项召回命中，不调用 embedding |
| 反向关系 | 老师帮助学生/学生帮助老师向量相同 | 明确标记 demo，真实语义门槛拒绝哈希提供方 |
| Markdown 前言 | 第一个标题前的内容遗漏 | 未删除的非空白字符覆盖100% |
| trim/标题来源 | 尾部空白、合成标题使区间失真 | 原文区间与文本严格相等，标题上下文单独存储 |
| failed统计 | failed 返回值被计作 completed | failed 单独计数，原文保留 |

本基线只证明原故障可复现。真实provider、PostgreSQL并发/迁移、浏览器来源定位及性能验收仍需分别执行。
