document.addEventListener('DOMContentLoaded', async () => {
  const $ = selector => document.querySelector(selector);
  const node = (tag, text) => { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; return element; };
  const status = text => { $('#status').textContent = text; };
  let current = null, revision = 0, controller = null, busy = false;
  const json = body => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  async function api(path, options) {
    const response = await CampusAuth.apiFetch(path, options);
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(response.status === 401 ? '登录已过期，请重新登录；问题不会自动重发。' : data.error || '请求失败');
    return data;
  }
  $('#logout-button').onclick = async () => {
    controller?.abort();
    try { await CampusAuth.apiFetch('/api/auth/logout', {method: 'POST'}); }
    finally { CampusAuth.clear(); location.assign('/login'); }
  };
  if (!CampusAuth.access()) return location.assign('/login');
  let user;
  try { user = (await api('/api/auth/me')).user; } catch (error) { status(error.message); return; }
  if (!['teacher', 'student'].includes(user.role)) { status('当前角色无法使用学习辅导。'); $('#question-form').hidden = true; return; }
  const base = `/api/classes/${user.class_id}`;
  $('#current-account').textContent = `${user.username} · 班级 ${user.class_id}`;
  $('#config-link').hidden = user.role !== 'teacher';
  function sending(value) { busy = value; $('#send').disabled = value || !current; $('#question').disabled = value || !current; $('#cancel').hidden = !value; }
  function cancel() { revision += 1; controller?.abort(); controller = null; sending(false); $('#source-panel').hidden = true; }
  $('#cancel').onclick = () => { cancel(); status('已停止接收。请重新打开历史确认保存状态后继续。'); };
  window.addEventListener('pagehide', cancel);
  async function source(citation, stamp) {
    if (citation.unavailable) throw new Error('历史来源已删除或权限已变更。');
    await api(`${base}/knowledge/chunks/${citation.chunk_id}?${new URLSearchParams({source_hash: citation.source_hash})}`);
    const data = await api(`${base}/materials/${citation.material_id}`);
    if (stamp !== revision) return;
    if (data.source_hash !== citation.source_hash) throw new Error('来源已变化，请在新一轮重新检索。');
    $('#source-title').textContent = `${citation.subject_name} · ${citation.material_title}`;
    const body = $('#source-body'); body.replaceChildren();
    const points = Array.from(data.body_text);
    const spans = (citation.source_segments || []).filter(s => Number.isInteger(s.start) && Number.isInteger(s.end)).sort((a, b) => a.start - b.start);
    let cursor = 0;
    for (const span of spans) {
      if (span.start < cursor || span.end > points.length) continue;
      body.append(document.createTextNode(points.slice(cursor, span.start).join('')), node('mark', points.slice(span.start, span.end).join(''))); cursor = span.end;
    }
    body.append(document.createTextNode(points.slice(cursor).join('')));
    $('#source-status').textContent = spans.length ? '已定位引用原文。' : '旧版来源暂无精确定位。';
    $('#source-panel').hidden = false; body.focus(); body.querySelector('mark')?.scrollIntoView({block: 'nearest'});
  }
  function renderCitations(host, citations) {
    host.replaceChildren();
    for (const [index, citation] of citations.entries()) {
      const button = node('button', `[${citation.index || index + 1}] ${citation.subject_name || ''} · ${citation.material_title}${citation.unavailable ? '（来源不可用）' : ''}`);
      button.type = 'button'; const stamp = revision;
      button.onclick = async () => { try { await source(citation, stamp); } catch (error) { if (stamp === revision) status(error.message); } };
      const li = node('li'); li.append(button); host.append(li);
    }
    host.hidden = !citations.length;
  }
  function message(role, content, citations = [], skill = null, state = 'complete', toolCalls = []) {
    const card = node('article'); card.className = `chat-message chat-message--${role}`;
    card.append(node('strong', role === 'user' ? '你' : '学习助手'));
    const label = node('span', skill ? `技能：${skill}` : ''); label.className = 'skill-label'; label.hidden = !skill;
    const text = node('p', content); text.className = 'chat-text';
    const tools = node('ul'); tools.className = 'tool-status'; tools.setAttribute('aria-label', '工具调用状态'); tools.setAttribute('aria-live', 'polite'); tools.hidden = true;
    const sources = node('ul'); sources.className = 'source-links';
    const completion = node('p', state === 'interrupted' ? '回答已中断' : ''); completion.className = 'field-hint';
    card.append(label, tools, text, sources, completion); renderCitations(sources, citations); CampusTools.render(tools, toolCalls); $('#messages').append(card);
    return {card, text, label, tools, sources, completion};
  }
  async function recent(stamp = revision) {
    const data = await api('/api/conversations'); if (stamp !== revision) return;
    const active = data.items.find(item => item.id === current);
    if (active) $('#conversation-title').textContent = active.title;
    $('#conversations').replaceChildren(...data.items.map(item => {
      const li = node('li'), button = node('button', item.title); button.type = 'button';
      button.classList.toggle('selected', item.id === current);
      button.onclick = () => open(item.id).catch(error => status(error.message)); li.append(button); return li;
    }));
  }
  async function open(ident) {
    cancel(); const stamp = revision; status('正在读取历史…');
    const data = await api(`/api/conversations/${ident}`); if (stamp !== revision) return;
    current = ident; $('#conversation-title').textContent = data.conversation.title;
    $('#question').value = '';
    $('#active-agent').textContent = `${data.agent.name}${data.agent.enabled ? '' : '（已停用，已有会话仍可继续）'}`;
    $('#messages').replaceChildren(); data.messages.forEach((item, index) => {
      const next = data.messages[index + 1];
      message(item.role, item.content, item.citations, item.skill_name, item.completion_state,
        item.role === 'user' && next?.role === 'assistant' ? [] : item.tool_calls || []);
    });
    sending(false); status(''); await recent(stamp); $('#question').focus();
  }
  $('#new-conversation').onclick = async () => {
    cancel(); try {
      const agentId = Number($('#agent-select').value); if (!agentId) throw new Error('本班暂无可用智能体，请联系任课教师。');
      const data = await api('/api/conversations', json({agent_id: agentId})); await open(data.conversation.id);
    } catch (error) { status(error.message); }
  };
  $('#question-form').onsubmit = async event => {
    event.preventDefault(); if (busy || !current) return;
    const question = $('#question').value.trim();
    if (Array.from(question).length < 2 || Array.from(question).length > 500) { status('问题须为2–500字。'); return; }
    const stamp = ++revision, ident = current; controller = new AbortController(); sending(true); status('正在发送…');
    message('user', question); const answer = message('assistant', '');
    try {
      const response = await CampusAuth.apiFetch(`/api/conversations/${ident}/messages`, {...json({question}), signal: controller.signal});
      if (!response.ok) {
        const data = await response.json().catch(() => ({})); throw new Error(response.status === 401 ? '登录已过期，请重新登录；问题不会自动重发。' : data.error || '回答服务暂不可用');
      }
      await CampusSSE.readSSE(response, (name, data) => {
        if (stamp !== revision || current !== ident) return;
        if (name === 'meta') {
          answer.label.textContent = data.skill ? `技能：${data.skill.name}` : ''; answer.label.hidden = !data.skill;
          renderCitations(answer.sources, data.citations); status(data.demo_mode ? '演示模式 · 正在生成…' : '正在生成…');
          CampusTools.render(answer.tools, data.tool_calls, data.tool_warning);
        }
        if (name === 'delta') answer.text.append(document.createTextNode(data.text));
        if (name === 'done') { answer.completion.textContent = '已保存'; status('回答已保存'); $('#question').value = ''; }
        if (name === 'error') answer.completion.textContent = data.error;
      });
      if (stamp === revision) await recent(stamp);
    } catch (error) {
      if (stamp === revision) { answer.completion.textContent = '回答未完成，请重新打开历史确认保存状态。'; status(error.name === 'AbortError' ? '已停止生成' : error.message); }
    } finally { if (stamp === revision) { controller = null; sending(false); $('#question').focus(); } }
  };
  $('#question').onkeydown = event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); $('#question-form').requestSubmit(); } };
  $('#close-source').onclick = () => { $('#source-panel').hidden = true; $('#question').focus(); };
  sending(false);
  try {
    const data = await api(`${base}/agents`), enabled = data.items.filter(item => item.enabled);
    $('#agent-select').replaceChildren(...enabled.map(item => { const option = node('option', item.name); option.value = item.id; return option; }));
    $('#new-conversation').disabled = !enabled.length;
    if (!enabled.length) $('#selection-hint').textContent = '本班暂无可用智能体，请联系任课教师。已有会话可从左侧打开。';
    await recent();
  } catch (error) { status(error.message); }
});
