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

from app import create_app
from app.database import db


@pytest.fixture()
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-secret",
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "SEED_DEMO_DATA": True,
            "DEMO_TEACHER_PASSWORD": "teacher-password",
            "DEMO_TEACHER_B_PASSWORD": "teacher-b-password",
            "DEMO_STUDENT_A_PASSWORD": "student-a-password",
            "DEMO_STUDENT_A2_PASSWORD": "student-a2-password",
            "DEMO_STUDENT_B_PASSWORD": "student-b-password",
            "DEMO_STUDENT_B2_PASSWORD": "student-b2-password",
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
    return response.get_json()["csrf_token"]
