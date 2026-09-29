from __future__ import annotations

from flask import current_app
from sqlalchemy import inspect, text
from .extensions import db
from .models import (
    Assistant,
    Assignment,
    ClassMembership,
    ClassAdminGrant,
    ClassSubject,
    KnowledgeEntry,
    KnowledgeChunk,
    Material,
    Role,
    SchemaMigration,
    SchoolClass,
    Skill,
    User,
    TeacherSubjectAssignment,
    utc_now,
)
from .security import hash_password


def initialize_database() -> None:
    _install_postgres_extensions()
    db.create_all()
    _upgrade_subject_schema()
    _install_retrieval_indexes()
    _record_schema_upgrade("20260929_traceable_retrieval")
    if current_app.config["SEED_DEMO_DATA"]:
        seed_demo_data()
    _migrate_subject_ownership()
    _enforce_subject_ownership()
    # Existing materials receive an idempotent auto-strategy generation at startup.
    from .indexing import backfill_entries

    backfill_entries()


def _add_column_if_missing(table: str, column: str, ddl: str) -> None:
    if column not in {item["name"] for item in inspect(db.engine).get_columns(table)}:
        db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
        db.session.commit()


def _upgrade_subject_schema() -> None:
    """Perform additive upgrades because create_all does not alter live tables."""
    active_default = "TRUE" if db.engine.dialect.name == "postgresql" else "1"
    _add_column_if_missing("users", "is_active", f"is_active BOOLEAN NOT NULL DEFAULT {active_default}")
    _add_column_if_missing("materials", "subject_id", "subject_id INTEGER")
    _add_column_if_missing("knowledge_entries", "subject_id", "subject_id INTEGER")
    _add_column_if_missing("knowledge_chunks", "subject_id", "subject_id INTEGER")
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_materials_class_subject ON materials (class_id, subject_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_entries_class_subject ON knowledge_entries (class_id, subject_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_class_subject_status_ready ON knowledge_chunks (class_id, subject_id) WHERE index_status = 'ready'"))
        db.session.commit()
    _record_schema_upgrade("20260929_subject_scoped_materials")


def _history_subject(school_class: SchoolClass) -> ClassSubject:
    subject = ClassSubject.query.filter_by(class_id=school_class.id, subject_key="historical").one_or_none()
    if not subject:
        subject = ClassSubject(
            class_id=school_class.id,
            subject_key="historical",
            name="历史待归档",
            normalized_name="历史待归档",
            status="archived",
        )
        db.session.add(subject)
        db.session.flush()
    return subject


def _migrate_subject_ownership() -> None:
    """Idempotently give all pre-subject material data a safe class-local owner."""
    changed = False
    for school_class in SchoolClass.query.all():
        history = _history_subject(school_class)
        materials = Material.query.filter_by(class_id=school_class.id, subject_id=None).all()
        for material in materials:
            material.subject_id = history.id
            entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=school_class.id).one_or_none()
            if entry:
                entry.subject_id = history.id
                KnowledgeChunk.query.filter_by(knowledge_entry_id=entry.id, subject_id=None).update(
                    {KnowledgeChunk.subject_id: history.id}, synchronize_session=False
                )
            # Retain existing teacher owners' ability to move/reorganize their legacy work.
            owner = db.session.get(User, material.uploader_id)
            membership = ClassMembership.query.filter_by(user_id=material.uploader_id, class_id=school_class.id, is_teacher=True).one_or_none()
            if owner and owner.role == "teacher" and membership and not TeacherSubjectAssignment.query.filter_by(teacher_id=owner.id, subject_id=history.id).one_or_none():
                db.session.add(TeacherSubjectAssignment(teacher_id=owner.id, subject_id=history.id, granted_by=None, is_active=True))
            changed = True
        # Repair interrupted runs where a material was migrated before its entry/chunks.
        for entry in KnowledgeEntry.query.filter_by(class_id=school_class.id, subject_id=None).all():
            material = db.session.get(Material, entry.material_id)
            entry.subject_id = material.subject_id if material and material.subject_id else history.id
            KnowledgeChunk.query.filter_by(knowledge_entry_id=entry.id, subject_id=None).update(
                {KnowledgeChunk.subject_id: entry.subject_id}, synchronize_session=False
            )
            changed = True
    if changed:
        db.session.commit()


def _enforce_subject_ownership() -> None:
    """PostgreSQL enforces the post-backfill invariant even for direct SQL writes."""
    if db.engine.dialect.name != "postgresql":
        return
    try:
        for table in ("materials", "knowledge_entries", "knowledge_chunks"):
            db.session.execute(text(f"ALTER TABLE {table} ALTER COLUMN subject_id SET NOT NULL"))
        db.session.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION campusclaw_subject_matches_class()
                RETURNS trigger AS $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM class_subjects
                    WHERE id = NEW.subject_id AND class_id = NEW.class_id
                  ) THEN
                    RAISE EXCEPTION 'subject does not belong to material class';
                  END IF;
                  RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
                """
            )
        )
        for table in ("materials", "knowledge_entries", "knowledge_chunks"):
            db.session.execute(text(f"DROP TRIGGER IF EXISTS trg_{table}_subject_class ON {table}"))
            db.session.execute(
                text(
                    f"CREATE TRIGGER trg_{table}_subject_class BEFORE INSERT OR UPDATE OF class_id, subject_id "
                    f"ON {table} FOR EACH ROW EXECUTE FUNCTION campusclaw_subject_matches_class()"
                )
            )
        db.session.commit()
        _record_schema_upgrade("20260929_subject_ownership_constraints")
    except Exception as error:
        db.session.rollback()
        raise RuntimeError("PostgreSQL subject ownership constraints could not be installed") from error


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

    for role_name in ("super_admin", "class_admin", "teacher", "student"):
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

    math_a = _ensure_subject(class_a, "mathematics", "数学")
    language_a = _ensure_subject(class_a, "language", "语文")
    english_b = _ensure_subject(class_b, "english", "英语")

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
    _ensure_teacher_assignment(teacher_a, math_a)
    _ensure_teacher_assignment(teacher_b, english_b)
    _seed_material(class_a, math_a, teacher_a, "A 班教学示例材料", "A 班示例材料内容")
    _seed_material(class_b, english_b, teacher_b, "B 班教学示例材料", "B 班示例材料内容")

    optional_users = (
        ("super_admin", "super_admin", class_a.id, current_app.config["DEMO_SUPER_ADMIN_PASSWORD"]),
        ("class_admin_a", "class_admin", class_a.id, current_app.config["DEMO_CLASS_ADMIN_A_PASSWORD"]),
        ("teacher_a2", "teacher", class_a.id, current_app.config["DEMO_TEACHER_A2_PASSWORD"]),
    )
    for username, role, class_id, password in optional_users:
        if not password:
            continue
        user = User.query.filter_by(username=username).one_or_none()
        if not user:
            user = User(username=username, role=role, class_id=class_id, password_hash=hash_password(password))
            db.session.add(user)
            db.session.flush()
        if role == "class_admin" and not ClassAdminGrant.query.filter_by(admin_user_id=user.id, class_id=class_id).one_or_none():
            db.session.add(ClassAdminGrant(admin_user_id=user.id, class_id=class_id, created_by=None))
        if role == "teacher":
            if not ClassMembership.query.filter_by(user_id=user.id, class_id=class_id).one_or_none():
                db.session.add(ClassMembership(user_id=user.id, class_id=class_id, is_teacher=True))
            _ensure_teacher_assignment(user, language_a)

    if not Assignment.query.first():
        db.session.add(Assignment(class_id=class_a.id, title="A 班占位作业"))
    if not Assistant.query.first():
        db.session.add(Assistant(name="课程助手占位"))
    if not Skill.query.first():
        db.session.add(Skill(name="材料管理占位技能"))
    db.session.commit()


def _ensure_subject(school_class: SchoolClass, key: str, name: str) -> ClassSubject:
    subject = ClassSubject.query.filter_by(class_id=school_class.id, subject_key=key).one_or_none()
    if not subject:
        subject = ClassSubject(class_id=school_class.id, subject_key=key, name=name, normalized_name=name.casefold())
        db.session.add(subject)
        db.session.flush()
    return subject


def _ensure_teacher_assignment(teacher: User, subject: ClassSubject) -> None:
    if not TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id, subject_id=subject.id).one_or_none():
        db.session.add(TeacherSubjectAssignment(teacher_id=teacher.id, subject_id=subject.id, granted_by=None))


def _seed_material(school_class: SchoolClass, subject: ClassSubject, uploader: User, title: str, body_text: str) -> None:
    existing = Material.query.filter_by(class_id=school_class.id, title=title).one_or_none()
    if existing:
        if existing.uploader_id != uploader.id:
            existing.uploader_id = uploader.id
        return
    material = Material(
        class_id=school_class.id,
        subject_id=subject.id,
        uploader_id=uploader.id,
        title=title,
        original_filename=f"{school_class.code}-seed.md",
        storage_path="seeded",
        content_type="text/markdown",
    )
    db.session.add(material)
    db.session.flush()
    db.session.add(KnowledgeEntry(material_id=material.id, class_id=school_class.id, subject_id=subject.id, body_text=body_text))
