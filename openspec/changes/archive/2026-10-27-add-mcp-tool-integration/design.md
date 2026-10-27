# Design

## Context

动机和范围见 `proposal.md`。2026-10-21 已读取任务清单、思考页及其关联的协议、绑定、调用、安全、审计、实践页，并查看原型的 MCP 管理和技能编辑，以及公开 Swagger。用户明确选择“模型自主选择工具和参数，并支持多轮调用”。原型可参考操作，但课件完整调用循环和本仓权限模型共同决定本次实现。

已观察到的仓库约束：

- Flask/SQLAlchemy/PostgreSQL 后端，Flask/Jinja 和原生 JavaScript 前端；API 走同源代理，使用不透明 Bearer access/refresh token，班级由 `subject_scope` 从当前用户派生。任课教师仅有当前学科材料权限，教务处和班主任不自动继承 teacher 权限。
- `tutor_skills.py` 只允许 `knowledge_search`，按绑定启用技能的关键词选至多一条；`tutor_context.py` 每轮在材料绑定与当前学科授权交集内检索，再把资料放到最后一条 user 消息。
- `tutors.py` 在提交 user 消息后调用 `prepare_turn` 和 `stream_tutor`，目前只发一次 meta；`ProviderTutorStream` 只消费正文 delta，认为 `finish_reason=tool_calls` 是异常，不能直接承担工具决策循环。
- `GenerationLock` 已通过 PostgreSQL 会话 advisory lock 约束跨 worker 的同一会话并发。前端代理已有真实流式转发；前端 meta 处理可以改成合并更新，不需要新建传输通道。
- `api_docs.py` 的 `api_doc` 注解生成 OpenAPI 3.0.3 和 SSE 扩展；`apitest/` 已有动态 case 发现、只读数据库断言、脱敏 HTML 报告及独立 tutor fixture。
- 主规格为空；第 5 课 change 仍为 43/45，真实回答质量及同伴审阅未完成。工作树包含大量既有未提交实现，本次只新增本 change 的规划文件；实施基于这些实际代码，不恢复或覆盖既有变更。

## Goals / Non-Goals

**Goals:** 沿用单应用和现有技术栈，增加独立工具进程；将发现、配置确认、模型提议、宿主授权、出站执行和可追溯结果拆开；保持无 MCP 的会话路径与既有权限、引用、历史契约。

**Non-Goals:** 完整 Streamable HTTP/stdio 客户端互通、resources/prompts、第三方任意工具接入、写入/支付/外发工具及其人工批准工作流、分布式队列、指标与追踪系统。对模型只开放部署方认可的自建只读教学工具。

## Decisions

### 1. 单独交付教学 HTTP 服务，复用 Python 运行方式

新增 `mcp-server/` 的应用、依赖、Dockerfile、README 和协议测试；监听 8090。主 Compose 加入内部 `mcp-demo`，不发布宿主端口，不成为 API 的健康启动依赖。`GET /health` 只报告进程存活，`POST /mcp` 每次先做运行时 Bearer 校验。

实现 JSON-RPC 的版本/ID/方法/参数校验和 `-32700/-32600/-32601/-32602` 错误；未知工具属于参数错误，已知工具业务失败以 `result.isError=true` 表达。拒绝 batch，支持初始化、工具列表、文本工具调用；无 ID 的合法通知不产生 JSON-RPC 响应。初始化使用项目固定的受支持协议版本集合并在文档和双方测试中一致，不声称完整传输兼容。

两个工具均使用 `query`（2–500 字）对象输入：`formula_hint` 覆盖去括号、分数和公式选择的下一步提示；`unit_convert` 讲单位关系及操作方向。二者都不替学生给最终所求答案；不执行表达式代码、不调用模型、不访问外站。采用独立服务而非仅 mock 宿主，才能验证 Compose 互通和实际凭证边界。

### 2. 数据增量升级，调用记录独立于 assistant 消息

在 `models.py` 增加下列概念，迁移放入独立 `mcp_schema.py` 并接入现有初始化 prepare/create/finish 流程：

| 数据 | 主要字段与约束 |
| --- | --- |
| `mcp_servers` | class_id、班内唯一 name（1–64）、base_url、token_ciphertext、connected、operation_revision、configuration_revision、last_error_code、connected_at、维护人及时间 |
| `mcp_tools` | server_id + name 唯一、description、input_schema、declaration_hash；属于当前活动缓存 |
| `skill_mcp_bindings` | skill_id + ref 唯一、server_id、configuration_revision、已确认 declaration_hash；服务删除不删除技能原文 |
| `mcp_tool_calls` | class_id、nullable server_id、服务器名称快照、tool_ref、user_id、conversation_id、user_message_id、call_id、round、sequence、status、reason_code、summary、duration_ms、created_at；call_id 唯一 |
| `conversations` 扩展 | `mcp_attempt_count` 非负整数默认 0，累计远端尝试数，跨请求/重启保留 |
| `messages` 扩展 | `tool_calls_json` 默认空数组；user 行保存本轮快照，assistant 行复制最终快照 |

工具绑定不只保存名字：确认哈希由规范化 name/完整 description/inputSchema 计算，另带 configuration_revision。重连工具未变时哈希相同；名称/URL/令牌改变会增加配置版本，使旧确认失效。删除服务器时 binding.server_id 和 audit.server_id 置空，ref 与审计快照保留，防止新建同名服务器意外复用旧确认。

独立审计可在模型失败且没有 assistant 文本时保留调用。现有消息回读从相应行的快照展示，不重新执行工具，也不把工具长结果加入未来 6 条历史。迁移须在旧第 5 课库和空库执行两次；保留原消息、UUID 材料、索引 generation、向量 profile 和登录数据。

### 3. 密钥可解密保存在服务端，出站范围由部署配置约束

新增 `MCP_ENABLED`（旧环境缺省 false）、`MCP_TOKEN_ENCRYPTION_KEY`、`MCP_AUTH_TOKEN` 和 `MCP_TOOL_POLICY_JSON` 环境变量。加密密钥为独立 Fernet key，仅 API 运行环境持有；使用 `cryptography` 做认证加密，不能复用不可逆 access-token 哈希，也不复用登录签名密钥。新环境示例只给占位，真实值仅在忽略的 `.env`。

教师首次登记输入与 `.env` 中自建服务一致的 token；API 加密保存，接口只回 `has_token`。修改时空字符串或省略表示保留，非空替换后断开。前端只短暂读取 password 输入用于提交，提交后清空，不缓存、不回填；Swagger 请求字段标 `writeOnly`，响应无明文或密文字段。API 与 MCP 的日志不记录请求体或 Authorization；正文/错误脱敏先于上下文、SSE 和落库。

`MCP_TOOL_POLICY_JSON` 按规范化 origin 配置许可的只读工具，例如 `{"http://mcp-demo:8090":{"formula_hint":"read","unit_convert":"read"}}`。origin 本身构成出站白名单；名称映射构成逐工具许可，不相信远端自报的只读属性。教师可查看所有有效发现声明，但只有策略允许的工具能绑定和执行。

Base URL 限 HTTP/HTTPS origin，可有末尾 `/`，拒绝用户信息、其他 path、query 和 fragment，再拼接 `/mcp`。连接和每次执行都重新查策略，禁用重定向、环境代理和环境凭据，精确限制 scheme/host/port；Compose 私网域名显式许可，不能一概禁用私网。远端响应最多 256 KiB，最多 32 个工具，说明每条最多 2000 字，schema 最多 16 KiB、嵌套 8 层；发现分页按相同总预算聚合并拒绝重复/循环游标。

schema 采用有界 JSON Schema 校验；拒绝外部/本地 `$ref`、可执行扩展和复杂正则类约束，不从网络解析 schema。用 `jsonschema` 完成允许子集的 schema 与 arguments 校验。完整 MCP SDK 会引入此课范围之外的传输行为，当前 HTTP 子集更方便逐步核查；本设计不把子集当成通用 MCP 客户端。

### 4. 教师管理接口沿用本仓路径及角色规则

| 方法与路径 | 行为 |
| --- | --- |
| GET/POST `/api/classes/<class_id>/mcp/servers` | 列表 / 登记（201） |
| GET/PUT/DELETE `/api/classes/<class_id>/mcp/servers/<server_id>` | 详情 / 修改 / 删除（204） |
| POST `.../servers/<server_id>/connect` | 兼容握手、完整发现、原子发布 |
| POST `.../servers/<server_id>/disconnect` | 本地立即撤销状态和缓存，幂等 |
| GET `.../servers/<server_id>/tools` | 返回缓存声明、指纹、策略许可和需确认状态 |
| GET `/api/classes/<class_id>/mcp/tool-calls` | 本班审计，默认最近 50 条，limit 上限 100、游标分页 |

所有操作先鉴权和 teacher membership，再按当前有效班级查对象；路径班级、JSON class_id 和自报角色都不能扩大范围。跨班和不存在统一沿用 `{"error":"resource not found"}` 的 404。非法格式/重名 400，缺凭据 401，非教师 403，远端连接失败用 502；仅返回本地稳定 reason_code 和清楚的中文说明，不透传远端错误体。

连接开始时增加 operation_revision、将旧缓存置失效，短事务提交；随后在事务外握手并拉全量工具。发布时用 operation_revision 条件更新并整体替换缓存，只有全部验证和落库成功才 connected=true。断开、修改、删除也使操作版本变化，旧连接结果不能覆盖它们。普通断开/重连不改变 configuration_revision，名称/URL/令牌修改才增加该配置版本，避免相同声明重连误要求确认。失败清空可调用缓存，旧声明可仅通过现有绑定哈希保留，不冒充已连接工具。

### 5. 扩展技能格式和确认载荷，保留现有技能选择

`parse_skill` 保持纯文本解析，扩展严格工具正则和最长工具段限制；数据库相关的班级、状态、缓存和策略校验留在 `_write_skill` 的写入服务。创建/改写在验证完整集合后才写入，失败不改变原技能。

技能 HTTP 请求增加可选的 `tool_confirmations`：`{ "formula_hint@campus-tools": "<declaration_hash>" }`。JSON 与 multipart 均支持（multipart 使用单独 JSON 文本字段）；不增加中文技能文件头字段。新绑定或声明变更必须携带当前指纹，教师界面先完整展示说明/schema、让教师确认再提交。未改变的已确认 binding 可复用；知识库技能无需此字段。清单外或断开返回 400，解析到本班之外/不存在服务器统一 404；确认指纹陈旧返回 400 与 `binding_review_required`。

候选仍来自 `select_skill` 选出的唯一技能。内部 `knowledge_search` 不暴露为远端函数，不再次检索；材料检索始终按原逻辑执行。运行期从本班查询当前状态、配置版本、绑定确认和缓存；不重复解析技能原文或重新握手，但每次 dispatch 均复核会变化的事实。

### 6. 独立模型决策协议，多轮结束后保留真实正文流

新增 `tutor_tools.py` 编排与工具决策适配器；`mcp_client.py` 负责出站协议，`mcp.py` 负责管理接口。不要使现有只消费正文的 provider 直接解析工具调用碎片。首版用同一 `CHAT_*` 配置发 `stream:false` 的工具决策请求，每轮取得完整结构化 assistant tool_calls；决策输出的自由文本不作为正文发出。

声明从已确认的发现内容生成，函数名用 `mcp_<server-id>_<tool-name>` 的有界合法别名，过长时加摘要截断；本轮内建立 alias→ref 映射并检测碰撞。模型请求必须经过该映射，不能把模型给出的字符串当 URL、服务器名或函数入口。工具原名只在宿主的 `tools/call.params.name` 使用，arguments 来自模型并按 inputSchema 验证。

流程：

1. 保留现有 scope/own_conversation/GenerationLock、写入 user 消息、检索和有界历史组装；无 MCP 候选且无失效绑定则沿用原直接流式路径。
2. MCP turn 发初始 meta（skill、citations、demo_mode），失效绑定先记录 denied；不得自动调用所有绑定工具。
3. 发送受限工具声明和上下文，由模型返回零个或多个调用；为每个提议生成独立 call_id、记录 round/sequence，检查别名、参数和当前授权。
4. 实际 dispatch 前重新查询 user/conversation、当前 agent-skill 关系、技能启用状态、工具绑定、服务器配置版本、已连接状态和部署许可；预留并提交累计配额/审计意图，再在短事务外发远端请求。每轮多个调用按顺序执行，后续调用受剩余预算约束。
5. 合法结果只提取 text content；处理 isError、HTTP/JSON-RPC 错误、超时、空内容和 schema 错误。每条文本先脱敏、已知指令句式整条替换，再限长。保存结果及用户消息快照并发累计 meta 更新。
6. 对本轮每个模型 tool_call 追加相关联的 `role:tool` 数据结果；拒绝也补回相同 ID 的固定失败说明。模型可以进入下一轮；决策 messages 仅为本次瞬时状态，不落入正常历史。
7. 模型不再要工具或预算用尽后，丢弃决策性自由文本，把已清洗的结果按 `[工具 ref 返回的数据]` 附到最终 user 数据区，调用现有 `stream_tutor` 产生真正增量正文。最终请求不包含工具声明，故不会继续调用；所有循环产物都不能进入 system 指令位。

将决策与最终流分开会多一次模型往返，但能保留现有正文 provider、引用过滤和先工具后正文的清楚契约，且不必缓存/解析混合的正文与工具碎片。后续可单独优化；本次不在工具循环期间向用户暴露模型推理过程。

默认预算（服务端配置正整数并设置部署上限）：最多 3 个有调用的轮次，每轮最多 8 个提议、每轮决策响应最多 64 KiB；本次累计最多 16 个提议、实际远端尝试最多 6 次；每个会话累计远端尝试最多 30 次；工具阶段总墙钟 20 秒，单次远端请求最多 5 秒。决策请求 timeout 和每次远端请求均裁剪到剩余时间，流式读取时检查单调时钟，禁止把 requests 的 read timeout 误当总时限。拒绝结果不消耗远端次数，但消耗提议预算，失败远端尝试消耗次数且不自动重试。超预算、模型工具协议不支持或格式异常后进入最终无工具生成，并输出固定 tool_warning。

会话计数在现有跨 worker 会话锁下、每次 dispatch 前原子递增并提交，因此不同 worker/重启不能绕过。超出提议长度限制的模型响应整体拒绝并停止决策，不为无限数组生成无限记录。已在返回里的受限提议逐项给出 denied；超过响应上限只报告固定预算/协议 warning。

### 7. 状态、注入与审计的边界

公开状态仅 `ok/error/denied`：权限、确认、schema 和配额拒绝为 denied；远端/协议/超时/不安全输出/空结果为 error；可用文本为 ok。稳定 reason_code 如 `server_unavailable`、`binding_review_required`、`invalid_arguments`、`quota_exhausted`、`remote_timeout`、`unsafe_output`，不要把未知远端字符串直接放进错误。

工具每条可进入模型的结果最多 1200 字，总结果最多 4800 字，审计摘要最多 200 字；调用参数不保存全文，只留必要的不可逆摘要。已知中英文指令式载荷整条替换，规则和用例可追踪，文档明确这不是完备注入防御。真正的动作边界来自候选集、部署只读许可、schema、当前授权和配额。完整说明在绑定确认界面展示，声明只进入受限 tools 字段，不能拼进 system。

审计采用 nullable server_id，哪怕已删除或不存在也能以当前班级、ref 和 user_message_id 留 denied；不查询全局同名服务器，不在理由里确认其他班级存在。这比原型“无服务器则无独立记录”更完整，差异由本次规格明确规定。

远端执行不能与本地数据库提交成为同一事务：先提交带内部 pending 的调用意图，再执行和提交终态；崩溃残留在读取/恢复时展示为 error + `outcome_unknown`，不声称远端未执行、不自动重试。审计意图无法写入则不出站；终态存储失败则停止后续工具并尝试正常辅导，历史/审计保留未确认状态。撤权检查与已发出的 HTTP 之间仍有极短竞态；断开阻止后续 dispatch，不声称可以撤销远端已开始的调用。

### 8. 用重复 meta 表达工具进展，不重建消息

现有成功路径在无 MCP 时仍为 `meta → delta* → done`。MCP 路径为 `meta → meta(tool_calls 累计)* → delta* → done`；每个 meta 都保留 skill/citations/demo_mode，并可包含 `tool_warning`。每条 call 对外仅含 call_id、ref、round、status、reason_code、bounded text，不含地址、令牌或原参数。没有 outcome 时省略 tool_calls。

前端按 call_id 合并工具卡片，meta 不增加对话消息、不清除正文；最终消息和 user 行保存相同已清洗快照，刷新从私有会话恢复。生成中断沿用 interrupted/error 行为，done 仍在成功存库后发出，数字引用只来自材料，工具不增加 citations。API 代理和 fetch 解帧协议不变；增加重复 meta 和取消时资源释放的回归。

第 5 课未归档规格中“tools 仅 knowledge_search”被本次 MCP 引用扩展，“成功只一次 meta”仅对 MCP turn 扩展为更新序列。既有无 MCP 契约保留。本次以六份新增 delta 记录扩展，不修改旧 change 或借机发布主规格。

### 9. 界面、文档与隔离验收使用现有入口

在 `/tutor-config` 增加 MCP 区域，沿用现有导航和页面风格；对照原型显示名称、Base URL、has_token、连接状态、工具详情、最近调用。MCP 请求失败单独显示，不让 `Promise.all` 的一个失败阻断 agent/skill 列表。编辑密钥不回显，技能编辑器增加工具选择/完整声明审阅和确认状态。在 `/tutor` 增加工具状态区、无工具隐藏和历史恢复，使用 textContent，兼顾窄屏和键盘。

沿用 `api_doc` 注册所有新 operation 和更新技能/消息 schema，`api_docs.py` 的 x-sse-events 文档明确重复 meta。Swagger 浏览器试调登记、连接、tools、技能保存，说明 token 为 write-only，不更换现有认证。`apitest` 沿实际 `/api/classes/{class_id}/mcp/...` 增加各 method case 和只读 DB 断言，保持报告忽略。

新增 `docker-compose.mcp-test.yml`，独立 project、临时 PostgreSQL/上传目录、真实自建 MCP 和可控工具决策 HTTP 模型；采用本次专用 fixture 标识和只读 DB 角色，runner 拒绝开发部署。浏览器建议使用新端口 5178（启动前检查占用），不修改现有 5174/5176/5177 环境。真实模型验收单独启用，不把 fixture 输出算模型能力，也不把自动化角色切换算同伴交叉验证。

| 课程条目 | 对应能力 / 实施任务组 |
| --- | --- |
| 自建服务、独立 health/list/call、Compose 同网 | mcp-tool-service / 1 |
| 登记、密钥、连接、缓存清空、跨班隔离 | class-mcp-server-management / 2–3 |
| 引用、保存校验、声明审阅 | mcp-skill-bindings / 4 |
| 模型工具决策、宿主执行、注入与配额 | mcp-tutor-tool-execution / 5–6 |
| meta、历史、调用审计 | mcp-tool-call-observability / 7 |
| 界面、Swagger、apitest、证据和同伴复核 | mcp-workspace-verification / 8–10 |

## Risks / Trade-offs

- [真实 CHAT 模型的工具协议或质量不达标] → 先以 HTTP fixture 验证结构，再实际验证模型自主选择和两轮调用；不兼容时降级并提示，不计为多轮验收通过。
- [多轮模型请求增加首字等待和成本] → 初始 meta 及时送达，工具阶段总预算 20 秒、有限轮次与调用数；无工具路径不新增模型请求。
- [说明投毒/工具返回注入无法完全过滤] → 自建只读许可、完整审阅与指纹确认、数据位、已知载荷拦截和执行配额并用；不宣称句式过滤可证明安全。
- [白名单域名的 DNS/网络被攻破仍有风险] → 当前范围限部署方控制的 Compose origin，禁重定向/环境代理；扩展第三方网络前需另行设计地址绑定与网络出口策略。
- [调用成功而进程/数据库在提交前失败] → 审计意图先提交、未知终态显式记录、不重试；只读教学工具把副作用风险限制在可接受范围。
- [加密密钥丢失导致存量令牌不可恢复] → 保管密钥与数据库备份，错误密钥只使 MCP 不可用，不破坏材料和会话；重新登记令牌，不在本次实现无提示自动换钥。
- [与未归档旧 change 合并时有扩展契约重叠] → 本文明确差异，实施和归档前检查知识库工具限制与 meta 次数；第 5 课 pending 验收继续单独保留。

## Migration Plan

1. 实施前备份数据库和上传卷，记录当前镜像与 schema 版本；不重置正在使用的开发库。先在隔离旧库/空库运行幂等升级，再验证所有既有行与权限。
2. 增量加入表、列及索引；已有 messages 默认空快照，conversations 累计计数从 0 起。`MCP_ENABLED=false` 时保留旧路径，管理页提示未启用；启用时校验运行时加密密钥与只读策略，不做远端健康依赖。
3. 配置本机 `.env`，Compose 仅在运行时给自建服务注入 MCP_AUTH_TOKEN、给 API 注入加密 key/策略；构建上下文显式排除 `.env`、报告和本地测试缓存。先独立验证 `/health` 和带/不带 Bearer 的协议，再用教师 UI 登记与发现，不自动修改已有技能。
4. 先绑定试验技能和智能体，在隔离环境完成所有负例、两轮链路、浏览器/Swagger、回归及真实模型审阅，再按用户部署指令更新目标环境。课堂四项同伴检查须实际完成，以用户明确确认结果正确的记录验收，保存确认日期和结论；同伴姓名、截图或原始请求响应为可选补充。未实际完成或未经用户确认时保留 pending，不用自动化角色切换代替实际同伴复核。
5. 回滚可关闭 MCP 功能或回到旧 API/Web 镜像并停止自建服务；新表、快照与审计保留，不删卷。旧 parser 无法改写含 MCP 引用的技能，回滚前导出其 source，必要时在新版本移除 MCP 项后再回退；旧执行路径仍按原行为检索和回答，不能将其误认为成功调用 MCP。重新升级后对服务器重新连接并检查确认状态。
