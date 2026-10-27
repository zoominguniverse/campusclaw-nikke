# OpenSpec 规格与归档

`specs/` 是当前已实现能力的主规格。`changes/archive/` 保存历次提案、设计、增量规格和任务清单；历史文档描述当时的约定，当前行为以合并后的主规格为准。

## 2026-10-27 批量归档

全部 10 项变更使用 `spec-driven` schema，文档齐全，270/270 项任务完成。按实施先后同步 33 份增量规格，形成 30 个主规格，再归档全部变更。每个变更移动前后均逐文件核对 SHA-256；历史内容及 `.openspec.yaml` 完整保留。

| 归档变更 | 完成任务 | 增量规格 |
| --- | ---: | ---: |
| [登录、隔离与材料库](changes/archive/2026-10-27-add-auth-class-isolation-material-kb/) | 30/30 | 4 |
| [可追溯向量检索](changes/archive/2026-10-27-add-traceable-vector-retrieval/) | 29/29 | 3 |
| [中文文件与多编码上传](changes/archive/2026-10-27-support-localized-text-uploads/) | 4/4 | 1 |
| [材料删除界面](changes/archive/2026-10-27-add-material-deletion-ui/) | 3/3 | 1 |
| [学科材料与角色管理](changes/archive/2026-10-27-add-subject-scoped-material-management/) | 30/30 | 4 |
| [角色工作区与界面](changes/archive/2026-10-27-redesign-role-based-teaching-ui/) | 21/21 | 3 |
| [Bearer 认证迁移](changes/archive/2026-10-27-authorization-only-authentication/) | 21/21 | 1 |
| [检索质量优化](changes/archive/2026-10-27-improve-traceable-retrieval-quality/) | 44/44 | 4 |
| [AI 技能与流式辅导](changes/archive/2026-10-27-add-agent-skills-streaming-tutor/) | 45/45 | 6 |
| [MCP 工具接入](changes/archive/2026-10-27-add-mcp-tool-integration/) | 43/43 | 6 |

## 主规格导航

| 范围 | 能力 |
| --- | --- |
| 身份与隔离 | [认证与角色](specs/user-authentication-and-authorization/spec.md)、[Bearer 生命周期](specs/authorization-only-api-authentication/spec.md)、[班级隔离](specs/class-data-isolation/spec.md)、[教育角色治理](specs/education-role-governance/spec.md) |
| 材料与学科 | [材料入库](specs/material-knowledge-base-ingestion/spec.md)、[中文文本上传](specs/localized-text-material-upload/spec.md)、[材料删除](specs/material-deletion-ui/spec.md)、[班级学科目录](specs/class-subject-folders/spec.md)、[学科材料权限](specs/subject-scoped-material-access/spec.md)、[学科检索权限](specs/subject-aware-knowledge-retrieval/spec.md) |
| 检索与证据问答 | [索引](specs/traceable-knowledge-indexing/spec.md)、[检索](specs/class-scoped-knowledge-retrieval/spec.md)、[证据问答](specs/evidence-grounded-knowledge-answering/spec.md)、[质量评测](specs/retrieval-quality-evaluation/spec.md) |
| 运行与工作区 | [服务运行](specs/service-runtime/spec.md)、[登录界面](specs/reference-aligned-account-login-ui/spec.md)、[角色外壳](specs/role-aware-application-shell/spec.md)、[角色工作区与演示数据](specs/role-oriented-teaching-workspace/spec.md) |
| AI 辅导 | [智能体](specs/class-tutor-agent-management/spec.md)、[技能](specs/class-tutoring-skills/spec.md)、[私有会话](specs/private-tutor-conversations/spec.md)、[流式回答](specs/streaming-tutor-answering/spec.md)、[辅导界面](specs/tutor-workspace-ui/spec.md)、[接口文档与验证](specs/documented-api-verification/spec.md) |
| MCP | [工具服务](specs/mcp-tool-service/spec.md)、[服务器管理](specs/class-mcp-server-management/spec.md)、[技能绑定](specs/mcp-skill-bindings/spec.md)、[执行编排](specs/mcp-tutor-tool-execution/spec.md)、[审计与流事件](specs/mcp-tool-call-observability/spec.md)、[界面与验收](specs/mcp-workspace-verification/spec.md) |

## 合并时处理的历史差异

- **认证与页面入口**：后续 Bearer 变更替代 Cookie/CSRF 认证；登录身份位于 `user` 对象，工作区先返回无业务数据的外壳，再由客户端验证 Bearer 身份。登录成功进入 `/materials`，不保留旧版服务端会话重定向和 `next` 约定。
- **演示数据**：三班、六学科、四类角色及私有运行时密码映射替代旧 A/B 班固定账号。服务端会话族仍用于撤销与刷新管理，不代表 Cookie 认证。
- **学科权限与运行**：旧班级级材料能力受后续学科授权约束；原文件按班级和学科存储。运行规格反映当前 pgvector、内部 MCP 服务和 `WEB_PORT` 覆盖方式。
- **索引与上传状态**：来源保存和语义索引分开报告；来源已提交但嵌入失败可返回 201 和失败状态，不能回写为原文保存失败。标题作为上下文与原文切片分离，预处理保留原文跨度映射。
- **检索与引用**：保留旧规格未被替代的要求和场景；后续质量规格细化相关性、profile、去重、短摘录与精确引用。摘录使用相关原文，完整切片另行展开。
- **两类回答**：`knowledge/ask` 仍无证据拒答；私有流式会话允许无引用辅导，避免把前者的规则扩大到后者。
- **MCP 扩展**：技能允许经确认的 `tool@server` 引用；普通流保持单个初始 meta，MCP 流可在正文前发送累计工具 meta。原确定性技能路由、材料引用和历史边界继续生效。

验收结论沿用仓库已有证据和用户确认。第 5 课的历史漏标引用及未通过采集记录保留；归档不表示这些历史输出已修复或重新生成。详见[用户验收确认](../docs/tutor-acceptance/user-confirmation.md)与 [MCP 同伴复核](../docs/mcp-acceptance/peer-review.md)。本次仅归档与整理规格，不运行业务迁移、重建索引或重新调用模型。

## 归档校验

- `openspec list --json`：无活动变更。
- `openspec validate --all --json`：30/30 个主规格通过，无错误；保留 15 条非阻断文字长度提示（4 个原始 Purpose 少于 50 字符、11 个要求正文超过 500 字符）。Purpose 原文按同步契约保留，不为消除提示改写。
- `openspec validate --archived --json`：10/10 项归档任务完整性通过。
- `openspec doctor --json`：规划根健康，无关系问题。
- 历史文件移动前后 SHA-256 一致；与 Git 原文核对时仅归一化检出产生的换行差异。主规格保留全部增量要求和场景的名称，变更内容仅限上述已实现约定的合并；导航链接有效。
