# 第5课隔离接口验收

仅使用 `campusclaw-tutor-test` Compose project：数据库 `tutor_test`、独立临时上传目录、可控HTTP流模型，web端口5176、数据库只读端口5546；不会使用 `.env` 的开发凭据或生产卷。fake fixture账号与密码定义在 `helpers.py`，只用于此隔离环境。

```powershell
docker compose -p campusclaw-tutor-test -f docker-compose.tutor-test.yml up -d --build tutor-web tutor-provider
docker compose -p campusclaw-tutor-test -f docker-compose.tutor-test.yml run --rm --build tutor-apitest
```

runner动态发现 `cases/api/.../{parameter}/METHOD.py`，每个生成的主要API operation一个脚本；shared scenarios检查响应schema、Bearer hash、关联表、拒绝操作无写入、会话归属、SSE首帧顺序/时序/DB一致性及advisory锁释放。报告 `reports/latest.html` 已被Git忽略，并自动脱敏密码、access/refresh token、Authorization和数据库口令。失败时继续收集用例并非零退出；`--inject-failure`验证报告失败路径。

运行前必须同时满足环境开关、专用URL/端口、`tutor_test`及`tutor_readonly`角色、API fixture标识。SQL helper限制SELECT，并使用`SET TRANSACTION READ ONLY`；该角色实际无INSERT权限。指向5174或开发库时立即拒绝。runner从不重置数据库，重复运行使用唯一命名；清理只能关闭上述独立project。

fixture流通过真实HTTP代理返回，首delta延迟约0.15秒、最终完成至少1秒后。用例覆盖多会话并行、同会话409、零正文/部分正文/EOF/首帧之前失败、空绑定与检索落空。它证明传输与状态行为，不能代替真实provider教育质量和实际同伴交叉验证。


## 第6课 MCP 验收

`docker compose -f docker-compose.mcp-test.yml up -d --build mcp-postgres mcp-demo mcp-provider mcp-api mcp-web` 后运行 `docker compose -f docker-compose.mcp-test.yml run --rm mcp-apitest`。独立项目 campusclaw-mcp-test、数据库 mcp_test、只读角色 mcp_readonly、fixture标识 lesson-six-v1，浏览器5284。脚本逐一匹配实际URL/method/operationId；先验证环境身份及只读权限，拒绝开发5174、开发库及写角色。

使用真实自建MCP，模型仅为受控HTTP决策/SSE fixture，证明两轮协议与宿主执行，不证明真实模型质量或实际同伴参与。MCP用例涵盖创建/列表/读取/更新/连接/工具/断开/删除/审计；工具用例关联SSE call_id、DB audit和user/assistant快照，验证断开拒绝、无调用、伪造名、非法参数、轮次预算和零正文/部分失败。第5课环境中MCP用例明确SKIP；不将其计为MCP验收成功。

运行 `docker compose -f docker-compose.mcp-test.yml run --rm mcp-apitest --inject-failure` 应退出1并仍生成HTML；正常全量验收退出0。报告自动脱敏访问令牌、数据库密码、MCP令牌和加密key，HTML转义正文，报告目录被.gitignore忽略。不得把容器运行时ENV或私有.env写入报告。
