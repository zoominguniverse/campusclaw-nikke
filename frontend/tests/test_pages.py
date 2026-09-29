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


def test_materials_page_includes_safe_inline_preview_control():
    client = app.test_client()
    user = {"username": "student_a1", "role": "student", "class_id": 1}
    with patch("server.current_user", return_value=user):
        response = client.get("/materials")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="preview" hidden' in body
    assert 'id="preview-body"' in body
    assert "materials/${materialId}" in body
    assert "preview-body').textContent = data.body_text" in body


def test_materials_page_includes_class_scoped_download_link():
    client = app.test_client()
    user = {"username": "student_a1", "role": "student", "class_id": 1}
    with patch("server.current_user", return_value=user):
        response = client.get("/materials")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "materials/${item.id}/download" in body
    assert "download.textContent = '下载文件'" in body


def test_materials_page_includes_retrieval_and_citations_without_vector_exposure():
    client = app.test_client()
    user = {"username": "student_a1", "role": "student", "class_id": 1}
    with patch("server.current_user", return_value=user):
        response = client.get("/materials")
    body = response.get_data(as_text=True)
    assert 'id="search-form"' in body
    assert 'id="ask-form"' in body
    assert 'id="citations"' in body
    assert "knowledge/retrieve" in body
    assert "knowledge/ask" in body
    assert "vector" not in body.replace('value="vector"', '')


def test_materials_page_renders_api_upload_errors_as_text():
    client = app.test_client()
    user = {"username": "teacher_a", "role": "teacher", "class_id": 1}
    with patch("server.current_user", return_value=user):
        response = client.get("/materials")
    body = response.get_data(as_text=True)
    assert "await response.json().catch(() => null)" in body
    assert "typeof failure.error === 'string'" in body
    assert "'#message').textContent = response.ok ? '上传成功。' : uploadMessage" in body
