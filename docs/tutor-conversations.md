# 第5课：学习辅导与配置

教师登录后，在「教学工作区 → 智能体与技能」创建或选择智能体，编辑角色提示词、启停状态，并多选本班技能与当前获授权学科材料。技能文件格式和可上传样板见 [技能说明](tutor-skills.md)。空提示词使用校园学习助手默认角色；修改配置在下一轮生效。停用只阻止新选用，已有会话仍可继续。

教师和学生从「AI 学习辅导」选择助手、新建会话、输入2–500字问题。已有会话固定助手；更换助手需新建会话。左侧最近会话可恢复完整历史。Ctrl/⌘+Enter发送，Enter换行；「停止生成」取消接收，随后重新打开历史确认已保存部分。回答出现「技能」标签代表本轮选中了绑定且启用的技能。来源提前显示，点击可查看并高亮原文；删除、撤权或原文变化时会提示不可用。演示模式明确标注，不代表真实模型质量验收。

## 两种问答契约

`POST /api/classes/{class_id}/knowledge/ask` 保持第4课规则：无证据不调用chat，回答最多200字，结构化claim/精确原文quote校验，不满足则拒答。

`POST /api/conversations/{id}/messages` 使用本轮服务器配置和最近6条eligible历史（各500字，排除interrupted assistant）。无证据仍可提供学习帮助，但数字引用全部移除。证据最多4条，每条输入最多800字原文；citations为检索快照，不能自动证明每句话受到支持。具体事实支撑与解题引导由真实模型人工审阅验收。

## 接口和故障

同源 `/swagger/`（兼容 `/swagger/index.html`）可登录后复制access token到Authorize试调；不持久保存令牌。`/openapi.json`从处理器注解生成。技能和智能体写操作仅本班教师允许；管理员不能继承教师权限。所有会话由认证推导owner与班级，外班/同班他人/不存在会话统一404。

消息流依次 `meta`、若干 `delta`、`done`；`done.message_id`只在assistant complete落库后返回。首帧之前用HTTP错误；meta后用error帧，HTTP仍为200。已发部分尽量保存为interrupted；数据库故障提示未保存。中断回答不进入下一轮历史。客户端不能自动重放POST，401需重新登录并主动发送。单会话跨worker advisory锁冲突返回409，不插入第二条问题；不同会话可并行。锁连接独立且在结束/取消时释放。

流中可出现标准SSE `: keep-alive`注释帧，用于刷新连接并检测下游断开，不增加正文或改变事件顺序。停止接收后，若服务已完成提交，历史可能显示complete；以重新读取的持久化状态为准。收到断开时保存已发部分为interrupted。窄屏最近列表可滚动，教师入口及无来源区域使用hidden隐藏；状态提示为polite live-region，来源打开后焦点进入原文，关闭后回到问题输入。

```javascript
const response = await fetch(`/api/conversations/${id}/messages`, {
  method: 'POST', headers: {Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json'},
  body: JSON.stringify({question: '请引导我理解这道题的条件'})
});
await CampusSSE.readSSE(response, (event, data) => console.log(event, data));
```

终端可设置本次access token环境变量，然后 `curl -N -H "Authorization: Bearer $ACCESS_TOKEN" -H 'Content-Type: application/json' -d '{"question":"请引导我理解条件"}' http://localhost:5173/api/conversations/1/messages`。不要将令牌写入源码或验收报告。


第6课扩展：MCP技能引用、完整声明确认、模型自主多轮工具决策、审计和重复meta事件见 [MCP工具说明](mcp-tools.md)，升级与回滚见 [MCP迁移](mcp-migration.md)。旧knowledge_search技能保持原路径。
