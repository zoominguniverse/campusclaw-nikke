import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("DEMO_TEACHER_PASSWORD", "teacher-password")
os.environ.setdefault("DEMO_TEACHER_B_PASSWORD", "teacher-b-password")
os.environ.setdefault("DEMO_STUDENT_A_PASSWORD", "student-a-password")
os.environ.setdefault("DEMO_STUDENT_A2_PASSWORD", "student-a2-password")
os.environ.setdefault("DEMO_STUDENT_B_PASSWORD", "student-b-password")
os.environ.setdefault("DEMO_STUDENT_B2_PASSWORD", "student-b2-password")
os.environ.setdefault("DEMO_SUPER_ADMIN_PASSWORD", "super-admin-password")
os.environ.setdefault("DEMO_CLASS_ADMIN_A_PASSWORD", "class-admin-a-password")
os.environ.setdefault("DEMO_TEACHER_A2_PASSWORD", "teacher-a2-password")

from app import create_app
from app.database import db


@pytest.fixture()
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-secret",
            # Compose delegates startup initialization to init_db.py, but each
            # isolated SQLite test app must create its own schema explicitly.
            "INITIALIZE_DATABASE": True,
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "SEED_DEMO_DATA": True,
            "DEMO_TEACHER_PASSWORD": "teacher-password",
            "DEMO_TEACHER_B_PASSWORD": "teacher-b-password",
            "DEMO_STUDENT_A_PASSWORD": "student-a-password",
            "DEMO_STUDENT_A2_PASSWORD": "student-a2-password",
            "DEMO_STUDENT_B_PASSWORD": "student-b-password",
            "DEMO_STUDENT_B2_PASSWORD": "student-b2-password",
            "DEMO_SUPER_ADMIN_PASSWORD": "super-admin-password",
            "DEMO_CLASS_ADMIN_A_PASSWORD": "class-admin-a-password",
            "DEMO_TEACHER_A2_PASSWORD": "teacher-a2-password",
            "FRONTEND_ORIGIN": "http://localhost:5173",
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    identity = response.get_json()
    assert set(identity) == {"username", "role", "class_id"}
    return client.get("/api/auth/me").get_json()["csrf_token"]
