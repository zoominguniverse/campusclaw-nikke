# MCP 工具接入与模型决策

教师在“智能体与技能”页登记本班服务器，填写服务器 origin 和访问令牌，连接后展开工具声明，审阅完整 description 与 inputSchema。勾选确认、加入工具引用并保存技能，再将技能绑定到智能体。纯文本或 multipart 上传也可用：工具行填写 `knowledge_search，formula_hint@school，unit_convert@school`；JSON `tool_confirmations` 将引用映射到发现接口返回的 declaration_hash，multipart 中该字段为 JSON 文本。

初次绑定及声明/name/URL/token配置变化需要新确认；普通断开再连接、声明完全相同可复用确认。删除服务器会使旧绑定失效，即使重新登记同名服务器也不能继承。保存整个技能是原子的，失败时原文和绑定均保留。停用、未命中或未绑定的技能不会提供工具。原来的知识检索仍运行一次，不把 knowledge_search 作为远端工具提供给模型。

宿主按既有确定性关键词路由选择至多一个技能。只有该技能的已确认工具进入决策请求。CHAT 兼容接口必须支持 `stream:false`、tools/function 声明、结构化 tool_calls、字符串JSON arguments、唯一调用ID和 role:tool/tool_call_id。模型自行选择是否调用、调用哪个工具、参数及后续轮次；绑定不代表自动执行。正文草稿不会从决策响应展示。多调用按顺序执行，每次重新检查当前身份、私有会话、agent-skill关系、技能启用、绑定版本、缓存、只读策略及参数 schema。

远端地址和令牌只留在宿主。模型看到有界函数别名（`mcp_<id>_<name>`，超长带摘要）、声明和参数；别名反查引用，模型无法指定 URL。远端 readOnly 提示不授予权限，只有 MCP_TOOL_POLICY_JSON 中精确 origin/工具的 `read` 授权有效。仅允许 http(s) origin，拒绝路径、查询、凭据和 fragment；不跟随重定向，不使用环境代理/netrc。发现与调用均复查策略。

默认预算：3轮、每轮最多8提议、每问最多16提议和6次远端尝试、每会话累计30次尝试、工具阶段20秒、每次远端最多5秒。可通过 MCP_MAX_ROUNDS、MCP_MAX_PROPOSALS、MCP_MAX_ATTEMPTS_PER_TURN、MCP_MAX_ATTEMPTS_PER_CONVERSATION、MCP_PHASE_TIMEOUT_SECONDS、MCP_REQUEST_TIMEOUT_SECONDS 调低，不能高于这些上限。额度在出站前和审计意图一同提交；远端失败也消耗次数，本地拒绝不消耗远端次数。累计值存于数据库，刷新页面和服务重启不清零；不自动重试。模型不兼容、超时或预算耗尽时，用固定工具提示说明阶段结束，继续既有无工具正文生成。CHAT正文失败仍按原 error/interrupted 契约处理。

每次结果最多1200字、全部最多4800字，审计摘要最多200字。不保存完整参数。已知令牌先脱敏；已知中英文“忽略规则/泄露密钥/执行命令”载荷整条替换。数字伪引用移除。该过滤不能识别所有提示注入，因此结果永远以 `[工具 ref 返回的数据]` 附在最终 user 数据段，不能成为 system 指令、权限或材料 citation。最终请求没有 tools 字段，由原有 stream_tutor 增量生成并过滤引用。决定往返和正文流是两个阶段。

MCP对话先发初始 meta，再发累计 tool_calls meta 更新，全部早于 delta；每个 meta 保留 skill/citations/demo_mode，可附 tool_warning。工具字段为 call_id/ref/round/status/reason_code/text，状态 ok/error/denied。界面按 call_id 合并，不重复消息、不清正文。无MCP保持单meta；没有结果时省略 tool_calls。done仅在assistant已提交后发出。用户消息保存工具快照，零正文失败也可重开历史查看。工具不会进入普通最近6条历史的长文本上下文。

教师 `GET /api/classes/{class_id}/mcp/tool-calls?limit=50&cursor=...&server_id=...` 读取有效班级审计（上限100、倒序ID游标）。学生和管理员403；外班服务器及不存在404同体。pending意图恢复为 error/outcome_unknown，表示可能已经执行，绝不声称未执行或自动重试。删除服务器保留名称快照和nullable关联。审计终态存储失败会停止后续工具，尽力继续普通辅导，历史保留结果未知。不要自动重放对话POST。

师生界面用纯文本展示工具内容、状态和错误；学生只有对话入口。教师MCP区域加载失败不会影响原智能体/技能配置；令牌输入提交即清空，不写浏览器存储。展开声明、复核失效提示、保存后再发新一轮即可生效。支持键盘、窄屏、状态播报和中断后历史恢复。

SSE简化示例（实际每个meta均带原skill/citations/demo_mode）：

```text
event: meta
data: {"status":"ok","skill":{"id":1,"name":"MCP解题引导"},"citations":[],"demo_mode":false}

event: meta
data: {"status":"ok","skill":{"id":1,"name":"MCP解题引导"},"citations":[],"demo_mode":false,"tool_calls":[{"call_id":"host-a","ref":"formula_hint@school","round":1,"status":"ok","reason_code":null,"text":"先看括号前的符号。"}]}

event: meta
data: {"status":"ok","skill":{"id":1,"name":"MCP解题引导"},"citations":[],"demo_mode":false,"tool_calls":[{"call_id":"host-a","ref":"formula_hint@school","round":1,"status":"ok","reason_code":null,"text":"先看括号前的符号。"},{"call_id":"host-b","ref":"unit_convert@school","round":2,"status":"error","reason_code":"remote_timeout","text":"工具未能提供可用提示。"}]}

event: delta
data: {"text":"你会先检查哪个符号？"}

event: done
data: {"message_id":3}
```
