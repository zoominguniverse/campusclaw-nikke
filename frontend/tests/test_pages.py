from server import app


def test_login_is_a_neutral_bearer_token_shell():
    response = app.test_client().get("/login")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="login-form"' in body
    assert 'static/auth.js' in body and 'static/login.js' in body
    assert "credentials: 'include'" not in body


def test_materials_is_not_server_authenticated_or_user_rendered():
    response = app.test_client().get("/materials", headers={"Cookie": "session=legacy"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'class="workspace-content"' in body
    assert 'current-account' in body
    assert 'static/materials.js' in body
    assert 'sessionStorage' not in body


def test_static_modules_use_authorization_and_session_storage_only():
    client = app.test_client()
    auth = client.get("/static/auth.js").get_data(as_text=True)
    materials = client.get("/static/materials.js").get_data(as_text=True)
    assert "sessionStorage" in auth
    assert "localStorage" not in auth
    assert "Authorization" in auth
    assert "token/refresh" in auth
    assert "credentials" not in auth
    assert "download" in materials and "apiFetch" in materials


def test_proxy_forwards_authorization_not_cookie(monkeypatch):
    captured = {}

    class Upstream:
        content = b"ok"
        status_code = 200
        headers = {"Content-Type": "text/plain"}

    def fake_request(*args, **kwargs):
        captured.update(kwargs["headers"])
        return Upstream()

    monkeypatch.setattr("server.requests.request", fake_request)
    response = app.test_client().get("/api/auth/me", headers={"Authorization": "Bearer access", "Cookie": "legacy=value"})
    assert response.status_code == 200
    assert captured == {"Authorization": "Bearer access"}


def test_token_pages_send_restrictive_security_headers():
    response = app.test_client().get("/login")
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "no-referrer"
