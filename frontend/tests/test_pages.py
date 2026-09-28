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

