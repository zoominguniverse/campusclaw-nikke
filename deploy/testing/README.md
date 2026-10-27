# 测试与验收环境

正常运行项目使用根目录的 `docker-compose.yml`。本目录集中保存隔离测试、浏览器、真实模型和迁移演练配置；所有下列命令均从项目根目录执行。

构建上下文和仓库内的文件挂载均相对于本目录通过 `../../` 定位。合并多个 Compose 文件时，先指定基础文件，再指定覆盖文件；不要同时指定根目录的主配置。

| 配置 | 用途 | 使用方式 |
| --- | --- | --- |
| [docker-compose.retrieval-test.yml](docker-compose.retrieval-test.yml) | 检索回归与隔离 PostgreSQL | 独立基础配置，指定 `-p campusclaw-quality` |
| [docker-compose.retrieval-real.yml](docker-compose.retrieval-real.yml) | 检索真实模型验收 | 叠加在 retrieval-test 后，指定独立项目名 |
| [docker-compose.retrieval-migration.yml](docker-compose.retrieval-migration.yml) | 旧版本数据迁移演练 | 叠加在 retrieval-test 后，预先准备 `.retrieval-backups/migration-drill/` |
| [docker-compose.retrieval-browser.yml](docker-compose.retrieval-browser.yml) | 检索浏览器验收 | 独立基础配置，指定 `-p campusclaw-quality-browser`，端口 5175 |
| [docker-compose.retrieval-browser-real.yml](docker-compose.retrieval-browser-real.yml) | 浏览器真实模型验收 | 叠加在 retrieval-browser 后，指定独立项目名 |
| [docker-compose.tutor-test.yml](docker-compose.tutor-test.yml) | AI 辅导与接口测试 | 指定 `-p campusclaw-tutor-test`，端口 5176 |
| [docker-compose.tutor-real.yml](docker-compose.tutor-real.yml) | AI 辅导真实模型验收 | 指定 `-p campusclaw-tutor-real`，端口 5177 |
| [docker-compose.mcp-test.yml](docker-compose.mcp-test.yml) | MCP 服务及多轮工具测试 | 内置项目名 `campusclaw-mcp-test`，端口 5284 |

基础测试使用各配置中的临时数据库和固定 fixture 凭据，不使用主项目数据卷。真实模型配置从根目录私有 `.env` 读取服务参数；示例显式指定 `--env-file .env`。核对配置时使用 `config --quiet`，避免打印展开后的密钥。

## 常用命令

检索回归：

```powershell
docker compose -p campusclaw-quality -f deploy/testing/docker-compose.retrieval-test.yml run --build --rm quality-tests
```

真实模型配置检查与开发集评测：

```powershell
docker compose --env-file .env -p campusclaw-quality-real -f deploy/testing/docker-compose.retrieval-test.yml -f deploy/testing/docker-compose.retrieval-real.yml config --quiet
docker compose --env-file .env -p campusclaw-quality-real -f deploy/testing/docker-compose.retrieval-test.yml -f deploy/testing/docker-compose.retrieval-real.yml run --build --rm --entrypoint python quality-tests -m evaluation.run --split dev --output /quality-results/dev-real
```

检索浏览器环境：

```powershell
docker compose -p campusclaw-quality-browser -f deploy/testing/docker-compose.retrieval-browser.yml up -d --build
```

浏览器真实模型覆盖配置检查：

```powershell
docker compose --env-file .env -p campusclaw-quality-browser-real -f deploy/testing/docker-compose.retrieval-browser.yml -f deploy/testing/docker-compose.retrieval-browser-real.yml config --quiet
```

迁移演练配置检查（需已准备旧版本与上传文件副本）：

```powershell
docker compose -p campusclaw-quality-migration -f deploy/testing/docker-compose.retrieval-test.yml -f deploy/testing/docker-compose.retrieval-migration.yml config --quiet
```

AI 辅导测试与真实模型环境：

```powershell
docker compose -p campusclaw-tutor-test -f deploy/testing/docker-compose.tutor-test.yml up -d --build tutor-web tutor-provider
docker compose -p campusclaw-tutor-test -f deploy/testing/docker-compose.tutor-test.yml run --rm --build tutor-apitest
docker compose --env-file .env -p campusclaw-tutor-real -f deploy/testing/docker-compose.tutor-real.yml up -d --build real-web
```

MCP 测试：

```powershell
docker compose -f deploy/testing/docker-compose.mcp-test.yml up -d --build mcp-postgres mcp-demo mcp-provider mcp-api mcp-web
docker compose -f deploy/testing/docker-compose.mcp-test.yml run --rm mcp-apitest
```

停止环境时，沿用对应的项目名和 `-f` 文件参数，将动作改为 `down`。接口报告仍生成到被 Git 忽略的 `apitest/reports/`；检索和人工验收资料保持原有 `docs/` 位置。

详细步骤见[接口验收](../../apitest/README.md)、[检索评测](../../docs/retrieval-quality-evaluation.md)、[迁移演练](../../docs/retrieval-quality-migration.md)与 [MCP 迁移](../../docs/mcp-migration.md)。OpenSpec 归档中的旧文件名保留当时记录，当前操作以本目录路径为准。
