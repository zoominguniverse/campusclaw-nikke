# CampusClaw

价值：为教师和学生提供按班级隔离的教学材料知识库入口。  
场景：教师上传 `.txt` 或 `.md` 材料后，本班师生可在材料列表中看到记录，跨班访问与学生上传均由服务端拒绝。  
范围：实现材料管理、可追溯检索和简短证据问答；暂不实现通用对话助手、作业提交/批改、SSO 或生产级高可用。

## OpenSpec 规格与归档

2026-10-27 已完成全部 10 项变更的主规格同步与归档，270/270 项任务完成，当前无活动变更。30 个主规格位于 `openspec/specs/`，历史提案、设计和任务原文保存在 `openspec/changes/archive/2026-10-27-*/`。变更清单、能力导航和新旧约定合并说明见 [OpenSpec 归档记录](openspec/README.md)。

## Docker Compose 启动

1. 复制配置：`Copy-Item .env.example .env`（PowerShell）或 `cp .env.example .env`。
2. 在 `.env` 中填入彼此不同的强随机 `SECRET_KEY` 和 `AUTH_TOKEN_SECRET`、数据库密码，以及 `DEMO_ACCOUNT_PASSWORDS` JSON 中每个固定演示用户名的私有密码。数据库连接中的密码须与 `POSTGRES_PASSWORD` 一致。
3. 执行：`docker compose up --build`。

根目录的 `docker-compose.yml` 用于正常运行。测试与验收配置统一位于 [`deploy/testing/`](deploy/testing/README.md)，以下相关命令均从项目根目录执行。

在线课堂还提供备课、随堂测验、讨论主持、课后复习四类助手，以及支持学科、年级、课题、时长变量的六项提示词模板。教师在“智能体与技能”中预览并应用模板，保存后下一轮生效；见[课堂应用说明](docs/classroom-ai-apps.md)。本机主环境已启用 MCP 公式提示与单位换算，各班“课堂工具助手”可用，实际结果见[本次启用与验收](docs/classroom-mcp-acceptance/README.md)。其他部署仍需独立配置私有密钥与精确工具许可。

服务端口：

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| Web | http://localhost:5173/login | 登录、受保护页面和同源 `/api` 代理（可用 `WEB_PORT` 覆盖） |

健康检查无需登录：`curl http://localhost:5173/health`，预期返回 `{"status":"ok"}`。API 与 PostgreSQL 仅在 Compose 内部网络可访问，浏览器请求通过 Web 的同源 `/api` 路径代理。

开发种子数据由 `SEED_DEMO_DATA=true` 启用，登录名采用姓名拼音。示例：教务处 `zhangruoxi`，1班班主任 `liuyifei`，数学教师 `linzimo`、语文教师 `wangyuxin`，学生 `zhouchengxi`。完整用户名在 `.env.example` 的 `DEMO_ACCOUNT_PASSWORDS` 中，实际密码只从忽略的 `.env` 读取；生产或非演示环境设置 `SEED_DEMO_DATA=false`。

## 学科文件夹与权限

每个班级的学科目录相互独立。教务处超级管理员管理班主任及班级授权；班主任管理获授权班级的学科与任课教师分配。学生可以浏览、下载、检索本班全部学科材料；任课教师仅可上传、重建、重命名和删除自己被分配学科的材料。新的教师上传请求必须带 `subject_id`，检索与问答可选传入该字段来缩小范围；返回命中和引用会包含学科名称。

## API 状态约定

- 未登录 API 请求：`401`，并带 `WWW-Authenticate: Bearer`。
- 已登录但角色无权：`403`；材料详情和下载若不在会话派生的班级范围内，返回与不存在对象相同的 `404`。
- 教师上传：`POST /api/classes/<class_id>/materials`，仅支持 `.txt`、`.md`。
- 本班材料列表：`GET /api/classes/<class_id>/materials`。

## Authorization Bearer 认证迁移

本版本已完全移除 Cookie 会话和 CSRF 令牌。登录 `POST /api/auth/login` 返回不透明的 `access_token` 与 `refresh_token`；客户端把二者仅保存于同一浏览器标签页的 `sessionStorage`，并在每个受保护请求中发送 `Authorization: Bearer <access_token>`。令牌不得放入 Cookie、`localStorage`、URL、DOM 或日志。

- `POST /api/auth/token/refresh` 只接受 `Authorization: Bearer <refresh_token>`，并返回新令牌对。旧刷新令牌的重复使用会撤销整个登录会话族，客户端须清除令牌并重新登录。
- `POST /api/auth/logout` 只接受访问令牌并返回 `204`；服务器会撤销该登录会话族。访问令牌过期或刷新失败时，客户端同样应清除状态并回到登录页。
- 切换部署时，服务启动迁移会撤销现有 Cookie 时代会话，用户必须重新登录。若回滚到旧版本，也应通知用户重新登录，不应尝试复用旧 Cookie。
- 生产环境必须配置 HTTPS 的精确 `TRUSTED_ORIGINS`，不可使用 `*`；API CORS 不允许凭据。前端通过外部脚本和限制性 CSP 降低 XSS 风险，但令牌位于 JavaScript 可读存储中，仍应持续执行 CSP、依赖审计和输入输出编码。

建议监控不含敏感值的认证事件（签发、刷新、拒绝、注销）与 401/429 比例；日志、错误追踪及代理不得记录完整 `Authorization`、令牌、密码或 Cookie。令牌响应包含 `Cache-Control: no-store`，中间层不得覆盖该头。

PostgreSQL 数据和上传文件使用 Docker named volumes。停止后使用 `docker compose up` 重启会保留数据；执行 `docker compose down -v` 会删除这些卷，用于主动重置开发数据。

## 可追溯知识库检索

第 4 课将材料正文切分为可回溯的 `knowledge_chunks`，正文、切片和向量均位于 PostgreSQL。Compose 使用带 `pgvector` 的 PostgreSQL 16 镜像，启动时会验证 `vector` 与 `pg_trgm` 扩展；不要改回不含扩展的官方 Alpine 镜像。

- `POST /api/classes/<class_id>/knowledge/retrieve`：认证用户检索本班切片。请求为 `{ "query": "...", "mode": "keyword|vector|hybrid" }`，默认 `hybrid`；路径中的班级编号不会覆盖会话班级。
- `POST /api/classes/<class_id>/materials/<material_id>/reindex`：教师携带 Bearer 访问令牌并以 `{ "chunking": { ... } }` 重建本班材料索引。
- `POST /api/classes/<class_id>/knowledge/ask`：仅在本班混合检索有依据时调用对话模型；无命中时返回 `资料中未找到相关内容` 和空 `citations`。

切分策略为 `auto`（默认，约 800 字/80 字重叠）、`custom`（100–2000 字、0–50% 重叠，支持 URL/邮箱/连续空白预处理）和 `hierarchy`（保留 Markdown `#` 至 `###` 标题）。重建索引通过新的 generation 完成后才替换旧 generation，避免检索到混合版本。

默认 `deterministic` 仅供演示，不代表语义改写检索已达标。真实服务配置在服务端 `.env`：`EMBEDDING_PROVIDER=openai-compatible`、API URL/key/model、明确的 `EMBEDDING_REVISION` 和实际输出维度，以及 `CHAT_*`。问答模型与向量模型分别配置。向量以独立 profile 存储，支持多种维度共存；旧64维列与旧generation保留，不能直接改维度或混用同维度不同模型。

DeepSeek 官方问答示例（模型标识参考[官方发布说明](https://api-docs.deepseek.com/zh-cn/news/news260910/)）：

```dotenv
CHAT_PROVIDER=openai-compatible
CHAT_API_URL=https://api.deepseek.com
CHAT_API_KEY=replace-with-your-private-deepseek-key
CHAT_MODEL=deepseek-flash
CHAT_TIMEOUT_SECONDS=60
SEMANTIC_RELEASE=false
```

此配置只接入问答，`EMBEDDING_*` 需要独立的 embedding 服务。先使用已有数据库配置，切勿把聊天模型名填到 embedding 配置。保存后 `docker compose up -d --build api web`；密钥不传给前端、不写入文档/报告。

已有材料重建前先执行 `docker compose exec api python retrieval_admin.py backfill --dry-run`，再执行 `docker compose exec api python retrieval_admin.py backfill --limit 100`，按返回cursor继续 `--after <cursor>`；新一轮可从0重新扫描失败项。同策略retry保存完整options；force/profile/恢复命令见[索引操作说明](docs/retrieval-indexing-operations.md)。旧custom参数未知时需显式选择设置。

默认检索卡片只展示最多160字符原文摘录，可展开完整证据并定位原文；回答正文最多200字符，引用由服务端校验生成。保存成功与索引成功分别显示；无证据、资料不足、需重建、模型不可用和引用校验失败有独立状态，详见[证据与问答契约](docs/retrieval-evidence-and-answer.md)。

`SEMANTIC_RELEASE=false` 保持关闭，直到真实profile的开发集校准、发布保留集、问答人工审阅、权限、浏览器、性能和升级回滚演练全部通过。启用需提供服务端可读取且匹配profile/chat模型的 `SEMANTIC_ACCEPTANCE_REPORT`。当前进度和证据见[验收状态](docs/retrieval-quality-status.md)，不得把demo或skip计为真实质量通过。

## 隔离验收

硅基流动/BGE-M3、百炼和DeepSeek的配置示例及接入顺序见[真实服务配置](docs/retrieval-provider-setup.md)。

```powershell
docker compose -p campusclaw-quality -f deploy/testing/docker-compose.retrieval-test.yml run --build --rm quality-tests
docker compose -p campusclaw-quality -f deploy/testing/docker-compose.retrieval-test.yml run --rm -e QUALITY_PERFORMANCE=true quality-tests tests/test_retrieval_performance.py -q
docker compose -p campusclaw-quality-browser -f deploy/testing/docker-compose.retrieval-browser.yml up -d --build
```

测试数据库仅使用独立 `quality_*` PostgreSQL/tmpfs，不连接当前开发库；浏览器环境为 `http://localhost:5175/login`，使用可控演示服务，测试凭据见测试fixture。报告保存在 `docs/retrieval-quality-artifacts`，2026-10-14 已通过真实语义门槛、50 条人工审阅和真实性能/回滚验收，OpenSpec 44/44 完成。主项目运行于 http://localhost:5174，已切换百炼 1024 维 + DeepSeek，并在备份后重建全部 4 条既有材料。见[最终报告](docs/retrieval-quality-artifacts/release-acceptance.md)。详见[评测步骤](docs/retrieval-quality-evaluation.md)和[迁移/回滚](docs/retrieval-quality-migration.md)。

## 第5课：智能体、技能与流式辅导

教师在 `/tutor-config` 维护本班智能体、中文技能文件及当前获授权材料绑定；师生在 `/tutor` 创建固定智能体的私有会话，查看增量回答、技能标签与原文引用。`/swagger/` 提供同源接口试调。已有材料、知识检索及单次证据问答入口保留。技能格式、师生操作和升级策略见[技能说明](docs/tutor-skills.md)、[使用与接口契约](docs/tutor-conversations.md)、[升级与回滚](docs/tutor-migration.md)。

```powershell
docker compose -p campusclaw-tutor-test -f deploy/testing/docker-compose.tutor-test.yml up -d --build tutor-web tutor-provider
docker compose -p campusclaw-tutor-test -f deploy/testing/docker-compose.tutor-test.yml run --rm --build tutor-apitest
```

隔离演示入口为 `http://localhost:5176/login`，fixture凭据见 `backend/tests/conftest.py`；接口报告生成至已忽略的 `apitest/reports/latest.html`。不连接5174开发库。真实模型验收使用独立5177环境，调用计划及样例见[真实模型复核](docs/tutor-acceptance/review-results.md)。

2026-10-14：后端223项通过（2项条件跳过），前端7项通过，27/27接口操作通过，桌面/窄屏和隔离升级回滚通过。OpenSpec `add-agent-skills-streaming-tutor` 的实现验收43/45；真实回答人工质量审阅与实际同伴交叉验证保留待办。本次未更新5174运行服务。完整证据见[第5课验收记录](docs/tutor-acceptance/implementation-acceptance.md)。

2026-10-20：收紧解题引导为单步提示，避免把阅读中心拆成关键词泄露及虚构学生进度；相关26项回归通过，重新采集12组真实模型输出并核对流/引用范围/数据库记录一致。语文解绑对照仍有1例漏标引用，质量未通过；人工质量与同伴验收继续待办，进度43/45。5177隔离演示已使用当前提示词。

2026-10-27：用户确认第5课9.2真实模型质量验收、9.3实际同伴交叉验证均已完成，OpenSpec `add-agent-skills-streaming-tutor` 45/45，已于同日同步主规格并归档。见 [用户验收确认](docs/tutor-acceptance/user-confirmation.md)；原始回答、历史问题和采集状态保留，本次未新增模型测试或同伴明细。


### 第6课：MCP 工具与模型自主多轮调用

教师可在 `/tutor-config` 登记班内MCP服务器，连接发现、审阅并确认声明，将 `formula_hint@school` / `unit_convert@school` 写入技能并绑定智能体。模型自主决定工具和参数，宿主逐次检查权限、持久化配额与审计，最终正文仍增量流式返回。MCP默认关闭，原知识检索可继续使用。

配置与预算见 [工具说明](docs/mcp-tools.md)，密钥、升级和回滚见 [迁移说明](docs/mcp-migration.md)，独立服务见 [服务README](mcp-server/README.md)。隔离验收使用 `docker compose -f deploy/testing/docker-compose.mcp-test.yml up -d --build mcp-postgres mcp-demo mcp-provider mcp-api mcp-web`，随后 `docker compose -f deploy/testing/docker-compose.mcp-test.yml run --rm mcp-apitest`。浏览器入口 http://localhost:5284，固定测试账号同第5课，不使用开发库或真实密钥；报告在忽略的 `apitest/reports/latest.html`。

2026-10-21：后端249项、隔离PostgreSQL18项、前端7项、MCP服务9项通过，36/36接口操作和浏览器/Swagger流程通过；已演练升级两次、关闭功能与旧镜像回滚。用户授权的5组真实 DeepSeek 样例已执行、审阅并核对 SSE/审计/消息/配额一致，见 [真实模型复核](docs/mcp-acceptance/real-model-review.md)。OpenSpec 42/43，实际同伴交叉验证待完成；fixture不计为真实模型质量通过，原第5课43/45待办保持原状。证据、复现入口和限制见 [第6课验收记录](docs/mcp-acceptance/implementation-acceptance.md)。

2026-10-27：用户确认四项实际同伴复核完成、结果正确，并要求简化为用户确认记录；验收约定和 [同伴复核记录](docs/mcp-acceptance/peer-review.md) 已同步，OpenSpec `add-mcp-tool-integration` 43/43 完成，已于同日同步主规格并归档。第5课随后也经用户确认9.2、9.3完成，现为45/45，见上方第5课用户验收确认。
