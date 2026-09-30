document.addEventListener('DOMContentLoaded', () => {
  if (CampusAuth.access()) { window.location.assign('/materials'); return; }
  document.querySelector('#login-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const response = await fetch(`${CampusAuth.api}/api/auth/login`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: form.get('username'), password: form.get('password')})});
    if (!response.ok) { document.querySelector('#error').textContent = '账号或密码错误。'; return; }
    CampusAuth.store(await response.json());
    window.location.assign('/materials');
  });
});
