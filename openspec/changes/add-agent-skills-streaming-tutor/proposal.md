# Proposal

## Why

CampusClaw 已具备按班级和学科隔离的材料管理、混合检索与单次证据问答，但教师尚不能配置解题智能体，学生也不能保存连续追问并逐段看到回答。第 5 课要求把智能体提示词、绑定技能、绑定知识库接入同一次回答，并交付可试调的 Swagger 和能核对数据库的接口测试。

## What Changes

- 新增本班智能体管理：名称、角色提示词、启停状态、技能与材料绑定；空提示词使用默认角色，配置更新下一轮生效。
- 新增中文文本技能文件的解析、增删改查与确定性路由；只从所选智能体绑定且启用的技能中选至多一条，名称含「解题引导」时只指导下一步，不给最终答案。
- 新增用户私有会话和持久化消息；创建时锁定本班已启用智能体，历史窗口为最近 6 条、每条最多 500 字。
- 新增会话回答链路：先在当前授权范围与绑定材料交集内检索，引用先行，再用 SSE 返回增量文本；无证据仍按角色与技能作答，引用为空。
- 新增教师配置页和学生/教师解题会话页，参考原型的智能体选择、最近对话、逐段回答、技能标识和出处入口，接入现有角色工作区。
- 从处理器注解生成 OpenAPI，提供同源 Swagger 页面；新增 `apitest/`，按 URL 与 HTTP 方法组织脚本，一键运行并生成不入 Git 的 HTML 报告，验证响应内容与数据库一致性。
- 兼容现有不透明 Bearer access/refresh token、学科授权与第 4 课检索接口；原 `knowledge/ask` 的无证据拒答和简短证据回答契约保持不变。流式会话是新增接口，不替换原接口。

## Capabilities

### New Capabilities

- `class-tutor-agent-management`：教师维护班内智能体与两类绑定，学生选择已启用智能体，维持角色、班级和材料权限边界。
- `class-tutoring-skills`：技能文本解析与班内管理，以及基于智能体绑定的词法路由和解题引导约束。
- `private-tutor-conversations`：用户私有会话、不可变智能体关联、消息历史、标题与有界上下文。
- `streaming-tutor-answering`：绑定材料内检索、消息组装、真实模型流式生成、SSE 事件、引用与失败持久化。
- `tutor-workspace-ui`：教师配置与师生解题会话的界面、流式状态、历史恢复和证据打开。
- `documented-api-verification`：与处理器同源的 OpenAPI/Swagger、按接口组织的自动化验证与数据库断言。

### Modified Capabilities

无。当前 `openspec/specs/` 仅有 `.gitkeep`，既有规格仍在已完成但尚未归档的 changes 中；本 change 不改写那些 change，也不借本次规划同步或归档旧规格。上述能力均为第 5 课新增行为，并明确保持既有证据问答和学科授权。

## Impact

- 后端：`backend/app/models.py`、`database.py`、`authorization.py`、`retrieval.py`、`providers.py`、`materials.py` 与应用注册；新增智能体、技能、会话、编排及接口文档模块。已有 `skills` 只有 `id/name` 占位字段，必须设计幂等升级，不能仅依赖 `create_all()`。
- 前端：Flask/Jinja 和原生 JavaScript 工作区；`frontend/server.py` 当前读取完整 `upstream.content`，需增加真正的流式转发；两端 Gunicorn 配置需验证长连接并发。
- 数据：新增智能体、关联表、会话和消息；扩展技能表。保留已有材料 UUID、索引 generation、向量 profile 和鉴权数据。
- 接口：新增班内 agents/skills 和用户 conversations/messages 路由，文档覆盖现有登录/刷新、材料、检索/单次问答及新增主要接口；不照搬演示的 JWT、Cookie、Go/Nginx 或路径。
- 依赖：模型与 embedding 沿用现有 `CHAT_*`/`EMBEDDING_*`；文档工具和 Swagger 静态资源使用可固定版本的最小依赖，满足现有 CSP。
- 验收：隔离 PostgreSQL 环境、模型流 fixture、真实模型引导行为验收、浏览器证据和同伴交叉验证记录；密钥仅在本机 `.env`，报告脱敏且 HTML 产物忽略。

参考：[任务清单](https://devops.hello1023.com/课程任务清单-第5课.html)、[实现教程](https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/index.html)、[系统原型](https://devops.hello1023.com/week05/tutor)。范围限本课解题助手、文档与接口测试；原型的错题本、智能批改、自助学习、收藏和个人目录不纳入本 change。
