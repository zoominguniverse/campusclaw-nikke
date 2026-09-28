import io

from app.database import db
from app.models import KnowledgeEntry, Material, User

from .conftest import login


def test_seeded_users_are_hashed_and_class_scoped(app):
    with app.app_context():
        teacher = User.query.filter_by(username="teacher_a").one()
        teacher_b = User.query.filter_by(username="teacher_b").one()
        student_a2 = User.query.filter_by(username="student_a2").one()
        student_b = User.query.filter_by(username="student_b1").one()
        assert teacher.password_hash != "teacher-password"
        assert teacher.password_hash.startswith("$2")
        assert teacher.class_id != student_b.class_id
        assert teacher.role == "teacher"
        assert teacher_b.role == "teacher"
        assert {student_a2.role, student_b.role} == {"student"}
        assert User.query.count() == 6


def test_second_teacher_is_limited_to_own_class(app, client):
    login(client, "teacher_b", "teacher-b-password")
    assert client.get("/api/classes/2/materials").status_code == 200
    forbidden = client.get("/api/classes/1/materials")
    assert forbidden.status_code == 403


def test_all_seeded_students_are_read_only(app):
    students = (
        ("student_a1", "student-a-password", 1),
        ("student_a2", "student-a2-password", 1),
        ("student_b1", "student-b-password", 2),
        ("student_b2", "student-b2-password", 2),
    )
    for username, password, class_id in students:
        client = app.test_client()
        token = login(client, username, password)
        response = client.post(
            f"/api/classes/{class_id}/materials",
            data={"file": (io.BytesIO(b"student content"), "student.md")},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 403


def test_unauthenticated_api_is_rejected_without_material_data(client):
    response = client.get("/api/classes/1/materials")
    assert response.status_code == 401
    assert "A 班" not in response.get_data(as_text=True)


def test_invalid_password_does_not_create_a_session(client):
    response = client.post("/api/auth/login", json={"username": "teacher_a", "password": "wrong-password"})
    assert response.status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_login_response_returns_top_level_identity_fields_only(client):
    response = client.post("/api/auth/login", json={"username": "teacher_a", "password": "teacher-password"})
    assert response.status_code == 200
    assert response.get_json() == {"username": "teacher_a", "role": "teacher", "class_id": 1}


def test_new_login_revokes_all_previous_sessions_for_the_same_user(app):
    first_client = app.test_client()
    second_client = app.test_client()
    login(first_client, "teacher_a", "teacher-password")
    assert first_client.get("/api/auth/me").status_code == 200

    login(second_client, "teacher_a", "teacher-password")
    assert second_client.get("/api/auth/me").status_code == 200
    assert first_client.get("/api/auth/me").status_code == 401


def test_logout_revokes_the_current_session(client):
    token = login(client, "teacher_a", "teacher-password")
    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_student_upload_is_forbidden_without_side_effects(app, client):
    token = login(client, "student_a1", "student-a-password")
    with app.app_context():
        before_materials = Material.query.count()
        before_entries = KnowledgeEntry.query.count()
    response = client.post(
        "/api/classes/1/materials",
        data={"file": (io.BytesIO(b"student content"), "student.md")},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 403
    with app.app_context():
        assert Material.query.count() == before_materials
        assert KnowledgeEntry.query.count() == before_entries
    update = client.put(
        "/api/classes/1/materials/not-a-real-id",
        json={"title": "student attempt"},
        headers={"X-CSRF-Token": token},
    )
    assert update.status_code == 403


def test_cross_class_list_is_forbidden_and_does_not_leak(client):
    login(client, "student_a1", "student-a-password")
    response = client.get("/api/classes/2/materials")
    assert response.status_code == 403
    assert "B 班" not in response.get_data(as_text=True)


def test_cross_class_material_id_is_forbidden(app, client):
    with app.app_context():
        material = Material.query.filter_by(class_id=2).first()
        material_id = material.id
    login(client, "student_a1", "student-a-password")
    response = client.get(f"/api/classes/1/materials/{material_id}")
    assert response.status_code == 403
    assert "B 班" not in response.get_data(as_text=True)


def test_same_class_material_preview_returns_parsed_text(app, client):
    with app.app_context():
        material = Material.query.filter_by(class_id=1).first()
        material_id = material.id
    login(client, "student_a1", "student-a-password")
    response = client.get(f"/api/classes/1/materials/{material_id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["material"]["id"] == material_id
    assert payload["body_text"] == "A 班示例材料内容"


def test_same_class_user_can_download_seeded_material(app, client):
    with app.app_context():
        material = Material.query.filter_by(class_id=1).first()
        expected = KnowledgeEntry.query.filter_by(material_id=material.id).one().body_text.encode("utf-8")
    login(client, "student_a1", "student-a-password")
    response = client.get(f"/api/classes/1/materials/{material.id}/download")
    assert response.status_code == 200
    assert response.data == expected
    assert "attachment" in response.headers["Content-Disposition"]
    assert material.original_filename in response.headers["Content-Disposition"]


def test_uploaded_material_downloads_without_storage_path_leakage(app, client):
    token = login(client, "teacher_a", "teacher-password")
    created = client.post(
        "/api/classes/1/materials",
        data={"file": (io.BytesIO(b"downloadable lesson"), "lesson.md")},
        headers={"X-CSRF-Token": token},
    )
    material_id = created.get_json()["material"]["id"]
    with app.app_context():
        material = db.session.get(Material, material_id)
        storage_path = material.storage_path
    response = client.get(f"/api/classes/1/materials/{material_id}/download")
    assert response.status_code == 200
    assert response.data == b"downloadable lesson"
    assert "attachment" in response.headers["Content-Disposition"]
    assert "lesson.md" in response.headers["Content-Disposition"]
    assert storage_path not in response.headers["Content-Disposition"]


def test_cross_class_material_download_is_forbidden(app, client):
    with app.app_context():
        material_id = Material.query.filter_by(class_id=2).first().id
    login(client, "student_a1", "student-a-password")
    response = client.get(f"/api/classes/1/materials/{material_id}/download")
    assert response.status_code == 403
    assert response.data == b'{"error":"class access denied"}\n'


def test_missing_csrf_token_rejects_a_state_change(client):
    login(client, "teacher_a", "teacher-password")
    response = client.post(
        "/api/classes/1/materials",
        data={"file": (io.BytesIO(b"content"), "lesson.md")},
    )
    assert response.status_code == 403


def test_teacher_upload_creates_material_and_knowledge_record(app, client):
    token = login(client, "teacher_a", "teacher-password")
    response = client.post(
        "/api/classes/1/materials",
        data={"title": "A 班新材料", "file": (io.BytesIO("课程正文".encode()), "lesson.md")},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    material_id = response.get_json()["material"]["id"]
    with app.app_context():
        material = db.session.get(Material, material_id)
        entry = KnowledgeEntry.query.filter_by(material_id=material_id, class_id=1).one()
        assert material.class_id == 1
        assert entry.body_text == "课程正文"
    listed = client.get("/api/classes/1/materials")
    assert listed.status_code == 200
    assert any(item["id"] == material_id for item in listed.get_json()["items"])
    student_client = app.test_client()
    login(student_client, "student_a1", "student-a-password")
    student_list = student_client.get("/api/classes/1/materials")
    assert any(item["id"] == material_id for item in student_list.get_json()["items"])


def test_invalid_upload_creates_no_record(app, client):
    token = login(client, "teacher_a", "teacher-password")
    with app.app_context():
        before = Material.query.count()
    response = client.post(
        "/api/classes/1/materials",
        data={"file": (io.BytesIO(b"not allowed"), "lesson.pdf")},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 400
    with app.app_context():
        assert Material.query.count() == before


def test_upload_direct_error_paths(client):
    unauthenticated = client.post(
        "/api/classes/1/materials",
        data={"file": (io.BytesIO(b"content"), "lesson.md")},
    )
    assert unauthenticated.status_code == 401
    token = login(client, "teacher_a", "teacher-password")
    cross_class = client.post(
        "/api/classes/2/materials",
        data={"file": (io.BytesIO(b"content"), "lesson.md")},
        headers={"X-CSRF-Token": token},
    )
    assert cross_class.status_code == 403
    malformed = client.post("/api/classes/1/materials", headers={"X-CSRF-Token": token})
    assert malformed.status_code == 400


def test_cross_class_mutation_is_forbidden(client):
    token = login(client, "teacher_a", "teacher-password")
    response = client.put(
        "/api/classes/2/materials/not-a-real-id",
        json={"title": "attempt"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 403


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
