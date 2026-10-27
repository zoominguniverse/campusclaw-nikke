/* Cumulative metadata and history share a call-id based renderer. */
(function (root) {
  function mergeCalls(previous, incoming) {
    const calls = new Map(previous.map(call => [call.call_id, call]));
    for (const call of incoming || []) if (typeof call.call_id === 'string') calls.set(call.call_id, {...calls.get(call.call_id), ...call});
    return [...calls.values()];
  }
  function render(host, incoming, warning) {
    host._calls = mergeCalls(host._calls || [], incoming);
    host.replaceChildren();
    for (const call of host._calls) {
      const item = document.createElement('li');
      const label = {ok: '成功', error: '失败', denied: '已拒绝'}[call.status] || '结果未知';
      item.textContent = `${call.ref} · 第${call.round}轮 · ${label}${call.reason_code ? '（' + call.reason_code + '）' : ''}：${call.text || ''}`;
      host.append(item);
    }
    if (warning) { const item = document.createElement('li'); item.textContent = warning; host.append(item); }
    host.hidden = !host.childElementCount;
  }
  root.CampusTools = {mergeCalls, render};
  if (typeof module !== 'undefined') module.exports = {mergeCalls};
})(typeof window === 'undefined' ? globalThis : window);
