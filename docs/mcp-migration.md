# MCP 升级、关闭与回滚

MCP_ENABLED 默认false，旧环境无需额外配置即可启动，原 knowledge_search 技能不改写。启用时需单独的 Fernet key 与非空精确 read 策略；不要复用 SECRET_KEY / AUTH_TOKEN_SECRET。在私有 `.env` 生成并保存 MCP_TOKEN_ENCRYPTION_KEY（`Fernet.generate_key()`），设置 MCP_AUTH_TOKEN（仅工具容器），MCP_ENABLED=true，以及 `MCP_TOOL_POLICY_JSON={"http://mcp-demo:8090":{"formula_hint":"read","unit_convert":"read"}}`。API只接收加密key与策略，教师手动登记工具令牌。不要轮换加密key而丢弃旧key；否则已保存令牌无法解密，需重新登记。

升级前备份数据库和 uploads（加密key另存私有密钥库）：

```powershell
docker compose exec -T postgres pg_dump -U <db-user> -d <db-name> -Fc -f /tmp/pre-mcp.dump
docker compose cp postgres:/tmp/pre-mcp.dump <private-backup-dir>/pre-mcp.dump
docker compose cp api:/app/uploads <private-backup-dir>/uploads
docker compose up -d --build api web mcp-demo
```

使用实际配置的用户名和库名，备份目录须在个人受控位置，勿提交Git。执行已有 entrypoint/init_db.py 会幂等添加 mcp_servers、mcp_tools、skill_mcp_bindings、mcp_tool_calls；messages.tool_calls_json 默认[]；conversations.mcp_attempt_count默认0且非负。版本记录20261021_mcp_tools。重复运行不会重置配额、消息、材料索引或认证关系。新增表中的server删除设空绑定/审计关联，保留引用和名称快照。

先在独立副本升级两次并核对旧行，再对正式库操作。可复现机器验收：

```powershell
docker compose -f deploy/testing/docker-compose.mcp-test.yml up -d --build mcp-postgres mcp-demo mcp-provider mcp-api mcp-web
docker compose -f deploy/testing/docker-compose.mcp-test.yml run --rm mcp-apitest
```

该环境数据库mcp_test、tmpfs、独立上传目录、只读验收角色mcp_readonly，与开发库及5174隔离。重复运行使用新资源名；不会删除教师资源。报告在忽略的 apitest/reports。Windows本机验收端口5284，5178被系统保留。PostgreSQL破坏性schema测试只能使用另建的quality_*库与QUALITY_DISPOSABLE_DATABASE=true，不得指向mcp_test或开发库。

关闭：设置MCP_ENABLED=false并重建API容器，不删除表或清空数据。现有MCP绑定变为本地拒绝，仍可普通辅导；knowledge_search路径无需工具决策。恢复功能后保留计数和历史。工具服务停止不影响API健康、认证、材料和原检索路由。

旧镜像回滚：保留上述新增表/列及数据库数据，只切回已记录的旧API/Web镜像ID，关闭MCP并禁止旧启动脚本自动做不相关迁移；核对health、原认证、检索和原会话。旧第5课parser无法保存包含`@`引用的技能，须提前导出原文；要在旧界面编辑须先在新界面删除MCP引用并保存纯knowledge_search版本。旧Web不会显示工具栏，新快照仍保留，重新升级可恢复显示。不要做破坏性删表“降级”。恢复整个备份会丢失备份后的对话、计数和配置，需另作明确恢复决策。

隔离升级/回滚演练与实际浏览器、HTTP证据见 docs/mcp-acceptance/。真实模型质量与实际同伴交叉验证分别记录，不用fixture替代。
