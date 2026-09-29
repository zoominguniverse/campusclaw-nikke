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


def test_login_page_is_branded_account_password_entry_without_role_picker():
    client = app.test_client()
    with patch("server.current_user", return_value=None):
        body = client.get("/login").get_data(as_text=True)
    assert 'class="login-layout"' in body
    assert 'name="username"' in body
    assert 'name="password"' in body
    assert 'href="/static/app.css"' in body
    assert 'data-role' not in body
    assert '预置账号' not in body


def test_local_workspace_stylesheet_is_served_without_external_dependency():
    response = app.test_client().get("/static/app.css")
    assert response.status_code == 200
    assert b"--brand:" in response.data


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
    assert "materials/${id}" in body
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
    assert "failure?.error || '上传失败。'" in body
    assert "new FormData(uploadForm)" in body


def test_teacher_materials_page_wires_confirmed_csrf_delete_action():
    client = app.test_client()
    user = {"username": "teacher_a", "role": "teacher", "class_id": 1}
    with patch("server.current_user", return_value=user):
        response = client.get("/materials")
    body = response.get_data(as_text=True)
    assert "const canDeleteMaterials = true;" in body
    assert "remove.textContent = '删除材料'" in body
    assert "deleteMaterial(item.id, item.title)" in body
    assert "if (!window.confirm(" in body
    assert "{method: 'DELETE'}" in body
    assert "response.status === 204 ? '材料已删除。'" in body
    assert "await loadMaterials();" in body


def test_student_materials_page_disables_delete_rendering():
    client = app.test_client()
    user = {"username": "student_a1", "role": "student", "class_id": 1}
    with patch("server.current_user", return_value=user):
        response = client.get("/materials")
    body = response.get_data(as_text=True)
    assert "const canDeleteMaterials = false;" in body
    assert "if (canDeleteMaterials && item.subject_id === selectedSubjectId())" in body


def test_role_navigation_is_server_rendered_without_account_switcher():
    client = app.test_client()
    with patch("server.current_user", return_value={"username": "teacher_a", "role": "teacher", "class_id": 1}):
        teacher_body = client.get("/materials").get_data(as_text=True)
    with patch("server.current_user", return_value={"username": "student_a1", "role": "student", "class_id": 1}):
        student_body = client.get("/materials").get_data(as_text=True)
    assert 'data-nav-view="materials"' in teacher_body
    assert 'data-nav-view="retrieve"' in teacher_body
    assert 'data-nav-view="ask"' in teacher_body
    assert 'data-nav-view="class-admin"' not in teacher_body
    assert 'data-nav-view="super-admin"' not in teacher_body
    assert '当前账号：teacher_a' in teacher_body
    assert '切换账号' not in teacher_body
    assert '切换角色' not in teacher_body
    assert 'data-nav-view="materials"' in student_body
    assert 'id="upload-form"' not in student_body


def test_workspace_navigation_has_allowlisted_view_and_mobile_toggle_hooks():
    client = app.test_client()
    with patch("server.current_user", return_value={"username": "teacher_a", "role": "teacher", "class_id": 1}):
        body = client.get("/materials").get_data(as_text=True)
    assert 'id="nav-toggle"' in body
    assert 'id="workspace-sidebar"' in body
    assert "const validViews = new Set" in body
    assert "activateWorkspaceView" in body
    assert "aria-current" in body


def test_teacher_page_has_subject_required_upload_and_scoped_controls():
    client = app.test_client()
    with patch("server.current_user", return_value={"username": "teacher_a", "role": "teacher", "class_id": 1}):
        body = client.get("/materials").get_data(as_text=True)
    assert 'id="subject-select"' in body
    assert 'name="subject_id"' in body
    assert "form.hidden = !selected || selected.status !== 'active'" in body
    assert "item.subject_name" in body


def test_student_page_has_all_subject_read_only_browser_and_subject_citations():
    client = app.test_client()
    with patch("server.current_user", return_value={"username": "student_a1", "role": "student", "class_id": 1}):
        body = client.get("/materials").get_data(as_text=True)
    assert "const canReadMaterials = true;" in body
    assert "subjectPayload({query:" in body
    assert "citation.subject_name" in body
    assert 'id="upload-form"' not in body


def test_administration_roles_receive_only_their_management_panels():
    client = app.test_client()
    with patch("server.current_user", return_value={"username": "class_admin_a", "role": "class_admin", "class_id": 1}):
        class_body = client.get("/materials").get_data(as_text=True)
    with patch("server.current_user", return_value={"username": "super_admin", "role": "super_admin", "class_id": 1}):
        super_body = client.get("/materials").get_data(as_text=True)
    assert 'id="class-admin-panel"' in class_body
    assert "const canManageClass = true;" in class_body
    assert 'id="super-admin-panel"' in super_body
    assert "const canManageAdmins = true;" in super_body
    assert "/api/admin/class-admins" in super_body
