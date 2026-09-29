from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.database import db, initialize_database
from app.models import ClassAdminGrant, ClassMembership, ClassSubject, Role, SchoolClass, TeacherSubjectAssignment, User

from .conftest import DEMO_ACCOUNT_PASSWORDS


def test_three_class_demo_roster_has_required_scopes_and_shared_mathematics_teacher(app):
    with app.app_context():
        classes = {school_class.code: school_class for school_class in SchoolClass.query.order_by(SchoolClass.code).all()}
        assert {(item.code, item.name) for item in classes.values()} == {("1", "1 班"), ("2", "2 班"), ("3", "3 班")}
        assert ClassSubject.query.filter_by(status="active").count() == 18
        for school_class in classes.values():
            assert {item.name for item in ClassSubject.query.filter_by(class_id=school_class.id, status="active")} == {"语文", "数学", "英语", "物理", "化学", "生物"}

        assert User.query.filter_by(role="super_admin").count() == 1
        assert User.query.filter_by(role="class_admin").count() == 3
        assert User.query.filter_by(role="teacher").count() == 17
        assert User.query.filter_by(role="student").count() == 3
        assert ClassAdminGrant.query.count() == 3
        assert TeacherSubjectAssignment.query.count() == 18

        shared_teacher = User.query.filter_by(username="linzimo", role="teacher").one()
        math_subject_ids = {
            ClassSubject.query.filter_by(class_id=classes[code].id, subject_key="mathematics").one().id
            for code in ("1", "2")
        }
        assert {item.subject_id for item in TeacherSubjectAssignment.query.filter_by(teacher_id=shared_teacher.id, is_active=True)} == math_subject_ids
        assert {item.class_id for item in ClassMembership.query.filter_by(user_id=shared_teacher.id, is_teacher=True)} == {classes["1"].id, classes["2"].id}


def test_demo_fixture_is_idempotent_and_preserves_password_hashes(app):
    with app.app_context():
        before_counts = (
            User.query.count(),
            ClassMembership.query.count(),
            ClassAdminGrant.query.count(),
            ClassSubject.query.count(),
            TeacherSubjectAssignment.query.count(),
        )
        before_hashes = {item.username: item.password_hash for item in User.query.all()}
        initialize_database()
        assert (
            User.query.count(),
            ClassMembership.query.count(),
            ClassAdminGrant.query.count(),
            ClassSubject.query.count(),
            TeacherSubjectAssignment.query.count(),
        ) == before_counts
        assert {item.username: item.password_hash for item in User.query.all()} == before_hashes


def test_explicit_legacy_fixture_purge_removes_only_the_recognized_a_b_demo_data(app):
    with app.app_context():
        legacy_class = SchoolClass(code="A", name="A 班")
        db.session.add(legacy_class)
        db.session.flush()
        legacy_user = User(username="teacher_a", role="teacher", class_id=legacy_class.id, password_hash="test-hash")
        db.session.add(legacy_user)
        db.session.flush()
        db.session.add(ClassMembership(user_id=legacy_user.id, class_id=legacy_class.id, is_teacher=True))
        db.session.commit()

        app.config["PURGE_LEGACY_DEMO_DATA"] = True
        initialize_database()

        assert SchoolClass.query.filter(SchoolClass.code.in_(("A", "B"))).count() == 0
        assert User.query.filter(User.username.in_(("teacher_a", "teacher_b", "student_a1"))).count() == 0
        assert {item.code for item in SchoolClass.query.all()} == {"1", "2", "3"}
        assert User.query.filter_by(role="super_admin").count() == 1
        assert User.query.filter_by(role="class_admin").count() == 3
        assert User.query.filter_by(role="teacher").count() == 17
        assert User.query.filter_by(role="student").count() == 3


def test_incomplete_credential_mapping_leaves_demo_tables_empty():
    from app import create_app

    fixture_root = Path(__file__).resolve().parents[1] / ".pytest-fixture" / uuid4().hex
    fixture_root.mkdir(parents=True)
    database_url = f"sqlite:///{fixture_root / 'incomplete-demo.db'}"
    invalid_passwords = dict(DEMO_ACCOUNT_PASSWORDS)
    invalid_passwords.pop("chendongyi")
    with pytest.raises(RuntimeError, match="complete credential mapping"):
        create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": database_url,
                "SECRET_KEY": "test-secret",
                "UPLOAD_DIR": str(fixture_root / "uploads"),
                "INITIALIZE_DATABASE": True,
                "SEED_DEMO_DATA": True,
                "DEMO_ACCOUNT_PASSWORDS": invalid_passwords,
            }
        )

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": database_url,
            "SECRET_KEY": "test-secret",
            "UPLOAD_DIR": str(fixture_root / "uploads"),
            "INITIALIZE_DATABASE": False,
            "SEED_DEMO_DATA": False,
        }
    )
    with app.app_context():
        assert Role.query.count() == 0
        assert SchoolClass.query.count() == 0
        assert User.query.count() == 0
        db.session.remove()
    shutil.rmtree(fixture_root, ignore_errors=True)


def test_demo_password_documentation_is_a_placeholder_only():
    root = Path(__file__).resolve().parents[2]
    example = (root / ".env.example").read_text(encoding="utf-8")
    assert "DEMO_ACCOUNT_PASSWORDS=" in example
    assert "replace-with-a-local-password" in example
    assert "teacher-password" not in example
