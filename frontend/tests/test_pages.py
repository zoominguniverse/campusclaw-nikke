from unittest.mock import patch

from server import app


def test_protected_page_redirects_to_login_without_user():
    client = app.test_client()
    with patch("server.current_user", return_value=None):
        response = client.get("/materials")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login?next=/materials"


def test_login_page_redirects_authenticated_user_to_materials():
    client = app.test_client()
    with patch("server.current_user", return_value={"username": "teacher_a", "role": "teacher", "class_id": 1}):
        response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"] == "/materials"


def test_materials_page_includes_csrf_protected_logout_control():
    client = app.test_client()
    user = {"username": "teacher_a", "role": "teacher", "class_id": 1}
    with patch("server.current_user", return_value=user):
        response = client.get("/materials")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="logout-button"' in body
    assert "'/api/auth/logout'" in body
    assert "{method: 'POST'}" in body
