# AI 应用能力与 LLM 请求核验

核验日期：2026-10-27（Asia/Hong_Kong）。代码基线：`dfcc8c4`。本次完成代码核查、正常运行环境只读核查、经用户明确授权的一次真实聊天调用和一次问题向量化调用，以及现有 MCP 真实模型验收记录的本地复核。

后续实施：同日已新增课堂应用和带变量的提示词模板，并在主环境启用 MCP、完成两组真实工具对话；当前运行状态见[新的启用验收记录](../classroom-mcp-acceptance/README.md)。下文和 JSON 保留本次早先核验时的原始状态，不回写旧采集数据。

## 功能覆盖情况

| 要求 | 当前实现与运行状态 | 核验结论 |
| --- | --- | --- |
| 内置多个 AI 应用 | 正常库有 6 个启用智能体，三班各有语文、数学解题助手；分别绑定技能和材料 | 已具备两类内置应用，可新增智能体 |
| 提示词模板 | 教师可配置每个智能体的角色提示词，空值使用内置默认提示；当前 6 个智能体均为空值 | 具备角色提示词配置；尚无独立的可复用模板库、变量插值或模板版本管理 |
| 知识库检索 | 班级和学科权限内的关键词、向量、混合检索；流式会话进一步限制到助手绑定材料 | 已实现，本次真实调用返回 1 条证据 |
| 内置及上传 Skill | 内置语文、数学技能；教师可粘贴或 multipart 上传 UTF-8 中文格式技能文件 | 已实现；本次离线复核 3 份样板解析及路由行为，未向正常库新增上传记录 |
| 外部工具及 MCP | 实现受控只读 HTTP JSON-RPC 工具、发现确认、技能绑定、模型多轮选择、宿主执行和审计 | 代码已具备，历史有真实模型验收；当前主环境 `MCP_ENABLED=false`，服务器登记数为 0，当前环境尚不能使用 MCP |

“提示词模板”若只要求保存和使用角色提示词，现有实现可满足；若要求独立模板库或 `{{变量}}` 替换，不能将该能力标为全部完成。本项目 Skill 是课程自定义中文文本协议，不是任意脚本包或任意格式的 SKILL.md 安装器。MCP 为文档声明的 HTTP JSON-RPC tools 子集，不承诺 stdio、resources、prompts 或任意第三方服务的完整互通。

## 1. 一次对话实际传给 LLM 的内容

聊天接口：`POST https://api.deepseek.com/chat/completions`。本次实际请求字段为：

```json
{
  "model": "deepseek-flash",
  "messages": [
    {"role": "system", "content": "默认或自定义角色提示词 + 命中技能名称和完整正文 + 平台约束"},
    {"role": "user", "content": "资料（仅数据）：\n[检索证据JSON]\n本轮问题：问题原文"}
  ],
  "stream": true,
  "max_tokens": 2048,
  "reasoning_effort": "none"
}
```

上例用说明性文字缩写了 `content`。完整、未经缩写的实际参数见 [2026-10-27-chat-request.json](2026-10-27-chat-request.json)。Authorization 使用服务端 API key，留档时替换为 `[REDACTED]`；没有显式传入 temperature 或 top_p。

**提示词会一并传递。** 当前实际 system 为 704 个 Unicode 字符，包含默认校园学习助手角色、87 字数学技能正文、单步引导与引用约束。若教师设置 `agent.prompt`，该完整值替代默认角色后再拼接技能和平台约束。没有单独的 `prompt_template` 接口参数，也没有模板变量渲染过程。

普通后续对话还会在 system 与本轮 user 之间加入服务器读取的最近 6 条有效历史，每条最多 500 字符；中断的 assistant 回答不进入该窗口。每次重新组装 messages，不依赖模型供应商保存会话。当前问题只出现一次，客户端自带的 system/history 不作为受信历史使用。本次以不存在的负数会话 ID 读取空历史，未读取其他人的历史。

LLM 返回 `text/event-stream`，正文位于每个 `data:` JSON 的 `choices[0].delta.content`，正常结束包含 `finish_reason: "stop"` 和 `data: [DONE]`。本次实测原始返回为：

> 先不用急着算这道方程，你第一步要做的，是把题目里的等号两边分别圈出来，确认哪一边有括号、哪一边有分数。
>
> 先看1班材料里这句话：“1 班数学示例材料内容”[1]。你现在卡在哪一步：是去括号没把握，还是分母不同没把握？

原始流帧见 [2026-10-27-normal-turn.json](2026-10-27-normal-turn.json)，拼接正文见 [2026-10-27-chat-answer.txt](2026-10-27-chat-answer.txt)。已逐帧重建并确认与拼接正文一致。真正走会话 HTTP 路由时，平台另外包装成 `meta → delta → done`，MCP 可以增加正文前的 meta，失败可以返回 error；这些平台事件不是直接传给 LLM 的请求参数。

本轮材料只有占位文本，问题也未给出具体方程；模型仍使用了“这道方程”等措辞。因此本例证明参数、引用传递和流接收链路，不能据此认定教学内容质量通过。

## 2. 绑定知识库后是否每次发送全库

**不会固定发送全部知识库。** 流式会话先取助手绑定材料与当前班级、学科权限的交集，再针对本轮问题进行混合检索，最多取 4 条；命中 Skill 的“资料”字段还可以按材料标题进一步过滤。每条实际进入提示词的原文片段合计最多 800 字符，即最多约 3200 字符证据正文，另有标题、编号、偏移等元数据。

本次 user 消息中的证据部分实际为：

```json
[
  {
    "index": 1,
    "title": "1 班数学示例材料",
    "source_segments": [
      {"start": 0, "end": 11, "text": "1 班数学示例材料内容"}
    ]
  }
]
```

该材料原文仅 11 字，因此这次命中的一个片段恰好覆盖它的全文。这与“每轮发送所有绑定文档、整个班级知识库”不同。短文档被完整检索到时，不能笼统宣称“任何文档都不会全文发送”。

问题向量化另调用已配置的阿里云兼容接口，请求仅为 `{"model":"text-embedding-v4","input":["本轮问题"]}`，本次返回一条 1024 维向量。向量用于数据库召回，没有放入 DeepSeek 的 messages。上传和重建时，材料切片会分批交给 embedding 服务生成索引；这不属于每轮对话重复发送全库。

如果没有绑定材料或没有命中，流式辅导允许发送空证据并提供无引用的一般学习帮助。独立的 `knowledge/ask` 则保持无证据不调用 chat、直接返回固定提示的规则。它也最多使用 4 条检索证据，但使用独立的结构化问答协议，不能套用流式会话每条 800 字符的输入上限。

## 3. 绑定 Skill 后是否发送全部技能文件

**绑定不等于每轮选中，也不等于发送原始文件全文。** 每轮只从当前助手已绑定且启用的技能中选至多 1 条：

| Skill 内容 | 处理方式 |
| --- | --- |
| 名称 | 命中后以“当前技能”写入 system |
| 空行后的正文 description | 命中后完整写入 system，最长 2000 字符 |
| 适用条件 | 宿主用于本地关键词路由 |
| 资料 | 宿主用于过滤检索材料标题 |
| 工具 | 宿主用于选择内置检索语义或 MCP 候选工具 |
| 启用 | 宿主用于本地启停判断 |
| 原始 source_text、注释与格式 | 保存供配置和编辑，不整体拼进 messages |

本次数学技能原始文件为 161 字符，正文为 87 字符。已检查实际请求：87 字符正文完整存在于 system；161 字符原文件未整体存在于 messages。其他绑定技能不会全部拼接发送。

## 4. Skill 的执行逻辑

1. 教师提交 UTF-8 文件或 source_text，解析名称、适用条件、资料、工具、启用和正文；验证必填、长度、重复字段与工具格式。带 MCP 引用时还验证本班服务器、连接、发现清单和声明确认。
2. 每轮读取助手当前的绑定和启停状态，不沿用上轮已选技能。
3. 将适用条件按中英文逗号、分号、顿号及竖线拆词，对问题做大小写归一化后按子串命中计分。
4. 只在已绑定、已启用且非占位的技能中选最高正分者；同分取较小技能 ID；全为 0 则不选技能。
5. 在授权绑定材料内检索，再应用技能资料标题条件。将角色提示词、技能名称与正文、证据和有界历史拼成模型请求。
6. 名称包含“解题引导”时，宿主追加每轮一步、不给最终答案、不虚构学生进度等限制，由 LLM 按提示词生成正文。宿主处理引用范围、流状态与持久化。
7. 命中的技能有 MCP 引用时，进入后述工具阶段。`knowledge_search` 保持内置检索含义，不作为远端函数再次交给模型。

因此普通 Skill 的“执行”是**宿主路由和组装提示词，LLM 按说明生成**。上传技能不会直接执行 Python、Shell 或任意代码。离线检查确认：三份内置样板可解析，停用技能不参与选择，同分按 ID 决定，无关键词命中返回空选择。

## 5. MCP 接入后的具体请求

当前主环境没有启用或登记 MCP，本次没有新建服务器、工具绑定或执行新的 MCP 实测。以下协议由当前代码核对，并以仓库保留的 [2026-10-21 五组真实模型记录](../mcp-acceptance/real-model.json)及[审阅说明](../mcp-acceptance/real-model-review.md)交叉复核；历史验收不等同于当前环境已启用。

**阶段一：模型决定工具。** 发到同一 chat/completions 接口的 JSON 为：

```json
{
  "model": "deepseek-flash",
  "messages": [
    {"role": "system", "content": "角色、技能、平台约束，以及工具决策阶段说明"},
    {"role": "user", "content": "检索证据和当前问题"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "mcp_12_formula_hint",
        "description": "给出去括号、移项或公式选择的下一步检查提示，不给出题目最终答案。",
        "parameters": {
          "type": "object",
          "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 500}},
          "required": ["query"],
          "additionalProperties": false
        }
      }
    }
  ],
  "tool_choice": "auto",
  "stream": false,
  "max_tokens": 2048,
  "reasoning_effort": "none"
}
```

这是说明性示例：实际历史声明同时有 formula_hint、unit_convert，messages 及每次参数详见原始记录；上例的服务器 ID 12 来自历史验收。只传入命中技能已确认的工具声明，不传整个服务器工具目录。MCP 服务器 URL 和 MCP 令牌不进入该 JSON。

模型可返回空工具列表，也可在 `choices[0].message.tool_calls` 中返回 `id`、`type:function`、`function.name` 和 JSON 字符串形式的 `function.arguments`。arguments 由模型选择，工具名出现于用户文本不构成自动执行。

**阶段二：宿主执行。** 宿主重新检查会话、角色、班级、技能绑定、声明和部署策略，验证参数 schema，再向已登记 MCP 服务发请求：

```json
{
  "jsonrpc": "2.0",
  "id": "宿主生成的请求ID",
  "method": "tools/call",
  "params": {"name": "formula_hint", "arguments": {"query": "模型提出的具体问题"}}
}
```

该请求发给 MCP 服务的 `/mcp`，使用另一个服务端 Bearer 凭据，与 LLM 供应商请求不同。结果经长度限制、脱敏及已知指令载荷过滤后回传模型。后续决策 messages 增加原 assistant.tool_calls 及对应的：

```json
{
  "role": "tool",
  "tool_call_id": "对应模型调用ID",
  "content": "{\"ref\":\"formula_hint@school\",\"status\":\"ok\",\"text\":\"经过处理的提示文本\"}"
}
```

模型可以据此请求下一轮工具。已复核历史 dependent 样例：先请求 formula_hint，再携带它的结果请求 unit_convert，第三次决策不再调用工具；第二、第三次决策分别含 1、2 条 tool 消息。

**阶段三：生成正文。** 宿主另发普通流式请求，参数回到 `model/messages/stream:true/max_tokens/reasoning_effort`，不携带 tools 或 tool_choice。最终 user 数据段追加有来源标签的工具结果，不把全部中间决策消息原样塞进最终正文请求。

默认限制为工具阶段最多 3 轮、每问最多 16 个提议/6 次远端尝试、每会话累计 30 次远端尝试、工具阶段 20 秒、单次远端 5 秒。每个结果最多 1200 字符、合计最多 4800；失败消耗已预留的远端配额。工具失败会明确展示状态并尝试继续普通辅导。

一次用户提问因而可能产生多次 LLM 请求；“一轮对话只会调用一次模型”在 MCP 场景不成立。默认最多 3 次工具决策，再进行 1 次流式正文生成，另有可能发生的问题 embedding 请求。

## 留档与边界

- [核验摘要](2026-10-27-verification-summary.json)：实际请求字段、Skill 与证据长度、SSE 一致性、业务记录数量与历史 MCP 复核结果。
- [完整实际交互](2026-10-27-normal-turn.json)：问题 embedding 参数与返回向量、聊天参数、逐帧响应、Skill 原文及正文对照。
- [实际聊天请求](2026-10-27-chat-request.json)与[实际模型回答](2026-10-27-chat-answer.txt)：便于逐项查看。
- [采集脚本](capture-normal-turn.py)：在独立进程复用主服务的 prepare_turn/stream_tutor，不经过浏览器或新增会话 HTTP 路由；会真实访问已配置的外部模型，重新运行需要相应数据与出站授权。

本次业务库使用只读事务，会话、消息、技能、智能体数量前后均为 0、0、7、6（7 条技能中有 1 条旧占位记录）；没有新增会话、上传、绑定或审计。当前 6 个有效技能和 6 个助手保持原状。历史 MCP 记录保持原文，本轮没有重新执行其中五组外部调用。

代码依据：角色与资料组装见 [tutor_context.py](../../backend/app/tutor_context.py)，Skill 解析/路由见 [tutor_skills.py](../../backend/app/tutor_skills.py)，文件接收与会话路由见 [tutors.py](../../backend/app/tutors.py)，流式提供方参数见 [tutor_stream.py](../../backend/app/tutor_stream.py)，工具决策见 [tutor_tool_decisions.py](../../backend/app/tutor_tool_decisions.py)，多轮编排见 [tutor_tools.py](../../backend/app/tutor_tools.py)，远端协议见 [mcp_client.py](../../backend/app/mcp_client.py)。独立短问答参数见 [providers.py](../../backend/app/providers.py)：`stream:false`、`response_format:{"type":"json_object"}`，返回 claims 与精确引用校验后的短回答，与新增流式会话契约不同。
