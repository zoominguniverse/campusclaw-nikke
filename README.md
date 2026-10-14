# CampusClaw

价值：为教师和学生提供按班级隔离的教学材料知识库入口。  
场景：教师上传 `.txt` 或 `.md` 材料后，本班师生可在材料列表中看到记录，跨班访问与学生上传均由服务端拒绝。  
范围：实现材料管理、可追溯检索和简短证据问答；暂不实现通用对话助手、作业提交/批改、SSO 或生产级高可用。

## Docker Compose 启动

1. 复制配置：`Copy-Item .env.example .env`（PowerShell）或 `cp .env.example .env`。
2. 在 `.env` 中填入彼此不同的强随机 `SECRET_KEY` 和 `AUTH_TOKEN_SECRET`、数据库密码，以及 `DEMO_ACCOUNT_PASSWORDS` JSON 中每个固定演示用户名的私有密码。数据库连接中的密码须与 `POSTGRES_PASSWORD` 一致。
3. 执行：`docker compose up --build`。

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
docker compose -p campusclaw-quality -f docker-compose.retrieval-test.yml run --build --rm quality-tests
docker compose -p campusclaw-quality -f docker-compose.retrieval-test.yml run --rm -e QUALITY_PERFORMANCE=true quality-tests tests/test_retrieval_performance.py -q
docker compose -p campusclaw-quality-browser -f docker-compose.retrieval-browser.yml up -d --build
```

测试数据库仅使用独立 `quality_*` PostgreSQL/tmpfs，不连接当前开发库；浏览器环境为 `http://localhost:5175/login`，使用可控演示服务，测试凭据见测试fixture。报告保存在 `docs/retrieval-quality-artifacts`，2026-10-14 已通过真实语义门槛、50 条人工审阅和真实性能/回滚验收，OpenSpec 44/44 完成。主项目运行于 http://localhost:5174，已切换百炼 1024 维 + DeepSeek，并在备份后重建全部 4 条既有材料。见[最终报告](docs/retrieval-quality-artifacts/release-acceptance.md)。详见[评测步骤](docs/retrieval-quality-evaluation.md)和[迁移/回滚](docs/retrieval-quality-migration.md)。
