/* Isolated MCP loading: registry failures cannot disable agent/skill editing. */
document.addEventListener('DOMContentLoaded', () => {
  const $ = selector => document.querySelector(selector);
  const node = (tag, text) => { const element = document.createElement(tag); element.textContent = text; return element; };
  let base, serverId = null, servers = [], declarations = [], confirmations = {};
  const status = text => { $('#mcp-status').textContent = text; };
  function confirmDelete(server) {
    return new Promise(resolve => {
      const previousFocus = document.activeElement, dialog = node('dialog', '');
      dialog.className = 'mcp-delete-confirm'; dialog.setAttribute('aria-labelledby', 'mcp-delete-title');
      const title = node('h3', `删除 ${server.name}？`); title.id = 'mcp-delete-title';
      const actions = node('div', ''); actions.className = 'action-row';
      const cancel = node('button', '取消'), accept = node('button', '确认删除');
      cancel.type = accept.type = 'button'; cancel.autofocus = true;
      cancel.onclick = () => dialog.close('cancel'); accept.onclick = () => dialog.close('delete');
      actions.append(cancel, accept); dialog.append(title, node('p', '历史和审计仍会保留。'), actions);
      dialog.onclose = () => { const accepted = dialog.returnValue === 'delete'; dialog.remove(); previousFocus?.focus(); resolve(accepted); };
      document.body.append(dialog); dialog.showModal();
    });
  }
  async function api(path, options) {
    const response = await CampusAuth.apiFetch(path, options), data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'MCP请求失败');
    return data;
  }
  function edit(server = null) {
    serverId = server?.id || null;
    $('#mcp-name').value = server?.name || ''; $('#mcp-url').value = server?.base_url || 'http://mcp-demo:8090'; $('#mcp-token').value = '';
    $('#mcp-token').required = !server;
    $('#mcp-edit-hint').textContent = server ? `${server.connected ? '已连接' : '未连接'} · ${server.has_token ? '已保存令牌，留空保留' : '未保存令牌'} · ${server.last_error_code || ''}` : '新服务器';
  }
  async function load() {
    const previousServers = servers;
    servers = (await api(`${base}/mcp/servers`)).items;
    for (const previous of previousServers) {
      if (!servers.some(server => server.id === previous.id && server.configuration_revision === previous.configuration_revision)) {
        for (const toolRef of Object.keys(confirmations)) if (toolRef.endsWith('@' + previous.name)) delete confirmations[toolRef];
      }
    }
    $('#mcp-servers').replaceChildren(...servers.map(server => {
      const row = node('li', ''), heading = node('strong', `${server.name} · ${server.connected ? '已连接' : '未连接'}`);
      row.append(heading);
      for (const [label, action] of [['编辑', null], ['连接', 'connect'], ['断开', 'disconnect'], ['删除', 'delete']]) {
        const button = node('button', label); button.type = 'button';
        button.onclick = async () => {
          if (!action) { edit(server); $('#mcp-name').focus(); return; }
          if (action === 'delete' && !await confirmDelete(server)) return;
          button.disabled = true;
          try {
            await api(`${base}/mcp/servers/${server.id}${action === 'delete' ? '' : '/' + action}`, {method: action === 'delete' ? 'DELETE' : 'POST'});
            await load(); status('操作已完成。');
          } catch (error) { status(error.message); await load().catch(() => {}); }
          finally { button.disabled = false; }
        };
        row.append(button);
      }
      return row;
    }));
    declarations = [];
    const failures = [];
    for (const server of servers) {
      try { declarations.push(...(await api(`${base}/mcp/servers/${server.id}/tools`)).items); }
      catch (error) { failures.push(`${server.name}：${error.message}`); }
    }
    for (const [toolRef, hash] of Object.entries(confirmations)) {
      if (!declarations.some(tool => tool.ref === toolRef && tool.declaration_hash === hash && tool.permitted)) delete confirmations[toolRef];
    }
    renderDeclarations();
    document.dispatchEvent(new CustomEvent('campus-mcp-registry-updated'));
    if (failures.length) status(failures.join('；'));
    edit(servers.find(server => server.id === serverId));
  }
  function renderDeclarations() {
    $('#mcp-tools').replaceChildren(...declarations.map(tool => {
      const details = node('details', ''), summary = node('summary', `${tool.ref}${tool.permitted ? '' : '（本地策略不许可）'}`);
      const description = node('p', tool.description), schema = node('pre', JSON.stringify(tool.inputSchema, null, 2));
      const label = node('label', ''), checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.disabled = !tool.permitted;
      label.className = 'checkbox-field';
      checkbox.checked = confirmations[tool.ref] === tool.declaration_hash;
      checkbox.onchange = () => { if (checkbox.checked) confirmations[tool.ref] = tool.declaration_hash; else delete confirmations[tool.ref]; };
      label.append(checkbox, document.createTextNode('我已审阅完整说明和参数 schema，确认本次绑定'));
      const add = node('button', '加入技能工具行'); add.type = 'button'; add.disabled = !tool.permitted;
      add.onclick = () => {
        const textarea = $('#skill-source'), lines = textarea.value.split('\n'), index = lines.findIndex(line => /^工具\s*[:：]/.test(line));
        if (index >= 0) {
          const refs = lines[index].split(/[:：]/).slice(1).join(':').split(/[,，、;；|]/).map(s => s.trim()).filter(Boolean);
          if (!refs.includes(tool.ref)) refs.push(tool.ref);
          lines[index] = '工具：' + refs.join('，');
        } else { const blank = lines.findIndex(line => !line.trim()); lines.splice(blank < 0 ? 0 : blank, 0, '工具：' + tool.ref); }
        textarea.value = lines.join('\n'); status('工具引用已加入。审阅并勾选确认后保存技能。');
      };
      details.append(summary, description, schema, node('p', `声明指纹：${tool.declaration_hash}`), label, add);
      return details;
    }));
    if (!declarations.length) $('#mcp-tools').append(node('p', '连接服务器后可查看完整工具声明。'));
  }
  window.CampusMCP = {
    confirmations: () => ({...confirmations}),
    editSkill: skill => {
      confirmations = {};
      $('#skill-mcp-hint').textContent = (skill?.mcp_bindings || []).map(binding => `${binding.ref}：${binding.status === 'ready' ? '已确认' : binding.status + '，请重新连接并审阅声明'}`).join('；');
      renderDeclarations();
    },
    refreshSkillStatus: skill => {
      $('#skill-mcp-hint').textContent = (skill?.mcp_bindings || []).map(binding => `${binding.ref}：${binding.status === 'ready' ? '已确认' : binding.status + '，请重新连接并审阅声明'}`).join('；');
    },
  };
  document.addEventListener('campus-config-ready', async event => {
    base = event.detail.base; $('#mcp-content').hidden = false;
    try { await load(); } catch (error) { status('MCP配置暂不可用：' + error.message); }
  });
  $('#mcp-new').onclick = () => { edit(); $('#mcp-name').focus(); };
  $('#mcp-refresh').onclick = () => load().catch(error => status(error.message));
  $('#mcp-form').onsubmit = async event => {
    event.preventDefault(); const button = event.currentTarget.querySelector('button'); button.disabled = true;
    const token = $('#mcp-token').value; $('#mcp-token').value = '';
    try {
      const response = await api(`${base}/mcp/servers${serverId ? '/' + serverId : ''}`, {method: serverId ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: $('#mcp-name').value, base_url: $('#mcp-url').value, token})});
      serverId = response.server.id; await load(); status('服务器已保存，请连接发现工具。');
    } catch (error) { status(error.message); }
    finally { button.disabled = false; }
  };
  $('#mcp-audit-refresh').onclick = async () => {
    try {
      const data = await api(`${base}/mcp/tool-calls`);
      $('#mcp-audit').replaceChildren(...data.items.map(call => node('li', `${call.created_at} · 用户${call.user_id} · 会话${call.conversation_id} · ${call.ref} · ${call.status} ${call.reason_code || ''} · ${call.text}`)));
      if (!data.items.length) $('#mcp-audit').append(node('li', '本班暂无工具调用记录。'));
    } catch (error) { status(error.message); }
  };
});
