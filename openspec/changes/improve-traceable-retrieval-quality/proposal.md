# Proposal

## Why

用户查找一句话时得到整段切片，改写问句或输入分散关键词又可能搜不到。现有字符哈希演示向量、整串 ILIKE 查询、缺失的来源定位和索引失败反馈，使知识库虽有检索接口，却尚未满足可用、准确、可追溯的检索体验。

## What Changes

- 保留 PostgreSQL 16、pgvector、pg_trgm、Flask 和现有 Bearer/班级/学科权限；不引入 MySQL、Qdrant 或新的 RAG 平台。
- 接入可配置的真实中文嵌入提供方，增加模型/维度/版本标识与安全的全量重建路径；演示模式明确标识，不能通过语义质量验收。
- 将关键词召回从整个查询连续匹配改为精确短语优先、中文词项匹配与覆盖率排序；keyword 不调用模型，vector/hybrid 支持语义改写。
- 保持默认 hybrid、RRF k=60 和向量最低相似度 0.35；增加独立相关性过滤、重叠证据去重和可验证的召回质量门槛。
- 返回查询相关的短摘录，提供完整切片展开和原文高亮定位；修复 Markdown 前言遗漏、空白裁剪偏移和标题补写造成的伪原文区间。
- 补齐上传/重建切分配置、预处理到原文的映射、索引状态/错误/重试、分页补建和并发 generation 切换保护。
- 收紧简短问答和引用契约，区分无证据、证据不足、依赖故障与演示回答；建立真实 PostgreSQL、真实模型和浏览器验收。
- **BREAKING（返回语义）**：`excerpt` 将由完整切片变为最长 160 个 Unicode 字符的原文摘录；`chunk_text` 保持完整证据字段。新增摘录位置、原文跨度、generation 和模型兼容状态，前后端须同步升级。

## Capabilities

### New Capabilities

当前 `openspec list --specs` 为空。以下前三项沿用已完成但未归档旧变更的能力路径，以 ADDED 规约建立正式基线，并明确替换旧变更中涉及关键词、标题正文和偏移的行为；不自动归档或修改旧变更。

- `traceable-knowledge-indexing`：完整且可定位的切片、真实模型兼容性、索引生命周期与可恢复迁移。
- `class-scoped-knowledge-retrieval`：中文关键词/语义/混合检索、短摘录、原文定位和范围隔离。
- `evidence-grounded-knowledge-answering`：简短证据问答、可校验的引用与不足/故障反馈。
- `retrieval-quality-evaluation`：固定评测集、数据库与浏览器验收、量化发布门槛。

### Modified Capabilities

无已同步至 `openspec/specs/` 的主规约。本提案不修改认证与学科授权能力。

## Impact

- 后端：`chunking.py`、`providers.py`、`models.py`、`database.py`、`indexing.py`、`retrieval.py`、`answers.py`、`knowledge.py`、`materials.py`、`config.py`、`backfill_indexes.py`。
- 前端：材料/检索/问答页面及 `materials.js`、样式、来源预览交互。
- 数据：增加模型 profile、向量存储及 generation 元数据、词项索引和来源映射；保留原文、文件和旧 64 维向量用于回滚。
- 配置/依赖：服务端真实 embedding/chat 配置、中文分词依赖、Compose 配置及版本化迁移；不在提案中写入密钥，不实际调用外部模型。
- 验证：扩展单元测试、一次性 PostgreSQL 集成目标、真实模型评测、浏览器场景及部署/回滚说明。
- 本次仅生成规划产物；实施顺序、发布门槛和待提供的真实模型配置见 design/tasks。
