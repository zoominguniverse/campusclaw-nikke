# 第6课 MCP 实施与验收记录

日期：2026-10-21（Asia/Hong_Kong）。Change：`add-mcp-tool-integration`。

实现、机器验收、五组真实 CHAT 样例验收及实际同伴交叉验证完成，OpenSpec 43/43。2026-10-27 用户明确确认同伴实际复核完成、结果正确，并要求简化为用户确认记录。未归档、未提交 Git、未更新 5174 开发服务。第5课 change 仍为 43/45，原质量/同伴待办保持原状。

## 已交付行为

同仓 MCP 服务提供固定 JSON-RPC 子集及两个只返回提示的工具。教师按班级登记、加密保存令牌、连接发现并审阅完整声明；技能持有声明指纹及配置版本确认。模型在命中技能的工具集合内自主选择工具和参数，可根据上一轮结果继续调用，也可不调用。宿主在每次远端调用前重新授权、校验参数、预留持久化配额并记录意图；结果经过限量、脱敏和数据边界处理后交回模型，最终正文继续使用原流式通道。

消息、审计及会话累计计数持久化。前端合并重复 meta，展示工具结果与错误，并在刷新或中断后恢复历史。删除服务器保留审计名称快照。配置或声明变化需要重新确认；配置变化也清空界面上尚未提交的审阅。教师 MCP 区独立加载，学生无管理入口。服务器删除使用可键盘操作的页面确认框，支持 Escape 取消和焦点恢复。

## 机器验收

| 验证 | 实测结果 | 范围与限制 |
| --- | --- | --- |
| 后端完整回归 | 249 passed，22 skipped | SQLite、实际本机 HTTP、原权限/检索/流式用例；条件跳过不计为成功 |
| 隔离 PostgreSQL | 18 passed，1 skipped | `quality_mcp`：新增约束、旧库迁移两次、连接竞态、配额持久化及既有检索/流式；旧源码目录回滚用例跳过，另外执行了下述不可变镜像演练 |
| 前端 Python + MCP 服务 | 16 passed | 前端7项，工具服务9项 |
| Node 流与状态组件 | 两套均通过 | UTF-8 每个字节边界、重复 meta、CRLF、EOF、错误、迟到 meta 拒绝及 call_id 合并 |
| 完整接口 runner | 36/36 PASS，退出0 | Swagger operation 清单一致；HTTP→真实 MCP→模型 fixture→SSE→审计/消息数据库断言 |
| runner 负例 | 36项通过 + 1项有意失败，退出1 | 仍生成 HTML；负例报告保留在忽略目录 `apitest/reports/negative.html`，正常结果在 `latest.html` |
| 真实 CHAT 五组样例 | 5/5 完成并审阅 | 用户已授权；DeepSeek 实际不调用、选择工具/参数、两轮依赖、错误令牌失败、轮次预算结束；最终辅导未给最终答案，见 [真实模型复核](real-model-review.md) |
| 实际同伴四项复核 | 完成，用户确认结果正确 | 2026-10-27 按用户指示简化为确认记录；未另存同伴姓名、截图或原始请求响应，见 [同伴复核](peer-review.md) |
| 主 Compose 独立烟测 | 通过 | API 容器 initialize/list/两种 call；无令牌401；停止 MCP 后 API health200、原材料路由401仍保留 |
| 密钥与报告扫描 | 通过 | 本地比对私有凭据，不输出值、不传给扫描容器；三个镜像 history 与 `/app` 文件、前端/工具源码及报告无实际密钥；扫描容器禁用网络 |
| OpenSpec | strict validate 通过 | 仅按实际证据勾选完成项 |

后端回归包含：模型零/多提议与两轮依赖、调用ID关联、坏协议/超大响应、伪造别名/非法参数、每问/会话/时间预算、失败消耗配额、两轮之间断开/撤权、意图/终态存储故障、密钥回显与中英文注入、伪引用、零正文和部分正文失败。PostgreSQL 的 connect 对 disconnect/update/delete 竞态确认旧发现不能重新发布缓存。

接口报告含实际请求响应与数据库断言，已脱敏并由 `.gitignore` 忽略。`git check-ignore apitest/reports/latest.html apitest/reports/negative.html` 两者均匹配。受控决策服务通过真实 HTTP 提出工具调用，工具服务和数据库都是真实进程；这证明协议与宿主行为，不能证明真实模型的工具选择和教育质量，也不能代表实际同伴参与。

## 浏览器实测

Chrome 访问独立 `http://localhost:5284`，仅用隔离 fixture 账号。

- 教师登记 `ui_school`，提交后密码输入清空；连接发现、完整 schema/指纹审阅、加入技能引用、绑定智能体。断开/相同声明重连后原确认可用。再次提交配置后旧绑定失效，旧审阅被清空，保存显示 `binding_review_required`；重新勾选两项后保存成功。
- 另建错误令牌服务器 `ui_bad`，连接显示 `remote_unauthorized`，原智能体/技能仍可配置；Escape 取消删除，再用 Tab/Enter 确认删除，记录从列表移除。本班审计能读取 ok/denied 及原因。
- 学生选 `UI工具助手` 发送“MCP括号和单位，两轮工具检查。”，工具结果先于正文显示，重复 meta 不产生重复消息。恶意 `<script>` 作为文本展示；没有材料时没有伪来源编号。
- 实际发送取消验收请求，在首段后点击“停止生成”，重新打开历史显示“回答已中断”，两项工具结果保留；390×844 窄屏可读。键盘 Ctrl+Enter 发送及删除确认框 Escape/Tab/Enter 已操作。
- 学生直达 `/tutor-config` 显示只有任课教师可以维护配置，无管理表单。
- Swagger 浏览器真实试调：登记 `swagger_school` 返回201 → connect200 → tools200（完整两项声明）→ 携带两项 declaration_hash 保存技能201，两个 binding 均为 ready。登录凭据和 Bearer 没有写入证据；文本中的 Authorization 已替换。

浏览器证据：

| 文件 | 内容 |
| --- | --- |
| [tutor-desktop.png](tutor-desktop.png) | 桌面两轮工具状态、正文和 HTML 作为文本展示 |
| [tutor-narrow-interrupted.png](tutor-narrow-interrupted.png) | 390×844 中断历史恢复 |
| [student-no-management.png](student-no-management.png) | 学生无管理入口 |
| [teacher-review-invalid.png](teacher-review-invalid.png) | 配置变化后的旧绑定失效反馈 |
| [teacher-declarations.png](teacher-declarations.png) | 完整参数声明、指纹及正常尺寸复核控件 |
| [teacher-connect-failure.png](teacher-connect-failure.png) | 连接失败时其余配置保留 |
| [swagger-tools.txt](swagger-tools.txt)、[swagger-skill.txt](swagger-skill.txt) | Swagger 浏览器实际响应，Bearer 已脱敏 |

## 升级与回滚

[rollback.json](rollback.json)：从 `mcp_test` 用 pg_dump/pg_restore 复制到新 `mcp_rollback`，升级两次，再运行已有旧 API 镜像 `f3223cd7d429` / Web 镜像 `f4cdac11e39b` 及关闭 MCP 的新 API。原健康、认证、检索和历史均200；14张材料、向量、身份/成员关系、对话/计数/快照和 MCP 表的内容摘要不变。正常登录按原契约签发/撤销会话，认证事件不被假定完全不变。副本保留，脚本拒绝覆盖已有 `mcp_rollback`。

旧 parser 无法保存 `@` 引用，旧 Web 不展示工具栏；保留新列/表和技能导出，重新升级可以恢复。操作说明及备份要求见 [迁移文档](../mcp-migration.md)。主 Compose 停服烟测见 [main-compose.json](main-compose.json)，最终镜像扫描见 [secret-scan.json](secret-scan.json)。

## 复现入口

```powershell
docker compose -f docker-compose.mcp-test.yml up -d --build mcp-postgres mcp-demo mcp-provider mcp-api mcp-web
docker compose -f docker-compose.mcp-test.yml run --rm mcp-apitest
docker compose -f docker-compose.mcp-test.yml run --rm mcp-apitest --inject-failure
node frontend/tests/test_tutor_sse.cjs
node frontend/tests/test_tutor_tools.cjs
openspec validate add-mcp-tool-integration --strict
```

正常 runner 在负例之后再运行一次，可恢复 `latest.html` 为全通过报告。重复 runner 使用唯一测试资源名，不重置库。独立项目及 runner 的 URL/数据库/只读角色预检见 [apitest 说明](../../apitest/README.md)。浏览器5284；本机5178被 Windows 保留，未占用开发5174。

本次完整 Python 回归在已安装项目依赖的 Python 3.14 环境执行；PostgreSQL 使用独立 `quality_mcp` 库及 `QUALITY_DISPOSABLE_DATABASE=true`，测试会重建该测试库的 public schema。不可指向 `mcp_test` 或开发库。独立主 Compose 烟测脚本为 `backend/evaluation/mcp_main_smoke.py`，只清理它新建的 `campusclaw-mcp-main-smoke` 项目。

## 后续验收完成记录

10.2：初次外部请求因缺少对应明确授权被自动审批拒绝；随后用户明确允许这5组真实模型验收，已执行并审阅通过。只读核对确认 SSE、DB审计、消息快照和计数一致，脱敏证据见 [real-model-review.md](real-model-review.md)。没有把 fixture 结果当作真实 CHAT 结果，也没有将这5组推论为所有主题的质量保证。

10.3：2026-10-27 用户明确确认“同伴实际复核完成 我确认结果正确”，并要求简化验收留档。同步调整本 change 的验收约定，以该确认记录接受四项实际同伴复核，不再强制另交同伴姓名、截图或原始请求响应，本项完成。四项自动权限/隔离测试不替代同伴交叉验证。记录见 [peer-review.md](peer-review.md)。
