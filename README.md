# CampusClaw

价值：为教师和学生提供按班级隔离的教学材料知识库入口。  
场景：教师上传 `.txt` 或 `.md` 材料后，本班师生可在材料列表中看到记录，跨班访问与学生上传均由服务端拒绝。  
非目标：本项目不实现检索问答、对话助手、作业提交/批改、SSO 或生产级高可用。

## Docker Compose 启动

1. 复制配置：`Copy-Item .env.example .env`（PowerShell）或 `cp .env.example .env`。
2. 在 `.env` 中填入强随机 `SECRET_KEY`、数据库密码和六个演示账号密码。
3. 执行：`docker compose up --build`。

服务端口：

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| 前端 | http://localhost:5173/login | 登录与受保护页面 |
| Flask API | http://localhost:8080 | 认证、材料上传和列表 API |
| PostgreSQL | localhost:5432 | 本地数据库检查工具连接 |

健康检查无需登录：`curl http://localhost:8080/health`，预期返回 `{"status":"ok"}`。

开发种子数据由 `SEED_DEMO_DATA=true` 启用：A 班为教师 `teacher_a` 和学生 `student_a1`、`student_a2`，B 班为教师 `teacher_b` 和学生 `student_b1`、`student_b2`。所有密码只从 `.env` 中读取；生产或非演示环境应设置 `SEED_DEMO_DATA=false`。

## API 状态约定

- 未登录 API 请求：`401`。
- 已登录但角色或班级无权：`403`。
- 教师上传：`POST /api/classes/<class_id>/materials`，仅支持 `.txt`、`.md`。
- 本班材料列表：`GET /api/classes/<class_id>/materials`。

PostgreSQL 数据保存在 `postgres-data/`，上传文件保存在 `uploads/`。停止后使用 `docker compose up` 重启（不删除这些目录）会保留数据。
