document.addEventListener('DOMContentLoaded', async () => {
  const $ = selector => document.querySelector(selector);
  if (!CampusAuth.access()) return window.location.assign('/login');
  const me = await CampusAuth.apiFetch('/api/auth/me');
  if (!me.ok) return;
  const user = (await me.json()).user;
  const base = `/api/classes/${user.class_id}`;
  const select = $('#subject-select');
  let revision = 0, rebuilding = null;
  const selected = () => select.value ? Number(select.value) : null;
  const show = text => { $('#message').textContent = text; };
  const node = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const button = (text, action) => {
    const element = node('button', text); element.type = 'button';
    element.addEventListener('click', async () => {
      element.disabled = true;
      try { await action(); } catch (error) { show(error.message); }
      finally { element.disabled = false; }
    });
    return element;
  };
  const jsonOptions = body => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  function clearEvidence() {
    revision += 1;
    $('#search-results').replaceChildren(); $('#search-message').textContent = '';
    $('#citations').replaceChildren(); $('#answer-text').textContent = ''; $('#answer-status').textContent = '';
    $('#preview').hidden = true; $('#preview-body').replaceChildren();
  }
  async function request(path, options) {
    const response = await CampusAuth.apiFetch(base + path, options);
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) {
      if ([401, 403, 404].includes(response.status)) clearEvidence();
      const messages = {400: '输入无效，请检查内容与切片设置。', 401: '登录已过期，请重新登录。', 403: '当前权限无法执行该操作。', 404: '资料或证据不可访问，请刷新列表。', 409: '来源已变化或重建发生冲突，请重新检索或重试。', 502: '回答引用未通过校验，请重试。', 503: '模型服务暂不可用，请稍后重试。'};
      const error = new Error(data.code === 'reindex_required' ? '当前范围资料需要重建索引，可先使用关键词检索。' : messages[response.status] || '请求失败，请重试。');
      error.status = response.status; throw error;
    }
    return data;
  }
  $('#current-account').textContent = `当前账号：${user.username}`;
  $('#context-indicator').textContent = `班级 ${user.class_id}`;
  $('#role-kicker').textContent = user.role === 'teacher' ? '教师工作区' : '学习工作区';
  const nav = $('#workspace-nav');
  const activate = id => {
    ['materials', 'retrieve', 'ask'].forEach(view => { $(`#view-${view}`).hidden = view !== id; });
    [...nav.children].forEach(a => a.classList.toggle('is-active', a.hash === `#${id}`));
    $('#preview').hidden = true;
  };
  ['materials', 'retrieve', 'ask'].forEach((id, index) => {
    const a = node('a', ['材料管理', '知识检索', '基于资料提问'][index]);
    a.href = `#${id}`; a.onclick = event => { event.preventDefault(); activate(id); }; nav.append(a);
  });
  async function capabilities() {
    const stamp = revision;
    try {
      const data = await request(`/knowledge/capabilities${selected() ? `?subject_id=${selected()}` : ''}`);
      if (stamp !== revision) return;
      $('#capability-status').textContent = [
        data.demo_mode ? '语义检索使用演示向量，改写检索效果尚未验收。' : data.semantic_ready ? '语义检索已通过验收。' : '语义检索尚未完成质量验收。',
        data.chat_demo_mode ? '问答为演示摘录。' : '问答使用真实模型。',
        data.index_compatibility === 'reindex_required' ? '部分资料需要重建；关键词仍可使用。' : ''
      ].filter(Boolean).join(' ');
    } catch (error) { if (stamp === revision) $('#capability-status').textContent = error.message; }
  }
  function indexState(item) {
    const latest = {ready: '成功', failed: '失败', building: '进行中', conflict: '冲突', pending: '未开始'}[item.latest_attempt_status] || item.latest_attempt_status;
    const searchable = item.searchable_status === 'ready';
    return `${item.source_saved ? '原文已保存' : '原文未保存'} · ${searchable ? '已有可检索索引' : '暂不可检索'} · 最近索引尝试：${latest}` +
      (item.latest_attempt_status === 'failed' && searchable ? '（已保留此前索引）' : '') +
      (item.index_compatibility !== 'compatible' ? ' · 语义索引需重建' : '');
  }
  function indexOutcome(data) {
    if (data.indexing?.status === 'ready') return '原文已保存，索引已建立。';
    return `原文已保存，本次索引${data.indexing?.status === 'conflict' ? '发生冲突' : '失败'}。` + (data.material?.searchable_status === 'ready' ? '此前索引仍可检索；可按原设置重试。' : '暂不可检索，可按原设置重试。');
  }
  async function load() {
    const stamp = revision;
    try {
      const data = await request(`/materials${selected() ? `?subject_id=${selected()}` : ''}`);
      if (stamp !== revision) return;
      $('#materials').replaceChildren(...data.items.map(item => {
        const li = node('li'); li.append(node('strong', `${item.subject_name} · ${item.title}`), node('p', indexState(item), 'material-state'));
        const actions = node('div', undefined, 'action-row');
        actions.append(button('在线预览', () => preview(item.id)), button('下载文件', () => download(item)));
        if (user.role === 'teacher') actions.append(
          button('重命名', () => rename(item)), button('设置并重建', () => openRebuild(item)),
          button('按原设置重试', () => rebuild(item.id, null)), button('删除材料', () => remove(item))
        );
        li.append(actions); return li;
      }));
    } catch (error) { show(error.message); }
  }
  // Python offsets are Unicode code points. Array.from keeps emoji as one item.
  // Text nodes and mark elements prevent source text from being interpreted as HTML.
  function highlightSource(text, spans) {
    const points = Array.from(text), merged = [];
    const valid = spans.filter(span => Number.isInteger(span.start) && Number.isInteger(span.end) && span.start >= 0 && span.end <= points.length && span.start < span.end).sort((a, b) => a.start - b.start);
    valid.forEach(span => {
      const previous = merged[merged.length - 1];
      if (previous && span.start <= previous.end) previous.end = Math.max(previous.end, span.end);
      else merged.push({...span});
    });
    const body = $('#preview-body'); body.replaceChildren(); let cursor = 0;
    merged.forEach(span => {
      body.append(document.createTextNode(points.slice(cursor, span.start).join('')));
      body.append(node('mark', points.slice(span.start, span.end).join(''))); cursor = span.end;
    });
    body.append(document.createTextNode(points.slice(cursor).join('')));
    return body.querySelector('mark');
  }
  async function detail(hit, query) {
    return (await request(`/knowledge/chunks/${hit.chunk_id}?${new URLSearchParams({source_hash: hit.source_hash, query})}`)).evidence;
  }
  async function preview(materialId, hit = null, query = '') {
    const stamp = revision;
    $('#preview').hidden = true; $('#preview-body').replaceChildren();
    if (hit) await detail(hit, query); // Reauthorize every open, including retired citations.
    const data = await request(`/materials/${materialId}`);
    if (stamp !== revision) return;
    if (hit && data.source_hash !== hit.source_hash) throw new Error('原文已变化，请重新检索。');
    const precise = hit?.provenance_version === 'source-map-v1';
    const spans = precise ? (hit.quotes?.map(q => q.source_span) || [{start: hit.excerpt_start_offset, end: hit.excerpt_end_offset}]) : [];
    const first = highlightSource(data.body_text, spans);
    $('#preview-title').textContent = `${data.material.subject_name} · ${data.material.title}`;
    $('#preview-status').textContent = hit && !precise ? '旧版索引缺少精确原文映射，仅显示原文。' : first ? '已高亮引用原文。' : '材料原文';
    $('#preview').hidden = false;
    $('#preview').scrollIntoView({block: 'nearest'});
    if (first) first.scrollIntoView({block: 'center'});
  }
  function evidenceCard(hit, query, ordinal) {
    const li = node('li', undefined, 'evidence-card');
    const location = hit.provenance_version === 'source-map-v1' ? `原文字符 [${hit.excerpt_start_offset}, ${hit.excerpt_end_offset})` : '旧版来源，暂无精确定位';
    li.append(node('strong', `${ordinal ? `[${ordinal}] ` : ''}${hit.subject_name} · ${hit.material_title}`), node('p', `切片 ${hit.chunk_index} · ${location}`, 'evidence-location'), node('p', hit.excerpt, 'evidence-excerpt'));
    const full = node('div', undefined, 'evidence-full'); full.hidden = true;
    const expand = button('展开完整证据', async () => {
      if (!full.hidden) { full.hidden = true; full.replaceChildren(); expand.textContent = '展开完整证据'; return; }
      const stamp = revision; const data = await detail(hit, query); if (stamp !== revision) return;
      full.replaceChildren();
      if (data.heading_context) full.append(node('p', `章节：${data.heading_context}`, 'field-hint'));
      full.append(node('pre', data.chunk_text)); full.hidden = false; expand.textContent = '收起完整证据';
    });
    const actions = node('div', undefined, 'action-row'); actions.append(expand, button('打开原文并定位', () => preview(hit.material_id, hit, query)));
    li.append(actions, full); return li;
  }
  async function download(item) {
    const response = await CampusAuth.apiFetch(`${base}/materials/${item.id}/download`);
    if (!response.ok) throw new Error('文件不可访问，请刷新列表。');
    const url = URL.createObjectURL(await response.blob()), a = node('a'); a.href = url; a.download = item.original_filename; a.click(); URL.revokeObjectURL(url);
  }
  async function rename(item) {
    const title = window.prompt('材料标题', item.title); if (!title) return;
    await request(`/materials/${item.id}`, {...jsonOptions({title}), method: 'PUT'}); show('材料已重命名。'); await load();
  }
  async function remove(item) {
    if (!window.confirm(`确定删除“${item.title}”吗？`)) return;
    await request(`/materials/${item.id}`, {method: 'DELETE'}); clearEvidence(); show('材料已删除。'); await load(); await capabilities();
  }
  function installOptions(form) {
    form.querySelector('.chunk-options-host').append($('#chunk-options-template').content.cloneNode(true));
    form.elements.strategy.onchange = () => { form.querySelector('.custom-options').hidden = form.elements.strategy.value !== 'custom'; form.querySelector('.chunk-preview').replaceChildren(); };
  }
  const uploadForm = $('#upload-form'), rebuildForm = $('#rebuild-form'); installOptions(uploadForm); installOptions(rebuildForm);
  function readOptions(form) {
    const fields = form.elements, options = {strategy: fields.strategy.value, preprocess: {}};
    for (const name of ['remove_urls', 'remove_emails', 'collapse_whitespace']) options.preprocess[name] = fields[name].checked;
    if (options.strategy === 'custom') {
      options.max_length = Number(fields.max_length.value); options.overlap_percent = Number(fields.overlap_percent.value);
      options.separators = ['blank_line', 'line', 'sentence'].filter(name => fields[`sep_${name}`].checked);
      if (!Number.isInteger(options.max_length) || options.max_length < 100 || options.max_length > 2000 || !Number.isFinite(options.overlap_percent) || options.overlap_percent < 0 || options.overlap_percent > 50) throw new Error('请检查长度及重叠比例。');
    }
    return options;
  }
  function openRebuild(item) {
    rebuilding = item; const options = item.chunking || {}, fields = rebuildForm.elements;
    fields.strategy.value = ['auto', 'hierarchy', 'custom'].includes(options.strategy) ? options.strategy : 'auto';
    fields.max_length.value = options.max_length ?? 800; fields.overlap_percent.value = options.overlap_percent ?? 10;
    for (const name of ['blank_line', 'line', 'sentence']) fields[`sep_${name}`].checked = (options.separators || ['blank_line', 'line', 'sentence']).includes(name);
    for (const name of ['remove_urls', 'remove_emails', 'collapse_whitespace']) fields[name].checked = Boolean(options.preprocess?.[name]);
    fields.strategy.onchange(); $('#rebuild-title').textContent = `重建：${item.title}`; $('#rebuild-panel').hidden = false; $('#rebuild-panel').scrollIntoView({block: 'nearest'});
  }
  async function rebuild(id, options) {
    clearEvidence(); show('正在重建索引…');
    const data = await request(`/materials/${id}/reindex`, jsonOptions(options ? {chunking: options} : {}));
    show(indexOutcome(data)); $('#rebuild-panel').hidden = true; await load(); await capabilities();
  }
  function showChunkPreview(form, data) {
    const target = form.querySelector('.chunk-preview'); target.replaceChildren(node('p', `共 ${data.total} 片，展示前 ${data.samples.length} 片。`));
    data.samples.forEach((sample, index) => {
      const item = node('details'); item.append(node('summary', `样本 ${index + 1} · ${Array.from(sample.text).length} 字符`), node('pre', sample.text)); target.append(item);
    });
  }
  async function decodeFile(file) {
    if (!file) throw new Error('请先选择材料文件。');
    if (file.size > 5242880) throw new Error('材料文件不能超过 5 MB。');
    const bytes = await file.arrayBuffer();
    try { return new TextDecoder('utf-8', {fatal: true}).decode(bytes); } catch { return new TextDecoder('gb18030', {fatal: true}).decode(bytes); }
  }
  async function previewChunks(form, existing) {
    form.querySelector('.chunk-preview').replaceChildren();
    try {
      const chunking = readOptions(form), stamp = revision;
      const data = existing ? await request(`/materials/${existing.id}/chunk-preview`, jsonOptions({chunking})) : await request('/materials/chunk-preview', jsonOptions({subject_id: selected(), text: await decodeFile(uploadForm.elements.file.files[0]), chunking}));
      if (stamp === revision) showChunkPreview(form, data);
    } catch (error) { form.querySelector('.chunk-preview').textContent = error.message; }
  }
  $('#upload-preview').onclick = () => previewChunks(uploadForm, null);
  $('#rebuild-preview').onclick = () => previewChunks(rebuildForm, rebuilding);
  $('#close-rebuild').onclick = () => { $('#rebuild-panel').hidden = true; };
  async function submitForm(form, work) {
    const submit = form.querySelector('button[type="submit"], button.primary-action'); submit.disabled = true;
    try { await work(); } catch (error) { show(error.message); } finally { submit.disabled = false; }
  }
  uploadForm.onsubmit = event => {
    event.preventDefault(); submitForm(uploadForm, async () => {
      const chunking = readOptions(uploadForm); clearEvidence(); show('正在保存材料并建立索引…');
      const body = new FormData(uploadForm); body.set('chunking', JSON.stringify(chunking)); body.set('subject_id', selected());
      const data = await request('/materials', {method: 'POST', body}); show(indexOutcome(data));
      uploadForm.querySelector('.chunk-preview').replaceChildren(); await load(); await capabilities();
    });
  };
  rebuildForm.onsubmit = event => { event.preventDefault(); submitForm(rebuildForm, () => rebuild(rebuilding.id, readOptions(rebuildForm))); };
  $('#search-form').onsubmit = event => {
    event.preventDefault(); submitForm(event.currentTarget, async () => {
      clearEvidence(); const stamp = revision, query = $('#search-query').value;
      $('#search-message').textContent = '正在检索…';
      try {
        const data = await request('/knowledge/retrieve', jsonOptions({query, mode: $('#search-mode').value, subject_id: selected()}));
        if (stamp !== revision) return;
        $('#search-message').textContent = data.hits.length ? `找到 ${data.hits.length} 条相关证据；摘录最多 160 字符。` : '未找到相关资料。';
        $('#search-results').replaceChildren(...data.hits.map(hit => evidenceCard(hit, query)));
      } catch (error) { if (stamp === revision || [401, 403, 404].includes(error.status)) $('#search-message').textContent = error.message; }
    });
  };
  $('#ask-form').onsubmit = event => {
    event.preventDefault(); submitForm(event.currentTarget, async () => {
      clearEvidence(); const stamp = revision, question = $('#ask-question').value;
      $('#answer-status').textContent = '正在查找证据并生成回答…';
      try {
        const data = await request('/knowledge/ask', jsonOptions({question, subject_id: selected()}));
        if (stamp !== revision) return;
        $('#answer-status').textContent = `${data.demo_mode ? '演示摘录' : '模型回答'} · ${{answered: '已校验引用原文', insufficient: '资料不足以回答', no_evidence: '未找到相关资料'}[data.status] || ''}`;
        $('#answer-text').textContent = data.answer;
        $('#citations').replaceChildren(...data.citations.map((hit, index) => evidenceCard(hit, question, index + 1)));
      } catch (error) { if (stamp === revision || [401, 403, 404].includes(error.status)) $('#answer-status').textContent = error.message; }
    });
  };
  select.onchange = () => {
    clearEvidence(); $('#rebuild-panel').hidden = true;
    uploadForm.querySelector('.chunk-preview').replaceChildren(); $('#upload-subject-id').value = select.value;
    $('#upload-panel').hidden = user.role !== 'teacher' || !selected(); show(''); load(); capabilities();
  };
  $('#close-preview').onclick = () => { $('#preview').hidden = true; $('#preview-body').replaceChildren(); };
  $('#nav-toggle').onclick = () => { document.body.dataset.sidebarOpen = document.body.dataset.sidebarOpen !== 'true' ? 'true' : 'false'; };
  $('#logout-button').onclick = async () => {
    await CampusAuth.apiFetch('/api/auth/logout', {method: 'POST'}).catch(() => {});
    CampusAuth.clear(); window.location.assign('/login');
  };
  try {
    const subjects = (await request('/subjects')).items; select.append(...subjects.map(subject => new Option(subject.name, subject.id)));
    if (user.role === 'teacher' && subjects.length === 1) select.value = String(subjects[0].id);
    select.onchange(); activate(['materials', 'retrieve', 'ask'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'materials');
  } catch (error) { show(error.message); }
});
