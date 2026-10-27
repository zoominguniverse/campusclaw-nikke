# 真实模型与同伴复核计划

当前状态（2026-10-27）：用户明确确认9.2、9.3均已完成，两项已按用户确认结束验收。见 [用户验收确认](user-confirmation.md)。下文为此前的调用计划、历史问题和待办记录，原始采集文件保留。本次用户确认不等于新一轮模型运行或新增同伴请求响应证据。

准备发送的数据仅为合成课程样例：数学去括号/分数规则、《春晓》与树苗阅读片段，以及本仓库两份技能样板和校园学习助手提示词。问题固定在 `backend/evaluation/tutor_real_review.py` 的QUESTIONS中；额外无据问题为“火星环形山的年龄是多少？”。不发送开发库、实际学生数据、真实账号密码或其他个人内容。服务端仅使用当前配置的API凭据认证。

当前目标：DeepSeek `api.deepseek.com` 的 `deepseek-flash`（角色、技能、问题、证据和历史）；阿里云 `ws-iaucspuhthee68eh.cn-beijing.maas.aliyuncs.com` 的 `text-embedding-v4`（上述样例原文与问题embedding）。独立临时数据库，web5177，不改动5174开发环境。

通过 `docker compose --env-file .env -p campusclaw-tutor-real -f deploy/testing/docker-compose.tutor-real.yml up -d --build real-web` 启动，随后 `docker compose --env-file .env -p campusclaw-tutor-real -f deploy/testing/docker-compose.tutor-real.yml exec real-api python -m evaluation.tutor_real_review` 收集真实输出。此计划不代表已取得出站批准或已通过质量验收。记录保存在 `real-provider.json`，没有令牌或密钥。

用户已于2026-10-14明确批准上述真实模型调用，12组最终实际输出已收集至 `review-results.md` 和 `real-provider.json`。用户选择“稍后审阅，保留待办”，故人工质量状态继续为pending，任务9.2未勾选。实际同伴复核未提供，任务9.3未勾选。

2026-10-20：收紧单步引导与阅读答案边界后，沿用上述批准范围重新采集12组。当前记录已更新，旧记录保留在 `runs/2026-10-14/`；`record-integrity.json`只证明流、引用范围和持久化结构一致，不是人工语义或同伴结论。人工与同伴状态仍为pending。

当前第10例解绑对照仍漏标引用，属于未解决的质量发现，已在逐例记录标出。人工审阅时不能将本轮视为已通过，需一并评估该问题及解题引导边界。

人工审阅每例：有引用的事实由对应原文支撑；无据正文无数字引用；解题引导不泄露最终式子、得数、正确选项、诗句下一句或完整解答；对比技能停用/解绑、空prompt、材料落空和固定会话智能体。填写reviewer与结论后才能完成质量验收。

同伴复核四项：本人会话归属、本班agent/停用旧会话、跨班边界、技能开关。必须记录实际同伴身份、时间、环境和脱敏请求响应；自动测试或agent自检不能冒充同伴。未提供证据时任务9.3保持未勾选。
