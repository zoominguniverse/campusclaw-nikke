document.addEventListener('DOMContentLoaded', async () => {
  const $ = selector => document.querySelector(selector), status = text => { $('#status').textContent = text; };
  const node = (tag, text) => { const element = document.createElement(tag); element.textContent = text; return element; };
  const json = (body, method) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const selected = id => [...$(id).selectedOptions].map(option => option.value);
  let agentId = null, skillId = null, agents = [], skills = [], materials = [], base;
  let materialsTouched = false, hiddenMaterials = 0;
  let promptTemplates = [];
  async function api(path, options) {
    const response = await CampusAuth.apiFetch(path, options), data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(response.status === 401 ? '登录已过期，请重新登录。' : data.error || '请求失败');
    return data;
  }
  if (!CampusAuth.access()) return location.assign('/login');
  try {
    const user = (await api('/api/auth/me')).user;
    $('#current-account').textContent = `${user.username} · 班级 ${user.class_id}`;
    if (user.role !== 'teacher') { status('只有任课教师可以维护智能体和技能。'); return; }
    base = `/api/classes/${user.class_id}`; $('#config-content').hidden = false;
    document.dispatchEvent(new CustomEvent('campus-config-ready', {detail: {base}}));
  } catch (error) { status(error.message); return; }
  function options(host, items, values, display) {
    host.replaceChildren(...items.map(item => { const option = node('option', display(item)); option.value = item.id; option.selected = values.includes(item.id); return option; }));
  }
  function editAgent(item = null) {
    agentId = item?.id || null; materialsTouched = false; hiddenMaterials = item?.hidden_material_count || 0;
    $('#agent-name').value = item?.name || ''; $('#agent-prompt').value = item?.prompt || ''; $('#agent-enabled').checked = item ? item.enabled : true;
    options($('#agent-skills'), skills, item?.skill_ids || [], skill => `${skill.name}${skill.enabled ? '' : '（停用）'}`);
    options($('#agent-materials'), materials, item?.material_ids || [], material => `${material.subject_name} · ${material.title}（${material.searchable_status === 'ready' ? '可检索' : '待索引'}${material.index_compatibility === 'compatible' ? '' : '，语义需重建'}）`);
    $('#hidden-materials').textContent = hiddenMaterials ? `${hiddenMaterials}项绑定不在你当前学科权限内。保存其他字段会保留；修改材料选择会用当前选择替换全部绑定。` : '';
    $('#agent-audit').textContent = item ? `维护人ID：${item.updated_by ?? '演示种子'} · ${item.updated_at}` : '新智能体';
  }
  const template = '名称：新解题引导\n适用条件：解题、思路\n启用：是\n工具：knowledge_search\n\n通过提问帮助学生检查条件，不直接给出最终答案。';
  function editSkill(item = null) {
    skillId = item?.id || null; $('#skill-source').value = item?.source_text || template;
    $('#skill-file').value = ''; $('#delete-skill').disabled = !item;
    $('#skill-audit').textContent = item ? `维护人ID：${item.updated_by ?? '演示种子'} · ${item.updated_at}` : '新技能';
    window.CampusMCP?.editSkill(item);
  }
  function list(host, items, edit, display) {
    host.replaceChildren(...items.map(item => { const li = node('li', ''), button = node('button', display(item)); button.type = 'button'; button.onclick = () => edit(item); li.append(button); return li; }));
  }
  async function load() {
    const result = await Promise.all([api(`${base}/agents`), api(`${base}/skills`), api(`${base}/materials`)]);
    agents = result[0].items; skills = result[1].items; materials = result[2].items;
    list($('#agents'), agents, editAgent, item => `${item.name}${item.enabled ? '' : '（停用）'}`);
    list($('#skills'), skills, editSkill, item => `${item.name}${item.enabled ? '' : '（停用）'}`);
    editAgent(agents.find(item => item.id === agentId)); editSkill(skills.find(item => item.id === skillId));
  }
  async function saving(form, action) {
    const button = form.querySelector('button.primary-action'); button.disabled = true;
    try { await action(); await load(); status('配置已保存，下一轮提问生效。'); }
    catch (error) { status(error.message); }
    finally { button.disabled = false; }
  }
  $('#agent-form').onsubmit = event => {
    event.preventDefault(); saving(event.currentTarget, async () => {
      const body = {name: $('#agent-name').value, prompt: $('#agent-prompt').value, enabled: $('#agent-enabled').checked, skill_ids: selected('#agent-skills').map(Number)};
      if (!agentId || !hiddenMaterials || materialsTouched) body.material_ids = selected('#agent-materials');
      const data = await api(`${base}/agents${agentId ? '/' + agentId : ''}`, json(body, agentId ? 'PUT' : 'POST')); agentId = data.agent.id;
    });
  };
  $('#skill-form').onsubmit = event => {
    event.preventDefault(); saving(event.currentTarget, async () => {
      const data = await api(`${base}/skills${skillId ? '/' + skillId : ''}`, json({source_text: $('#skill-source').value, tool_confirmations: window.CampusMCP?.confirmations() || {}}, skillId ? 'PUT' : 'POST')); skillId = data.skill.id;
    });
  };
  $('#skill-file').onchange = async () => {
    try { const file = $('#skill-file').files[0]; if (!file) return; if (file.size > 32000) throw new Error('技能文件过大'); $('#skill-source').value = new TextDecoder('utf-8', {fatal: true}).decode(await file.arrayBuffer()); }
    catch (error) { status(error.message); }
  };
  $('#agent-materials').onchange = () => { materialsTouched = true; };
  document.addEventListener('campus-mcp-registry-updated', async () => {
    if (!base || !skillId) return;
    try {
      const item = (await api(`${base}/skills/${skillId}`)).skill;
      skills = skills.map(skill => skill.id === item.id ? item : skill);
      window.CampusMCP?.refreshSkillStatus(item);
    } catch (error) { $('#skill-mcp-hint').textContent = error.message; }
  });
  $('#new-agent').onclick = () => { editAgent(); $('#agent-name').focus(); };
  async function renderTemplate() {
    const identifier = $('#prompt-template').value;
    if (!identifier) throw new Error('请先选择提示词模板');
    const variables = Object.fromEntries(['subject', 'grade', 'topic', 'minutes'].map(name => [name, $(`#template-${name}`).value]));
    const data = await api(`${base}/prompt-templates/${encodeURIComponent(identifier)}/render`, json({variables}, 'POST'));
    $('#template-preview').value = data.template.prompt;
    return data.template;
  }
  async function templateAction(apply) {
    $('#preview-template').disabled = true; $('#apply-template').disabled = true;
    try {
      const item = await renderTemplate();
      if (apply) {
        $('#agent-prompt').value = item.prompt;
        if (!agentId && !$('#agent-name').value.trim()) $('#agent-name').value = item.app_name;
        $('#template-status').textContent = '已应用到角色提示词；可继续编辑，点击“保存智能体”后生效。';
        $('#agent-prompt').focus();
      } else $('#template-status').textContent = '预览已生成，尚未修改或保存智能体。';
    } catch (error) { $('#template-status').textContent = error.message; }
    finally { $('#preview-template').disabled = false; $('#apply-template').disabled = false; }
  }
  $('#preview-template').onclick = () => templateAction(false);
  $('#apply-template').onclick = () => templateAction(true);
  $('#prompt-template').onchange = () => {
    const item = promptTemplates.find(item => item.id === $('#prompt-template').value);
    $('#template-description').textContent = item ? `${item.audience} · ${item.description}` : '';
    $('#template-preview').value = ''; $('#template-status').textContent = '';
  };
  $('#new-skill').onclick = () => { editSkill(); $('#skill-source').focus(); };
  $('#delete-skill').onclick = async () => {
    if (!skillId || !confirm('删除此技能并解除所有智能体绑定？')) return;
    try { await api(`${base}/skills/${skillId}`, {method: 'DELETE'}); skillId = null; await load(); status('技能已删除并解绑。'); } catch (error) { status(error.message); }
  };
  try { await load(); } catch (error) { status(error.message); }
  try {
    promptTemplates = (await api(`${base}/prompt-templates`)).items;
    const host = $('#prompt-template');
    host.replaceChildren(...promptTemplates.map(item => { const option = node('option', item.name); option.value = item.id; return option; }));
    host.disabled = !promptTemplates.length;
    $('#preview-template').disabled = !promptTemplates.length; $('#apply-template').disabled = !promptTemplates.length;
    host.onchange();
  } catch (error) { $('#template-status').textContent = `模板暂不可用：${error.message}`; }
});
