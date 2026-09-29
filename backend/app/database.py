from __future__ import annotations

from flask import current_app
from sqlalchemy import text
from .extensions import db
from .models import (
    Assistant,
    Assignment,
    ClassMembership,
    KnowledgeEntry,
    Material,
    Role,
    SchemaMigration,
    SchoolClass,
    Skill,
    User,
)
from .security import hash_password


def initialize_database() -> None:
    _install_postgres_extensions()
    db.create_all()
    _install_retrieval_indexes()
    _record_schema_upgrade("20260929_traceable_retrieval")
    if current_app.config["SEED_DEMO_DATA"]:
        seed_demo_data()
    # Existing materials receive an idempotent auto-strategy generation at startup.
    from .indexing import backfill_entries

    backfill_entries()


def _install_postgres_extensions() -> None:
    """Fail early in PostgreSQL if the retrieval extensions are unavailable."""
    if db.engine.dialect.name != "postgresql":
        return
    try:
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        raise RuntimeError("PostgreSQL pgvector and pg_trgm extensions are required") from error


def _record_schema_upgrade(version: str) -> None:
    if not db.session.get(SchemaMigration, version):
        db.session.add(SchemaMigration(version=version))
        db.session.commit()


def _install_retrieval_indexes() -> None:
    if db.engine.dialect.name != "postgresql":
        return
    try:
        db.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_text_trgm "
                "ON knowledge_chunks USING gin (chunk_text gin_trgm_ops) "
                "WHERE index_status = 'ready'"
            )
        )
        db.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_cosine "
                "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
                "WHERE index_status = 'ready' AND embedding IS NOT NULL"
            )
        )
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        raise RuntimeError("PostgreSQL retrieval indexes could not be created") from error


def seed_demo_data() -> None:
    required_passwords = {
        "teacher_a": current_app.config["DEMO_TEACHER_PASSWORD"],
        "teacher_b": current_app.config["DEMO_TEACHER_B_PASSWORD"],
        "student_a1": current_app.config["DEMO_STUDENT_A_PASSWORD"],
        "student_a2": current_app.config["DEMO_STUDENT_A2_PASSWORD"],
        "student_b1": current_app.config["DEMO_STUDENT_B_PASSWORD"],
        "student_b2": current_app.config["DEMO_STUDENT_B2_PASSWORD"],
    }
    missing = [name for name, password in required_passwords.items() if not password]
    if missing:
        raise RuntimeError("demo seed mode requires passwords for all demo accounts")

    for role_name in ("teacher", "student"):
        if not db.session.get(Role, role_name):
            db.session.add(Role(name=role_name))

    class_a = SchoolClass.query.filter_by(code="A").one_or_none()
    if not class_a:
        class_a = SchoolClass(code="A", name="A 班")
        db.session.add(class_a)
    class_b = SchoolClass.query.filter_by(code="B").one_or_none()
    if not class_b:
        class_b = SchoolClass(code="B", name="B 班")
        db.session.add(class_b)
    db.session.flush()

    demo_users = (
        ("teacher_a", "teacher", class_a.id, required_passwords["teacher_a"]),
        ("student_a1", "student", class_a.id, required_passwords["student_a1"]),
        ("student_a2", "student", class_a.id, required_passwords["student_a2"]),
        ("teacher_b", "teacher", class_b.id, required_passwords["teacher_b"]),
        ("student_b1", "student", class_b.id, required_passwords["student_b1"]),
        ("student_b2", "student", class_b.id, required_passwords["student_b2"]),
    )
    for username, role, class_id, password in demo_users:
        user = User.query.filter_by(username=username).one_or_none()
        if not user:
            user = User(
                    username=username,
                    role=role,
                    class_id=class_id,
                    password_hash=hash_password(password),
            )
            db.session.add(user)
            db.session.flush()
        if not ClassMembership.query.filter_by(user_id=user.id, class_id=class_id).one_or_none():
            db.session.add(ClassMembership(user_id=user.id, class_id=class_id, is_teacher=role == "teacher"))
    db.session.flush()

    teacher_a = User.query.filter_by(username="teacher_a").one()
    teacher_b = User.query.filter_by(username="teacher_b").one()
    _seed_material(class_a, teacher_a, "A 班教学示例材料", "A 班示例材料内容")
    _seed_material(class_b, teacher_b, "B 班教学示例材料", "B 班示例材料内容")

    if not Assignment.query.first():
        db.session.add(Assignment(class_id=class_a.id, title="A 班占位作业"))
    if not Assistant.query.first():
        db.session.add(Assistant(name="课程助手占位"))
    if not Skill.query.first():
        db.session.add(Skill(name="材料管理占位技能"))
    db.session.commit()


def _seed_material(school_class: SchoolClass, uploader: User, title: str, body_text: str) -> None:
    existing = Material.query.filter_by(class_id=school_class.id, title=title).one_or_none()
    if existing:
        if existing.uploader_id != uploader.id:
            existing.uploader_id = uploader.id
        return
    material = Material(
        class_id=school_class.id,
        uploader_id=uploader.id,
        title=title,
        original_filename=f"{school_class.code}-seed.md",
        storage_path="seeded",
        content_type="text/markdown",
    )
    db.session.add(material)
    db.session.flush()
    db.session.add(KnowledgeEntry(material_id=material.id, class_id=school_class.id, body_text=body_text))
