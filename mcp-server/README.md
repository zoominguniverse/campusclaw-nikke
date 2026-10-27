# 教学 MCP 服务

独立 Flask/Gunicorn 服务，容器内端口 8090。`GET /health` 无需令牌；`POST /mcp` 要求运行时 `MCP_AUTH_TOKEN` 对应的 `Authorization: Bearer ...`。未配置令牌时所有 RPC 均拒绝。令牌不用于构建，也不写入日志。

仅实现固定 **2024-11-05** 版本的 JSON-RPC 2.0 教学子集：`initialize`、`tools/list`、`tools/call`。不支持批请求；合法通知返回204且不执行工具。错误码为 parse -32700、envelope -32600、method -32601、params/version -32602；响应保留请求ID。这不是完整的 MCP SDK / Streamable HTTP 实现，不提供 stdio、资源或 prompts。

`formula_hint` 给出去括号、移项或公式选择的下一步检查提示；`unit_convert` 给出单位关系和方向。两者参数均为 `{"query":"2至500字的问题"}`，结果为文本 content 和 isError。服务不执行表达式、不使用 eval、不调用模型或外部网络，不计算题目最终所求答案。不支持主题返回 isError=true 的说明。

主 Compose 的 `mcp-demo` 仅在内部网络暴露。API 启动和 health 不依赖 MCP。教师登记 `http://mcp-demo:8090` 并手动填写同一令牌，再连接发现；学生没有管理入口。

在独立、无真实密钥的环境复现：

```powershell
docker compose -f docker-compose.mcp-test.yml up -d --build mcp-postgres mcp-api mcp-provider mcp-demo mcp-web
docker compose -f docker-compose.mcp-test.yml exec -e MCP_SMOKE_TOKEN=disposable-mcp-token mcp-api python -m evaluation.mcp_smoke
```

该命令从 API 容器验证 health200、缺令牌401、initialize、发现和两个 tools/call。浏览器入口为 http://localhost:5284（本机5178属于 Windows 保留段）。生产环境用私有环境变量注入 smoke token，不把实际值写进命令历史或报告。

镜像构建上下文采用白名单，只包含 app.py、requirements.txt、Dockerfile；`.env` 和测试均不会进入该镜像。可用 `docker history --no-trunc campusclaw-mcp-test-mcp-demo` 核对无 build arg / ENV 密钥，`docker image inspect` 核对镜像未保存运行时环境值。勿把容器 inspect 的环境变量输出到共享报告。
