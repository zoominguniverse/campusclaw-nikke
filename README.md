# CampusClaw

价值：为教师和学生提供按班级隔离的教学材料知识库入口。  
场景：教师上传 `.txt` 或 `.md` 材料后，本班师生可在材料列表中看到记录，跨班访问与学生上传均由服务端拒绝。  
非目标：本项目不实现检索问答、对话助手、作业提交/批改、SSO 或生产级高可用。

## Docker Compose 启动

1. 复制配置：`Copy-Item .env.example .env`（PowerShell）或 `cp .env.example .env`。
2. 在 `.env` 中填入强随机 `SECRET_KEY`、数据库密码和六个演示账号密码；如需演示教务处、班主任和第二位 A 班任课教师，再设置三个可选 `DEMO_*` 管理账号密码。
3. 执行：`docker compose up --build`。

服务端口：

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| Web | http://localhost:5173/login | 登录、受保护页面和同源 `/api` 代理（可用 `WEB_PORT` 覆盖） |

健康检查无需登录：`curl http://localhost:5173/health`，预期返回 `{"status":"ok"}`。API 与 PostgreSQL 仅在 Compose 内部网络可访问，浏览器请求通过 Web 的同源 `/api` 路径代理。

开发种子数据由 `SEED_DEMO_DATA=true` 启用：A 班为数学教师 `teacher_a` 和学生 `student_a1`、`student_a2`，B 班为英语教师 `teacher_b` 和学生 `student_b1`、`student_b2`。设置可选密码后还会创建教务处 `super_admin`、A 班班主任 `class_admin_a` 和语文教师 `teacher_a2`。所有密码只从 `.env` 中读取；生产或非演示环境应设置 `SEED_DEMO_DATA=false`。

## 学科文件夹与权限

每个班级的学科目录相互独立。教务处超级管理员管理班主任及班级授权；班主任管理获授权班级的学科与任课教师分配。学生可以浏览、下载、检索本班全部学科材料；任课教师仅可上传、重建、重命名和删除自己被分配学科的材料。新的教师上传请求必须带 `subject_id`，检索与问答可选传入该字段来缩小范围；返回命中和引用会包含学科名称。

## API 状态约定

- 未登录 API 请求：`401`。
- 已登录但角色无权：`403`；材料详情和下载若不在会话派生的班级范围内，返回与不存在对象相同的 `404`。
- 教师上传：`POST /api/classes/<class_id>/materials`，仅支持 `.txt`、`.md`。
- 本班材料列表：`GET /api/classes/<class_id>/materials`。

PostgreSQL 数据和上传文件使用 Docker named volumes。停止后使用 `docker compose up` 重启会保留数据；执行 `docker compose down -v` 会删除这些卷，用于主动重置开发数据。

## 可追溯知识库检索

第 4 课将材料正文切分为可回溯的 `knowledge_chunks`，正文、切片和向量均位于 PostgreSQL。Compose 使用带 `pgvector` 的 PostgreSQL 16 镜像，启动时会验证 `vector` 与 `pg_trgm` 扩展；不要改回不含扩展的官方 Alpine 镜像。

- `POST /api/classes/<class_id>/knowledge/retrieve`：认证用户检索本班切片。请求为 `{ "query": "...", "mode": "keyword|vector|hybrid" }`，默认 `hybrid`；路径中的班级编号不会覆盖会话班级。
- `POST /api/classes/<class_id>/materials/<material_id>/reindex`：教师携带 CSRF 令牌以 `{ "chunking": { ... } }` 重建本班材料索引。
- `POST /api/classes/<class_id>/knowledge/ask`：仅在本班混合检索有依据时调用对话模型；无命中时返回 `资料中未找到相关内容` 和空 `citations`。

切分策略为 `auto`（默认，约 800 字/80 字重叠）、`custom`（100–2000 字、0–50% 重叠，支持 URL/邮箱/连续空白预处理）和 `hierarchy`（保留 Markdown `#` 至 `###` 标题）。重建索引通过新的 generation 完成后才替换旧 generation，避免检索到混合版本。

本地演示默认使用只在服务端运行的 `deterministic` 嵌入与对话提供方。部署真实模型时设置 `EMBEDDING_PROVIDER=openai-compatible`、`EMBEDDING_API_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL` 以及同类 `CHAT_*` 配置；密钥不得设置给前端容器。`EMBEDDING_DIMENSIONS` 必须与模型输出一致。对于已有材料，运行 `docker compose exec api python backfill_indexes.py` 可按默认策略补齐索引；该操作可重复执行且不会删除原始材料。
