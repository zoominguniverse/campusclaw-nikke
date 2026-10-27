# Proposal

## Why

CampusClaw 已具备第 5 课的班内智能体、确定性技能路由、私有会话和流式辅导，但技能的工具字段目前仅接受 `knowledge_search`，没有远端工具发现、执行或审计能力。第 6 课需要把同仓自建的 MCP 工具服务真正接入教学对话，使工具来源、权限、失败和调用过程都可验证。

## What Changes

- 在同一仓库增加 `mcp-server/`，随主 `docker-compose.yml` 构建运行，提供 Bearer 保护的 HTTP JSON-RPC `initialize`、`tools/list`、`tools/call` 和独立健康检查；首批工具为只给步骤提示的 `formula_hint`、`unit_convert`。
- 教师登记和维护本班服务器，连接时握手并整体替换发现缓存，断开时清空缓存；令牌只留在服务端，不出现在响应、日志、前端持久存储或镜像层。
- 扩展现有中文技能文件，接受 `工具名@服务器名`，保存时验证格式、本班归属、连接状态及发现清单；保持原技能格式、绑定和词法路由。
- 按补充课件的完整调用循环实现：命中技能限定候选工具，模型提出工具及参数，宿主逐项授权和校验，带令牌执行后将成功或失败回传模型；限制轮次、调用次数、会话累计次数及时间，超限后用已有信息继续生成。
- 工具返回作为不可信数据处理，已知指令载荷整条替换；教师可查看完整工具说明及参数，说明变化后须重新确认绑定。只允许部署方许可的自建只读工具，扩展出站地址校验。
- 通过 SSE `meta.tool_calls` 在正文之前显示工具引用和状态，记录班内调用审计并支持历史恢复；工具不可用时继续检索和辅导，不伪装为成功。
- 在现有 `/tutor-config`、`/tutor`、Swagger 和 `apitest/` 中增加 MCP 操作、状态和端到端验收；交付独立测试环境、脱敏证据及同伴复核步骤。

## Capabilities

### New Capabilities

- `mcp-tool-service`：同仓自建工具服务、教学工具语义、JSON-RPC 报文与 Bearer 认证。
- `class-mcp-server-management`：教师专属的班内服务器登记、密钥保管、连接发现、缓存失效及出站限制。
- `mcp-skill-bindings`：MCP 引用格式、保存校验、发现版本确认和命中技能候选集。
- `mcp-tutor-tool-execution`：模型提议与宿主执行分工、多轮编排、预算、故障降级和不可信数据边界。
- `mcp-tool-call-observability`：SSE 工具元数据、历史快照及班内审计记录的字段、权限与脱敏。
- `mcp-workspace-verification`：教师管理和对话展示、注解生成的接口文档、隔离接口测试与课堂证据。

### Modified Capabilities

无已发布主规格可修改：`openspec list --specs` 返回空，`openspec/specs/` 仅有占位文件。上述扩展以新增 delta 描述；设计明确列出与未归档第 5 课 change 中“仅支持 knowledge_search”和“仅一次 meta”的重叠契约及本次调整，不修改、同步或归档其他 change。

## Impact

- 后端：扩展 `models.py`、初始化迁移、技能解析/保存、`tutor_context.py`、`tutors.py`、`tutor_stream.py` 和 `api_docs.py`；新增 MCP 管理、HTTP 客户端、密钥封装及调用编排模块。增量保留现有材料、索引、鉴权和会话数据。
- 前端：在 Flask/Jinja、原生 JavaScript 与现有同源 SSE 代理上扩展，沿用不透明 Bearer access/refresh token 和当前角色/学科授权，不照搬原型的 JWT 或路由。
- 运行与依赖：新增内部 `mcp-demo:8090` 服务、环境变量占位和隔离 Compose；复用 Flask/requests，增加有界 JSON Schema 校验及令牌加密所需最小依赖，版本在实现时锁定兼容范围。
- 验收：工具服务真实 HTTP 往返、模型工具协议 fixture、跨班/越权/断开/超时/注入/配额、Swagger、浏览器及数据库一致性；真实模型须以实测证据验收。同伴四项检查须实际完成，以用户明确确认结果正确的记录验收，不强制另交同伴姓名、截图或原始请求响应。第 5 课尚未完成的质量与同伴审阅仍保留原状态。

依据：[任务清单](https://devops.hello1023.com/课程任务清单-第6课.html)、[思考与分析](https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/think.html)、[实践与验收](https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/apply.html)、[系统原型](https://devops.hello1023.com/week06/admin)。任务清单声明补充要求以课件为准，因此纳入多轮调用；完整 MCP 传输互通、stdio、资源/提示能力、任意第三方或写入工具、全站改版及第 8 课指标/追踪不属于本 change。
