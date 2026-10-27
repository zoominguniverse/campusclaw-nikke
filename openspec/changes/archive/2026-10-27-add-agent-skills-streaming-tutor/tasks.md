# Tasks

以下为实现阶段任务，勾选项已完成对应实现与验收。按组依赖推进，每组同时交付对应测试与文档。参考六份 delta specs 的场景与 `design.md` 的接口、升级和流式状态决策。

## 1. 数据模型与幂等升级

- [x] 1.1 在 `backend/app/models.py` 增加智能体、两张绑定表、会话与消息模型并扩展 Skill；通过 schema 测试确认班内唯一、UUID材料外键、消息role/state约束和必要索引。
- [x] 1.2 在初始化流程实现 tutor schema 的 prepare/finish 幂等迁移与版本记录；用旧 id/name skills 数据库执行两次升级，确认占位记录保留、禁用、无归属且不可查询为有效技能，新建数据库也成功。
- [x] 1.3 更新演示种子为带幂等键的数学/语文解题技能和助手，保留原 Assistant 占位；重复启动验证不重复、不覆盖教师编辑，非演示模式不插入演示配置。
- [x] 1.4 为材料删除接入绑定级联清理；SQLite与PostgreSQL验证删除后无悬空绑定，既有材料/切片/向量删除测试仍通过，历史引用快照保留。
- [x] 1.5 编写 tutor 数据升级与回滚说明，记录旧占位策略、备份步骤、非破坏性回滚；对照隔离升级测试确认步骤和实际schema一致。

## 2. 文档与接口测试基础设施

- [x] 2.1 建立处理器 `api_doc` 元数据注解和 OpenAPI 生成器；测试实际路由/method匹配、参数转换、重复operationId、遗漏主要接口和schema错误能被检测。
- [x] 2.2 为已有 auth login/refresh/logout/me、材料 list/upload/detail/download/reindex、knowledge retrieve/ask 添加注解；生成文档并核对真实Bearer/角色/输入/响应/错误，不引入JWT或路径别名。
- [x] 2.3 实现 `/openapi.json`、`/swagger/` 与 `/swagger/index.html` 及固定版本同源Swagger资产/外置初始化；浏览器在当前CSP下能加载并试调登录与检索，Authorization不持久保存，资产来源许可可查。
- [x] 2.4 建立 `apitest/run_all.py`、case发现、HTTP/SSE/只读DB helpers、脱敏HTML报告和忽略规则；样例用例成功及失败时均有报告、退出码正确，凭据不出现且 `git check-ignore` 确认报告被忽略。
- [x] 2.5 新增专用Compose tutor测试环境与fixture，使用独立PostgreSQL/upload store和可控流provider；runner预检查拒绝指向开发库，核对不会访问当前开发数据库或重置其数据。
- [x] 2.6 添加按实际URL组织的登录和检索脚本，并交付 `apitest/README.md` 的一键命令；运行核对响应schema、令牌hash/会话DB记录、班级与学科命中、401/跨班负例和报告内容。

## 3. 技能文本解析与班内管理

- [x] 3.1 实现中文技能文件parser与字段/长度/tool校验，保留source_text；单测覆盖BOM/CRLF、两种冒号、注释、缺字段/重复/未知字段、缺正文、非法工具、长度边界和原文回读。
- [x] 3.2 实现skills列表、详情、JSON或multipart创建/改写与删除，添加注解；接口及DB断言验证教师写权限、同班唯一400、外班与不存在404同体、学生403及拒绝写不变。
- [x] 3.3 实现确定性技能route；单测覆盖所有分隔符、casefold、平分小ID、零分不选、未绑定/停用不参与和每次更新重新读取。
- [x] 3.4 添加skills各method的apitest脚本，含技能删除解绑断言；通过一键runner并核对HTML报告中的解析错误、数据一致性与无部分写入。
- [x] 3.5 交付可上传的数学/语文技能样板与教师编辑说明；用实际parser加载两个样板，文档明确本项目格式、工具含义及解题引导验收限制。

## 4. 智能体配置与绑定权限

- [x] 4.1 实现agents列表/详情/创建/更新及名称prompt约束和空prompt fallback，添加注解；测试学生只见enabled、教师可见disabled、班内唯一、管理员不继承teacher权限、外班与不存在404同体。
- [x] 4.2 实现技能/材料binding整组验证与短事务替换，复用current subject_scope；测试空集合、混合合法/外班/未授权ID、拒绝后全部DB状态不变及省略字段保留关系。
- [x] 4.3 对agent读响应和材料选择器提供当前授权过滤，加入维护人/时间信息；验证教师不能读取或重新提交未授权材料内容，subject撤销后访问收窄。
- [x] 4.4 添加agents各operation的apitest与配置接口说明；一键runner校验响应绑定与关联表一致，Swagger可创建和修改agent且文档与真实请求一致。

## 5. 私有会话、消息与上下文

- [x] 5.1 实现conversations列表/创建/详情并添加注解；测试owner+effective class双重过滤、401无写入、缺agent400、指定非法/disabled/外班agent404同体及disabled旧会话可继续。
- [x] 5.2 实现user消息写入、首问24字标题和updated_at排序；DB测试确认2–500字符边界、角色约束、client agent_id/class_id/history不能更改会话或可信输入。
- [x] 5.3 实现最近6条非空eligible历史，每条500字并使本轮question仅出现一次；provider输入spy验证旧消息不入上下文、interrupted assistant跳过、完整历史仍能回读。
- [x] 5.4 实现跨worker单会话generation锁与finally释放；PostgreSQL两个并发连接/worker测试第二请求409且无重复user行，故障/取消后能继续，不同会话可并行。
- [x] 5.5 增加conversations读取/创建apitest和会话归属/并发说明；runner比较同班他人、外班、不存在响应全文及DB title/owner/agent，记录锁释放证据。

## 6. 绑定材料检索与输入编排

- [x] 6.1 扩展retrieve的material_ids参数并贯穿compatibility、空范围检测、词法/向量候选和句级门槛查询；回归测试确认None兼容旧行为、空集不调embedding、未绑定高分材料不挤出bound命中。
- [x] 6.2 接入binding与当前class/subject授权交集、最多4条后按技能资料标题筛选；测试未绑定不兼容profile不阻塞、空正文/过滤后落空、编号连续及授权撤销，既有检索质量回归通过。
- [x] 6.3 实现800字原文输入和可回溯citation快照；测试标题/学科/chunk/generation/spans对应实际授权证据，材料删除或索引换代后来源打开不指向错误对象。
- [x] 6.4 实现课程顺序的prompt assembly与独立fallback；单测spy验证role/单技能/引导限制/evidence规则/上传边界，资料在user消息、无重复本轮问题、无客户端system消息。
- [x] 6.5 记录会话与原knowledge/ask两种无证据契约和流式引用性质；运行旧structured-answer/subject/retrieval测试并确认原无证据不调chat和200字quote校验保留。

## 7. Provider流、SSE与故障持久化

- [x] 7.1 新增独立stream_tutor provider与可控演示流，沿用CHAT配置但发送stream:true；provider协议测试验证真实多chunk读取、仅正文输出、预算/超时/响应关闭，旧answer协议不变。
- [x] 7.2 实现有状态numeric citation filter；单测跨块`[12]`、无引用、越界、合法编号、未闭合/长前缀，清洗后delta拼接与累计正文完全一致。
- [x] 7.3 实现messages POST的meta→delta→持久化→done，添加OpenAPI SSE注解；接口测试检查skill/citations先到、每delta新增、实际provider完成前可收到正文、done ID指向一致DB消息。
- [x] 7.4 实现首帧前HTTP错误与meta后error边界、partial interrupted保存、EOF/取消cleanup和当前授权再校验；故障注入覆盖零文本、部分文本、存库失败、断开和撤权，确认无虚假done或敏感错误。
- [x] 7.5 增加messages SSE apitest，核对首帧顺序、内容/citations/skill/state与DB、空binding/检索落空仍调chat但无编号；通过runner并交付fetch/curl流式示例和故障状态说明。

## 8. 流式代理与教师/师生界面

- [x] 8.1 将frontend代理改为真正stream转发并配置api/web gthread与关闭缓冲头；通过web入口计时验证首delta早于provider完成，同时多个会话和health正常，普通JSON/下载回归通过。
- [x] 8.2 在现有角色工作区增加teacher agents/skills配置界面；浏览器验证source编辑/上传、prompt、启停、多选绑定、服务器校验反馈与当前学科权限过滤，student/管理员无teacher写入口。
- [x] 8.3 增加师生tutor页和导航、新会话agent选择、最近会话及历史恢复；浏览器验证换agent新建、空agent状态、disabled旧会话和既有materials/retrieve/ask入口不回归。
- [x] 8.4 实现fetch+ReadableStream SSE解帧与发送状态；有意义的分块fixture验证半字符、半帧、CRLF、多帧、error/EOF、401不重放、切换视图取消及旧流不混入新会话。
- [x] 8.5 接入技能标签、提前citation显示和原文定位，安全渲染正文与来源；浏览器验证无citation不显示来源、删除/撤权提示、恶意HTML不执行、reload恢复complete/interrupted状态。
- [x] 8.6 完成窄屏和键盘/live-region适配，交付师生使用说明及截图；桌面/移动视口实际检查选择、输入、发送、历史、引用及焦点操作，文档中的操作路径可复现。

## 9. 全链路验收与交付记录

- [x] 9.1 在隔离完整环境执行全部apitest和既有后端/前端回归；报告确认每主要接口有脚本、响应+DB断言通过、全部跨用户/跨班404同体、schema文档和Swagger可试调。
- [x] 9.2 用真实CHAT/EMBEDDING配置审阅数学去括号/分数及语文古诗/阅读回答，比较skill停用/解绑、空prompt、落空、固定agent；保存脱敏记录，逐项确认有据引用、无据无编号和引导不泄露答案，fixture或skip不算通过。
- [x] 9.3 完成教程四项同伴交叉验证并保存实际请求响应证据：会话归属、agent隔离/停用旧会话、班级边界、skill开关；未取得真实同伴复核时保持本项未勾选并注明待办。
- [x] 9.4 在隔离环境演练升级与上一版服务回滚，确认材料/向量/profile/认证和新增历史保留；更新README范围、运行命令及最终验收记录，`openspec validate add-agent-skills-streaming-tutor --strict`通过，Git不含密钥/HTML报告。

2026-10-14：43/45完成。用户已批准真实模型调用，12组实际记录在 `docs/tutor-acceptance/review-results.md`；用户明确选择“稍后审阅，保留待办”，因此9.2不勾选。9.3未取得实际同伴证据，操作记录模板在 `docs/tutor-acceptance/peer-review.md`。完整实现验收见 `docs/tutor-acceptance/implementation-acceptance.md`。

2026-10-20：收紧为每轮一个下一步和一个问题，禁止通过关键词透露阅读中心或虚构学生进度，并强调提示句来源编号。相关26项回归通过，相同已批准样例的12组真实模型输出已更新并通过流/引用范围/落库结构核查；旧记录及中间失败记录保留。最终语文解绑对照仍有1例漏标引用，质量未通过；语义质量与同伴审阅继续pending，9.2、9.3保持未勾选，进度43/45。

2026-10-27：用户明确确认“9.2 9.3均确认已完成”，据此完成两项验收，整体45/45。用户确认记录在 `docs/tutor-acceptance/user-confirmation.md`；未补造逐例批注、同伴身份或请求响应明细。原始模型输出、历史漏标问题及采集状态保留，本次未修改业务代码或新增技术修复证据，未归档。
