# Design

## Context

动机与范围见 `proposal.md`。本次只创建规划 artifacts，不执行迁移、修改业务代码或切换当前运行环境。

已核查的仓库事实：

| 位置 | 当前实现 | 对设计的约束 |
| --- | --- | --- |
| `backend/app/models.py` | SQLAlchemy；`Skill` 只有 `id/name`，`Assistant` 为占位；材料 ID 是 UUID 字符串 | 技能需要显式升级，不能照搬演示整数材料 ID |
| `backend/app/database.py` | `create_all()` 加幂等升级，`SchemaMigration` 记录版本；演示种子会插入占位技能 | 扩展表前处理旧结构，保留旧行但使其不可参与路由；更新种子逻辑 |
| `backend/app/auth.py`、`frontend/static/auth.js` | 不透明 Bearer access/refresh token；sessionStorage；POST 不自动重试 | 沿用认证，不迁移 JWT/Cookie，不自动重放消息 |
| `backend/app/authorization.py` | teacher/student 的有效班级为 `user.class_id`；教师按学科授权，教务/班主任不自动获得材料权限 | 新助手不能把教师范围扩大到全班；保持四角色边界 |
| `backend/app/retrieval.py` | profile/generation 校验、句级门槛、词法与向量融合；只有 subject_ids，没有 material_ids | 必须把材料交集传到所有候选和兼容性查询，不能仅过滤最终 hits |
| `backend/app/answers.py`、`providers.py` | 无证据不调用 chat；200 字结构化 JSON、原文 quote 校验；chat 为 `stream: false` | 保留旧 answer 路径，新增独立 tutor streaming 方法 |
| `frontend/server.py` | requests 代理读取 `upstream.content` 后返回 | 现状会吞掉流式效果，需端到端 generator 转发 |
| 两端启动配置 | Gunicorn 两个同步 worker，timeout 180 秒 | 长流会占住 worker；改为受控 gthread 并验证并发 |
| `openspec/specs/` | 无已归档主规格；相关行为在已完成 changes 内 | 新规格均 ADDED，明确兼容旧变化，不自动归档旧 change |

参考任务清单、教程 `scope/session/skill-model/route/stream/answer/apply` 章节、原型学生界面和 Swagger。教程的 stream 页仍含 Cookie、Go/Nginx 和“有切片才调用”旧描述，与任务清单 Bearer、课程概览和 answer 页冲突。本设计以清单与核心行为为准：Bearer + fetch POST，落空仍生成；技术实现使用现有 Python 栈。原型展示了额外产品入口，本 change 只对齐解题相关界面。

## Goals / Non-Goals

**Goals:**

- 把已有混合检索作为可传入材料白名单的服务复用，同时保持旧调用结果和质量门槛。
- 一轮请求按当前配置取输入；网络流不持有长数据库事务；持久化、错误与历史回放形成明确状态。
- 注解、路由、OpenAPI 和接口脚本能相互核对，测试运行与当前开发数据隔离。

**Non-Goals:**

- 不实现工具执行循环、自动语义选技能、WebSocket、断点续传、Agent Skills 标准目录或任意脚本运行。
- 不为原型旧 `class_prompts` 增加迁移表：本仓库没有该表，也没有旧提示词接口；角色只存于智能体。
- 不把流式出处声称为原单次问答的逐 claim 精确 quote 验证或既有 semantic release 报告覆盖的质量成果。
- 不增加智能体删除或会话删除接口；技能删除和材料删除会移除对应绑定，智能体保留以支持历史会话。

## Decisions

### 1. 沿用有效班级与学科权限，区分配置权限和材料权限

新增 `agents`、`skills`、`conversations` 蓝图与 tutor 编排模块。配置写权限要求 active teacher 及有效班级教师成员资格；student 和两类管理员不获得教师写权限。智能体与技能作为班级配置共享，由本班任课教师维护，维护人与时间记录用于追踪。材料绑定只接受写入教师当前可访问学科的材料；整组字段与绑定在同一短事务中替换。

读取与每轮生成重新计算调用者 `subject_scope`。教师打开别人配置的智能体时，材料选择器只显示自己能访问的材料，不能用读出的隐藏 ID 重新绑定；更新 binding 是显式完整替换，页面提示替换范围，避免无意覆盖。响应不暴露未授权材料标题或内容。学生可使用本班所有学科，仍受当前授权判断。新 routes 的 class 参数不能覆盖 effective class；资源 ID 查询必带班级条件，统一错误为 `{"error":"resource not found"}`，权限写拒绝为 403。

替代方案：把本班全部材料交给教师，会违背当前 subject-scoped change；增加 owner-only 智能体权限又超出教程的本班教师共享语义。本设计只收窄材料访问，不改变学科授权体系。

### 2. 数据升级保留旧占位记录，不自动猜测归属

新增表及扩展：

| 表 | 关键字段与约束 |
| --- | --- |
| `tutor_agents` | id, class_id, name(64), prompt(2000), enabled, seed_key, created_by/updated_by, timestamps；unique(class_id,name)，种子键班内唯一 |
| `skills` | 保留 id/name；新增 class_id, trigger_text(120), description(2000), tools_json, source_text(8000), subject_text(32), enabled, seed_key, legacy_placeholder, audit/timestamps；unique(class_id,name)，种子键班内唯一 |
| `tutor_agent_skills` | agent_id + skill_id 联合主键；技能删除级联解绑 |
| `tutor_agent_materials` | agent_id + material_id(UUID string) 联合主键；材料删除级联解绑 |
| `conversations` | id, class_id, user_id, agent_id, title, created_at, updated_at；用户/班级/时间索引 |
| `messages` | id, conversation_id, role, content, citations_json, skill_name, completion_state, created_at；role 限 user/assistant，state 为 complete/interrupted；会话/序号索引 |

在初始化中加入 tutor schema migration，先检查旧 skills 列，再 `create_all()` 与完成约束升级。旧占位 skills 行保留 `class_id=NULL, enabled=false, legacy_placeholder=true`，不展示、不路由、不绑定；新 active 行要求非空班级与合法完整字段。避免按某一个班级猜填旧行。旧 `Assistant` 表继续保留，不复用为 tutor_agents。

`SEED_DEMO_DATA=true` 时用 class-local seed_key 幂等创建至少数学/语文「解题引导」样板及相应助手；默认角色不过度限制直接回答，以便观察技能开关差异。只绑定该班且符合种子教师学科权限的材料，不覆盖教师修改过的配置。不改写既有真实材料、向量或账号，也不把普通材料自动全绑到助手。重复启动、非演示启动与已有数据库升级都需单独测试。

替代方案：删掉旧 skills 再建表破坏历史与回滚；仅 `create_all()` 不会补列；把原 Assistant 当成班级智能体会引入归属猜测。

### 3. 接口采用现有 /api 前缀，成功与错误按真实契约文档化

| 方法与路径 | 输入 / 结果 |
| --- | --- |
| GET/POST `/api/classes/{class_id}/agents` | 列表；创建 `{name,prompt,enabled,skill_ids,material_ids}`，201 |
| GET/PUT `/api/classes/{class_id}/agents/{agent_id}` | 读取；整体更新配置，200；未提交绑定字段保留原关系，提交空数组清空 |
| GET/POST `/api/classes/{class_id}/skills` | 列表；JSON `{source_text}` 或 multipart UTF-8 `file`，创建201 |
| GET/PUT/DELETE `/api/classes/{class_id}/skills/{skill_id}` | 原文/解析字段读取；相同输入整体改写200；删除204 |
| GET/POST `/api/conversations` | 本人列表；`{agent_id}` 创建201 |
| GET `/api/conversations/{conversation_id}` | 会话、智能体摘要、有序消息与快照 |
| POST `/api/conversations/{conversation_id}/messages` | `{question}`；SSE。可忽略客户端 agent_id/class_id/history，不能改变关联或上下文 |
| GET `/openapi.json`、`/swagger/`、`/swagger/index.html` | 无需认证的文档；实际受保护操作仍需 Bearer |

统一输入检查类型、trim 后长度和重复名称；完整 binding 验证先于写入。无 agent_id 为 400（包括本班无可用智能体的友好提示）；指定非法 agent_id 为统一 404。停用智能体只影响选择，已有会话按会话关系读取当前配置。绑定材料无须在绑定时已就绪，但 UI 展示索引状态，回答时若该范围需要重建则返回503/code reindex_required。

不提供演示 JWT 的 `/api/login` 兼容别名；文档准确描述 `/api/auth/login`、access/refresh opaque tokens 和现有错误码。替代方案是照抄演示全部路由，代价是多套认证与前端路径，不能满足本仓库兼容性。

### 4. 技能解析与路由为独立纯逻辑，上传不触发执行

技能格式沿教程的中文键行，兼容 `:`/`：`、UTF-8 BOM 和 CRLF。元数据内 `#` 注释忽略；首个在已出现元数据后的空行标记正文边界，正文 trim 后不可为空；前导空行/注释可忽略。名称/适用条件/启用必填，资料/工具可省略；启用接受是/否，工具用相同分隔符切分后仅允许 knowledge_search。正文保留原始文本，不加载路径、URL、脚本或外部资源。解析失败不写数据库。

每次请求按技能 ID 升序读取 bound + enabled 候选，trigger 按 `[,，、;；|]` 切词、trim、casefold，再做子串计分；最高正分选一条，平分取小 ID，零分不选。metadata 指示的工具不决定是否跳过课程强制的先检索步骤；knowledge_search 只是受支持的声明。

名称含「解题引导」时追加服务端引导规则；技能说明包在有标识的文本边界内，明确上传内容不能覆盖权限和服务规则。确定性单测验证路由，真实模型审阅验证不泄露答案；不能宣称仅凭提示词已经机械证明“永不泄露”。若真实行为失败，修正提示词/模型设置并重验，未通过不得标记课堂验收完成。

替代方案：模型路由难复现，多技能拼接易冲突，标准 SKILL.md 与课程格式和服务端计分并不等价。

### 5. 为检索增加 material_ids，缺省和空集合语义不同

扩展 `retrieve(..., material_ids=None)`：None 保持旧接口全授权范围语义；空集直接返回无证据，不调用 embedding；非空白名单是服务端经过权限过滤后的材料 UUID。

该条件贯穿 `_ensure_compatible`、是否存在授权材料的检查、`_base_query`、词法/向量候选与句级门槛关联，不能先全班 topK 再滤，否则未绑定材料会挤掉正确结果或触发 unrelated reindex 错误。传递当前 class/subject 权限，不允许学生直接传白名单扩大范围。现有 profile、source-map、重复证据去重、句级门槛继续使用。

取最多4条后按技能 subject_text 对 material.title 做子串过滤，删除空正文，再连续编号。不将 RRF 得分当余弦相似度；向量阈值保持现有配置与真实评测结果，不另设教程示例阈值破坏检索。沿用 evidence/source spans 生成最多800字原文输入，保留 title/material/subject/chunk/generation/source hash/spans 作为消息引用快照。开启出处时用现有 material/chunk API 重新授权；索引换代或来源消失时保留历史标签并显示位置已不可用，不跳转到另一份内容。

替代方案：只在 `hits` 过滤成本小但不正确；重写检索会丢失第4课已验收的门槛。

### 6. 新增流式 provider 方法，不修改旧 JSON 回答

保持 `ChatClient.answer()` 和 `answer_question()` 原样契约，新增 `stream_tutor(messages)` 返回文本增量。OpenAI-compatible 请求使用原 `CHAT_*` 与 `/chat/completions`，`stream:true`，不使用旧 `response_format:json_object`；仅消费正文 delta，不把 reasoning、工具参数或 provider 原始错误推给客户端。生成有界，沿用2048输出token预算和服务端超时；provider 响应与连接在 finally 关闭。

新提示词组装按课程顺序：智能体角色或 fallback、当前技能与引导限制（或未命中直接回答）、有/无证据的编号规则、不介绍模型身份、上传数据边界。历史取最新6条非空 user/complete assistant，每条500字；最后一个当前 user 内容替换为“编号资料 + 本轮问题”，不能再附一次重复提问。历史助手文本是非可信上下文，不能携带新的系统角色。

无 evidence 仍调用此方法，要求不得捏造出处；deterministic 模式提供逐段 fixture 响应并显著标注为演示，不能用其证明真实引导行为。逐块有状态 citation filter 暂存可能跨块的 `[digits]`，无引用则删除，有引用仅放行范围内数字；超过最大合法编号长度的纯数字前缀进入丢弃状态，直到右括号或非数字边界，不原样flush，避免无界缓冲与越界编号泄漏。非编号方括号文本正常保留。只对清洗后增量累积正文，保证 delta 拼接等于落库 content。

课程流式返回的 citations 是检索证据列表，在 meta 即固定，不承诺全部被正文使用，也不执行旧 JSON claim/quote 校验；准确编号与权限强制执行，实际支撑与解题引导通过真实人工审阅验收。

替代方案：先用旧 JSON 验证整段再切片会失去首字延迟和真正流式，且不能实现无依据角色回答。

### 7. 短事务、跨 worker 锁与明确流状态

PostgreSQL 使用独立连接上的 session advisory lock，以 conversation ID 加 tutor 命名空间生成锁键，非阻塞获取；同会话第二请求409，不插入问题。锁在 finally 释放，进程死亡连接释放；不把锁事务延伸到外部模型调用。SQLite 单元测试用受控进程锁，跨 worker 保证必须在 PostgreSQL 多worker验收。不同会话互不锁住。

顺序：校验 auth/会话/agent/问题 → 获取锁 → 读取当前配置并选技能 → 短事务保存 user、首轮 title/updated_at → 检索与输入预检查 → 再核验授权/来源 → `meta` → provider正文增量与清洗后的 `delta` → 短事务保存 assistant complete → `done`。user 落库后检索失败保留问题，不伪造 assistant 成功。配置按轮读取，老师改绑定影响下一轮；当前授权若撤销则终止后续输出，回放与引用打开同样重新授权。

正常流：

```text
event: meta
data: {"status":"ok","skill":{"id":1,"name":"数学解题引导"},"citations":[...],"demo_mode":false}

event: delta
data: {"text":"先检查括号外的系数是否乘到了每一项。[1]"}

event: done
data: {"message_id":42}

```

`skill` 可为null，citations 可为[]。每帧 UTF-8 JSON、双换行；Flask generator 每 yield 一帧；Content-Type text/event-stream、Cache-Control no-store、X-Accel-Buffering no。鉴权/输入/资源/并发/检索失败在首帧前返回真正4xx/503。一旦 meta 发出，包括首个模型字符前失败，都只能返回200流内 error；教程 answer 页“首片前503”与“meta后不能改状态码”冲突，本设计以首个SSE帧为边界。

有部分已发正文时，故障或客户端取消在 finally 尝试保存 assistant interrupted 的已清洗内容与原 meta 快照，不发送成功 done；无正文不写成功 assistant。数据库不可用时不能承诺保存，error/UI标为未保存。EOF没有done也算中断。中断文本保留回放，但不进入下一轮模型历史。无自动重连/续传/POST重试；用户重新打开历史后主动继续。

替代方案：只靠 JS disable 挡不住两个标签页，进程内锁挡不住 Gunicorn 多worker；整轮数据库事务会长期占锁。

### 8. 模型、后端、代理、浏览器均须流式

`frontend/server.py` 为上游请求设置 stream=True，根据 Content-Type 分支，用 generator 转发 `iter_content` 的小块并 `close`，不读取完整 content；普通JSON和文件响应保持既有行为，排除原 hop-by-hop 和set-cookie头。`/openapi.json` 和 Swagger 静态资源/页面明确代理或服务，不走只匹配 `/api` 的默认路由。两端使用少量 gthread workers/threads；测试同时多个会话和普通健康/检索请求，避免所有worker被流耗尽。

浏览器用 `CampusAuth.apiFetch` 发POST、ReadableStream + TextDecoder streaming + SSE帧缓冲，支持任意字节切分、CRLF、半个Unicode和一块多帧；不使用只能GET且不能自定义Authorization的EventSource。UI以request revision避免切换会话后旧流混入，AbortController取消离开页面的流。结束、error、EOF、401有各自状态，不自动重放POST。

桌面布局参考原型：侧栏智能体/最近对话，中心会话，底部输入，回答旁显示技能与引用。沿用现有浅色/CSS工作区和角色入口，不创建错题本等假功能入口。教师配置页使用source editor/文件上传与多选binding，材料状态与权限明确。生成文字通过textContent安全渲染，引用复用原文预览组件；窄屏侧栏收起，键盘focus和状态live region完整。

替代方案：只改浏览器解析解决不了代理缓冲；引入Nginx/React增加当前课程外的部署和前端迁移。

### 9. 处理器注解是 OpenAPI 来源，Swagger 资产同源

使用轻量 `@api_doc(...)` 元数据注解 + 注册后Flask url_map生成器；注解显式 request/response schemas、roles、errors、operationId。生成器把Flask参数转换为OpenAPI路径并核对实际methods，生成错误时测试失败。元数据先覆盖任务要求的 auth/material/retrieve/ask 和全部新增路径；不要求为本change外的每个管理接口新增脚本。Bearer scheme 为 HTTP bearer，不标记 JWT，也不改既有401/403/404/429契约。

固定版本、带来源/许可记录的 Swagger UI dist JS/CSS作为同源静态资产；初始化脚本外置，关闭持久保存Authorization，在现有 `script-src 'self'` 下验证。Python侧不为生成文档额外引入第二个API框架。Swagger用于普通试调；SSE operation文档提供完整事件schema与fetch/curl -N示例，UI自身若缓冲不计为端到端流式证据。

替代方案：手写一份openapi.json易漂移；CDN和inline初始化不满足当前CSP。

### 10. apitest 测真实 HTTP + 只读数据库，不触碰开发库

新增独立Compose test stack（专用project、tutor_test PostgreSQL/tmpfs、独立上传store、专用测试端口、可控流provider），参考现有 retrieval-test 环境，不依赖当前5174开发数据。runner先验证环境标识、test数据库名和测试base URL，缺一拒绝fixture reset。fixtures统一准备学生、同班不同用户、外班用户、教师授权与材料；测试密码来自专用fixture，真实密钥仅本机.env。

`apitest/cases/api/auth/login/POST.py`、`.../classes/{class_id}/knowledge/retrieve/POST.py`、`.../classes/{class_id}/agents/POST.py`、`.../conversations/{conversation_id}/messages/POST.py`等按实际URL组织，一operation一脚本，可含正反场景。公共helpers提供HTTP、SSE增量计时、SQL只读assertions和redaction，run_all.py动态发现、执行、继续收集故障、非零退出及生成HTML；`apitest/reports/`忽略。状态码、正文schema、DB side effects、hash而非明文令牌、negative no-write、delta==DB/citation snapshot==meta都要断言。

fixture SSE至少两个可控延迟delta，在首块到达且provider未完成时记录时间；浏览器测试通过web端口验证同样条件。真实provider单独审阅数学去括号/分数和语文古诗/阅读，比较启停/解绑技能、空prompt、无bound material和检索落空。真实审阅不能被fixture或skip替代。交叉验证记录明确peer身份、环境、时间与脱敏证据；实际同伴证据没有取得时保留pending任务，不自动声称完成。

## Risks / Trade-offs

- [prompt-only guidance不能机械保证最终答案不泄露] → 单轮规则优先级、代表性真实审阅和反例验收；发现泄露必须修正并重验，不把fixture通过算完成。
- [长连接占线程和DB锁连接] → 小规模gthread、专用advisory锁连接及时释放、限制provider超时，验收并发与健康请求。
- [技能或绑定共享维护可能覆盖其他教师配置] → 显式完整替换语义、权限过滤、保存反馈和维护人记录；本课不引入新的owner模型。
- [流式已展示内容无法撤回；引用不等于语义支撑] → 发送前编号清洗和当前授权校验，清楚标记中断与引用性质，真实支持审阅。
- [旧skills缺归属且db.create_all无法补列] → 单独幂等迁移、legacy禁用保留、升级前备份与重复启动测试。
- [现有semantic_release报告只验证旧问答] → 新流式引导验收记录独立，不覆盖或冒用既有报告。

## Migration Plan

1. 在隔离SQLite/PostgreSQL fixture验证旧schema升级、legacy占位、约束、重复启动、删除解绑与demo幂等；运行既有认证/学科/检索/问答回归。
2. 在隔离完整web入口验证注解生成、Swagger、所有apitest、真实SSE并发、故障和浏览器状态；完成真实provider人工审阅与同伴证据。
3. 实施阶段部署前按现有备份流程保存数据库和上传卷，核对运行配置；新增表与列为加法升级，不重建现有索引，不改变模型/profile或认证令牌。
4. 更新api/web服务并验证登录、材料、原单次问答、新配置与流式会话。保留当前对话和历史，不在部署中reset种子数据。
5. 回滚优先恢复上一版api/web镜像并关闭新入口，保留新增表/列和旧问答功能；不删新增会话。如需恢复升级前数据库，必须另行确认可接受丢失升级后的写入，不能自动执行破坏性恢复。
