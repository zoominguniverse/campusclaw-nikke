(() => {
  const accessKey = 'campusclaw.access_token';
  const refreshKey = 'campusclaw.refresh_token';
  const api = document.body.dataset.apiUrl || '';
  const clear = () => { sessionStorage.removeItem(accessKey); sessionStorage.removeItem(refreshKey); };
  const store = payload => { sessionStorage.setItem(accessKey, payload.access_token); sessionStorage.setItem(refreshKey, payload.refresh_token); };
  let refreshPromise;
  async function refresh() {
    if (!refreshPromise) refreshPromise = (async () => {
      const token = sessionStorage.getItem(refreshKey);
      if (!token) throw new Error('missing refresh token');
      const response = await fetch(`${api}/api/auth/token/refresh`, {method: 'POST', headers: {Authorization: `Bearer ${token}`}});
      if (!response.ok) throw new Error('refresh rejected');
      store(await response.json());
    })().finally(() => { refreshPromise = undefined; });
    return refreshPromise;
  }
  async function apiFetch(path, options = {}, retried = false) {
    const access = sessionStorage.getItem(accessKey);
    if (!access) return new Response(null, {status: 401});
    const headers = new Headers(options.headers || {});
    headers.set('Authorization', `Bearer ${access}`);
    const response = await fetch(`${api}${path}`, {...options, headers});
    const method = (options.method || 'GET').toUpperCase();
    if (response.status === 401 && !retried && ['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      try { await refresh(); return apiFetch(path, options, true); } catch (_) { clear(); window.location.assign('/login'); }
    }
    return response;
  }
  window.CampusAuth = {api, clear, store, apiFetch, access: () => sessionStorage.getItem(accessKey)};
})();
