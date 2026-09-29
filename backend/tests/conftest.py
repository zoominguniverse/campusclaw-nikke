import os
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
import bcrypt

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite://")

DEMO_ACCOUNT_PASSWORDS = {
    "zhangruoxi": "super-admin-password",
    "liuyifei": "class-admin-a-password",
    "chenwanqing": "class-admin-b-password",
    "zhouziyan": "class-admin-c-password",
    "linzimo": "teacher-password",
    "wangyuxin": "teacher-a2-password",
    "chenzixuan": "teacher-c-password",
    "zhoumingyuan": "teacher-d-password",
    "liqinghe": "teacher-e-password",
    "sunwanru": "teacher-f-password",
    "hejiayi": "teacher-g-password",
    "songxinyue": "teacher-b-password",
    "panhaoran": "teacher-h-password",
    "wumengyao": "teacher-i-password",
    "gaoxiaoyu": "teacher-j-password",
    "taoyichen": "teacher-k-password",
    "xiaowenhao": "teacher-l-password",
    "luojingyan": "teacher-m-password",
    "shenqianyu": "teacher-n-password",
    "guoxinyi": "teacher-o-password",
    "yeyuhan": "teacher-p-password",
    "zhouchengxi": "student-a-password",
    "xiewanqing": "student-b-password",
    "chendongyi": "student-c-password",
}
LEGACY_TEST_USERNAMES = {
    "super_admin": "zhangruoxi",
    "class_admin_a": "liuyifei",
    "teacher_a": "linzimo",
    "teacher_a2": "wangyuxin",
    "teacher_b": "songxinyue",
    "student_a1": "zhouchengxi",
    "student_a2": "zhouchengxi",
    "student_b1": "xiewanqing",
    "student_b2": "chendongyi",
}
os.environ.setdefault("DEMO_ACCOUNT_PASSWORDS", json.dumps(DEMO_ACCOUNT_PASSWORDS))

from app import create_app
from app import database
from app.database import db


def _test_hash_password(password: str) -> str:
    """Keep the large fixed fixture practical while production retains its default cost."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode("utf-8")


database.hash_password = _test_hash_password


@pytest.fixture()
def app():
    upload_dir = Path(__file__).resolve().parent.parent / ".pytest-uploads" / uuid4().hex
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-secret",
            # Compose delegates startup initialization to init_db.py, but each
            # isolated SQLite test app must create its own schema explicitly.
            "INITIALIZE_DATABASE": True,
            "UPLOAD_DIR": str(upload_dir),
            "SEED_DEMO_DATA": True,
            "DEMO_ACCOUNT_PASSWORDS": DEMO_ACCOUNT_PASSWORDS,
            "FRONTEND_ORIGIN": "http://localhost:5173",
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
    shutil.rmtree(upload_dir, ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username, password):
    username = LEGACY_TEST_USERNAMES.get(username, username)
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    identity = response.get_json()
    assert set(identity) == {"username", "role", "class_id"}
    return client.get("/api/auth/me").get_json()["csrf_token"]
