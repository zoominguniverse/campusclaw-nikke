import json
import subprocess
from pathlib import Path


def test_authorized_client_refreshes_once_and_never_replays_unsafe_requests():
    auth_path = Path(__file__).resolve().parents[1] / "static" / "auth.js"
    script = f"""
const fs = require('fs');
const storage = new Map();
global.sessionStorage = {{getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, String(value)), removeItem: key => storage.delete(key)}};
const redirects = [];
global.window = {{location: {{assign: value => redirects.push(value)}}}};
global.document = {{body: {{dataset: {{apiUrl: ''}}}}}};
eval(fs.readFileSync({json.dumps(str(auth_path))}, 'utf8'));
const auth = window.CampusAuth;
auth.store({{access_token: 'access-one', refresh_token: 'refresh-one'}});
let calls = [];
global.fetch = async (url, options) => {{
  calls.push([url, options.method || 'GET', options.headers instanceof Headers ? options.headers.get('Authorization') : options.headers.Authorization]);
  if (url.endsWith('/token/refresh')) return new Response(JSON.stringify({{access_token: 'access-two', refresh_token: 'refresh-two'}}), {{status: 200}});
  return new Response('ok', {{status: calls.filter(call => call[0] === '/safe').length === 1 ? 401 : 200}});
}};
(async () => {{
  const safeResponse = await auth.apiFetch('/safe');
  if (safeResponse.status !== 200) throw new Error(`safe request did not retry: status=${{safeResponse.status}}, calls=${{JSON.stringify(calls)}}`);
  if (JSON.stringify(calls) !== JSON.stringify([['/safe', 'GET', 'Bearer access-one'], ['/api/auth/token/refresh', 'POST', 'Bearer refresh-one'], ['/safe', 'GET', 'Bearer access-two']])) throw new Error(`unexpected refresh sequence: ${{JSON.stringify(calls)}}`);
  calls = [];
  global.fetch = async (url, options) => {{ calls.push([url, options.method || 'GET']); return new Response('', {{status: 401}}); }};
  if ((await auth.apiFetch('/unsafe', {{method: 'POST'}})).status !== 401 || calls.length !== 1) throw new Error('unsafe request was replayed');
  auth.store({{access_token: 'access-three', refresh_token: 'refresh-three'}});
  calls = [];
  global.fetch = async (url, options) => {{ calls.push(url); return new Response('', {{status: 401}}); }};
  await auth.apiFetch('/failed-refresh');
  if (auth.access() || redirects.at(-1) !== '/login' || calls.length !== 2) throw new Error('failed refresh did not clear and redirect');
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
