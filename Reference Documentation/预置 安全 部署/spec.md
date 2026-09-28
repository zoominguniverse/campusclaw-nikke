### Requirement: 预置核心数据

系统 MUST 建立班级、用户、讲义、作业、助手、技能六类核心数据结构（表或等价实体），并预置可验收的样本数据，以支持登录、班级隔离与上传验收。

#### Scenario: 种子数据满足双班与用户

- **WHEN** 首次执行数据库初始化或种子脚本（含 Compose 首次启动时的 entrypoint）
- **THEN** 库中 MUST 存在班级 A、班级 B
- **AND** MUST 存在教师 A（归属班级 A）、学生 A1（归属 A）、学生 B1（归属 B）
- **AND** 各用户 MUST 具备可登录的用户名与已哈希的密码字段

#### Scenario: 两班材料标题可区分

- **WHEN** 种子脚本执行完成
- **THEN** MUST 存在至少一条明确归属 A 班的材料标题（如含「A 班」）
- **AND** MUST 存在至少一条明确归属 B 班的材料标题（如含「B 班」）
- **AND** 六类核心结构中讲义、作业、助手、技能表 MUST 已创建（可各含 0~1 条占位行，不要求本 change 验收业务功能）

### Requirement: 密码哈希与会话密钥

系统 MUST 使用单向密码哈希算法存储用户密码，禁止明文；会话签名密钥（如 `SECRET_KEY`）MUST 仅通过服务端环境变量或 Compose 注入，MUST NOT 硬编码在源码或提交到版本库。

#### Scenario: 库中无明文密码

- **WHEN** 直接查询用户表中密码相关字段（如 `password_hash`）
- **THEN** 字段值 MUST NOT 等于任何已知预置账号的明文口令
- **AND** MUST 可识别为哈希格式（如 bcrypt `$2` 前缀或 argon2 标识）

#### Scenario: 登录校验使用哈希比较

- **WHEN** 用户使用正确明文密码登录
- **THEN** 系统 MUST 通过哈希验证通过并建立会话
- **WHEN** 同一用户使用错误密码登录
- **THEN** 验证 MUST 失败且不建立会话

#### Scenario: 缺少会话密钥时服务不得静默使用默认值

- **WHEN** 生产/Compose 配置未提供会话签名必需的环境变量
- **THEN** 应用启动 MUST 失败或使用文档明确禁止的不安全默认值；`.env.example` MUST 列出所需变量名

### Requirement: Docker Compose 部署与健康检查

系统 MUST 以 Docker Compose 作为标准启动方式；应用 MUST 提供 `GET /health`；数据库文件与上传目录 MUST 通过 volume 持久化，以便容器重建后数据仍在。

#### Scenario: Compose 启动后可访问

- **WHEN** 操作者按 README 复制 `.env.example` 并执行 `docker compose up --build`（或文档等价命令）直至 healthcheck 通过
- **THEN** 浏览器 MUST 可访问登录页 URL
- **AND** `GET /health` MUST 返回 HTTP 200 且 body 表明服务可用（如 JSON `status: ok`）

#### Scenario: health 不依赖登录态

- **WHEN** 未携带会话 cookie 的请求访问 `GET /health`
- **THEN** MUST 仍返回成功响应
- **AND** MUST NOT 重定向到登录页

#### Scenario: 重建容器后数据仍在

- **WHEN** 已存在预置用户、材料或教师上传产生的记录后，执行 `docker compose down` 再 `docker compose up` 且未删除数据 volume
- **THEN** 预置班级与用户 MUST 仍可登录
- **AND** 已上传材料与知识库记录 MUST 仍可通过本班列表或 SQL 查询到