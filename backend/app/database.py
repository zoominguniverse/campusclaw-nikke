from __future__ import annotations

import json

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
    KnowledgeIndexGeneration,
    LoginSession,
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


DEMO_CLASSES = (
    ("1", "1 班"),
    ("2", "2 班"),
    ("3", "3 班"),
)
DEMO_SUBJECTS = (
    ("mathematics", "数学"),
    ("language", "语文"),
    ("english", "英语"),
    ("physics", "物理"),
    ("chemistry", "化学"),
    ("biology", "生物"),
)
# These usernames are pinyin renderings of Chinese personal-style names.  The
# roster is fixed so seeding can be safely re-run without account duplication.
DEMO_USERS = (
    ("zhangruoxi", "super_admin", "1"),
    ("liuyifei", "class_admin", "1"),
    ("chenwanqing", "class_admin", "2"),
    ("zhouziyan", "class_admin", "3"),
    ("linzimo", "teacher", "1"),  # Shared mathematics teacher for 1/2 班.
    ("wangyuxin", "teacher", "1"),
    ("chenzixuan", "teacher", "1"),
    ("zhoumingyuan", "teacher", "1"),
    ("liqinghe", "teacher", "1"),
    ("sunwanru", "teacher", "1"),
    ("hejiayi", "teacher", "2"),
    ("songxinyue", "teacher", "2"),
    ("panhaoran", "teacher", "2"),
    ("wumengyao", "teacher", "2"),
    ("gaoxiaoyu", "teacher", "2"),
    ("taoyichen", "teacher", "3"),
    ("xiaowenhao", "teacher", "3"),
    ("luojingyan", "teacher", "3"),
    ("shenqianyu", "teacher", "3"),
    ("guoxinyi", "teacher", "3"),
    ("yeyuhan", "teacher", "3"),
    ("zhouchengxi", "student", "1"),
    ("xiewanqing", "student", "2"),
    ("chendongyi", "student", "3"),
)
DEMO_TEACHER_ASSIGNMENTS = (
    ("linzimo", "1", "mathematics"),
    ("linzimo", "2", "mathematics"),
    ("wangyuxin", "1", "language"),
    ("chenzixuan", "1", "english"),
    ("zhoumingyuan", "1", "physics"),
    ("liqinghe", "1", "chemistry"),
    ("sunwanru", "1", "biology"),
    ("hejiayi", "2", "language"),
    ("songxinyue", "2", "english"),
    ("panhaoran", "2", "physics"),
    ("wumengyao", "2", "chemistry"),
    ("gaoxiaoyu", "2", "biology"),
    ("taoyichen", "3", "language"),
    ("xiaowenhao", "3", "mathematics"),
    ("luojingyan", "3", "english"),
    ("shenqianyu", "3", "physics"),
    ("guoxinyi", "3", "chemistry"),
    ("yeyuhan", "3", "biology"),
)
LEGACY_DEMO_CLASS_CODES = ("A", "B")
LEGACY_DEMO_USERNAMES = frozenset(
    {
        "super_admin",
        "class_admin_a",
        "teacher_a",
        "teacher_a2",
        "teacher_b",
        "student_a1",
        "student_a2",
        "student_b1",
        "student_b2",
    }
)


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
    passwords = _demo_passwords()
    if current_app.config["PURGE_LEGACY_DEMO_DATA"]:
        _purge_legacy_demo_data()

    for role_name in ("super_admin", "class_admin", "teacher", "student"):
        if not db.session.get(Role, role_name):
            db.session.add(Role(name=role_name))

    classes: dict[str, SchoolClass] = {}
    for code, name in DEMO_CLASSES:
        school_class = SchoolClass.query.filter_by(code=code).one_or_none()
        if not school_class:
            school_class = SchoolClass(code=code, name=name)
            db.session.add(school_class)
        classes[code] = school_class
    db.session.flush()

    subjects = {
        (code, key): _ensure_subject(classes[code], key, name)
        for code, _ in DEMO_CLASSES
        for key, name in DEMO_SUBJECTS
    }

    users: dict[str, User] = {}
    for username, role, class_code in DEMO_USERS:
        school_class = classes[class_code]
        user = User.query.filter_by(username=username).one_or_none()
        if not user:
            user = User(
                username=username,
                role=role,
                class_id=school_class.id,
                password_hash=hash_password(passwords[username]),
            )
            db.session.add(user)
            db.session.flush()
        users[username] = user
        if role == "student":
            _ensure_membership(user, school_class, is_teacher=False)

    for username, class_code in (("liuyifei", "1"), ("chenwanqing", "2"), ("zhouziyan", "3")):
        school_class = classes[class_code]
        if not ClassAdminGrant.query.filter_by(admin_user_id=users[username].id, class_id=school_class.id).one_or_none():
            db.session.add(ClassAdminGrant(admin_user_id=users[username].id, class_id=school_class.id, created_by=None))

    for username, class_code, subject_key in DEMO_TEACHER_ASSIGNMENTS:
        teacher = users[username]
        school_class = classes[class_code]
        _ensure_membership(teacher, school_class, is_teacher=True)
        _ensure_teacher_assignment(teacher, subjects[(class_code, subject_key)])

    _seed_material(classes["1"], subjects[("1", "mathematics")], users["linzimo"], "1 班数学示例材料", "1 班数学示例材料内容")
    _seed_material(classes["2"], subjects[("2", "language")], users["hejiayi"], "2 班语文示例材料", "2 班语文示例材料内容")
    _seed_material(classes["3"], subjects[("3", "english")], users["luojingyan"], "3 班英语示例材料", "3 班英语示例材料内容")

    if not Assignment.query.first():
        db.session.add(Assignment(class_id=classes["1"].id, title="1 班占位作业"))
    if not Assistant.query.first():
        db.session.add(Assistant(name="课程助手占位"))
    if not Skill.query.first():
        db.session.add(Skill(name="材料管理占位技能"))
    db.session.commit()


def _purge_legacy_demo_data() -> None:
    """Remove only the former fixed A/B demo graph when explicitly requested."""
    legacy_classes = SchoolClass.query.filter(SchoolClass.code.in_(LEGACY_DEMO_CLASS_CODES)).all()
    if not legacy_classes:
        return
    legacy_class_ids = [school_class.id for school_class in legacy_classes]
    legacy_users = User.query.filter(User.class_id.in_(legacy_class_ids)).all()
    unknown_usernames = {user.username for user in legacy_users} - LEGACY_DEMO_USERNAMES
    if unknown_usernames:
        raise RuntimeError("legacy demo cleanup found non-demo A/B users and will not delete them")
    legacy_user_ids = [user.id for user in legacy_users]
    legacy_subject_ids = [
        subject.id for subject in ClassSubject.query.filter(ClassSubject.class_id.in_(legacy_class_ids)).all()
    ]
    legacy_entry_ids = [
        entry.id for entry in KnowledgeEntry.query.filter(KnowledgeEntry.class_id.in_(legacy_class_ids)).all()
    ]
    if legacy_entry_ids:
        generation_ids = [
            generation.id
            for generation in KnowledgeIndexGeneration.query.filter(
                KnowledgeIndexGeneration.knowledge_entry_id.in_(legacy_entry_ids)
            ).all()
        ]
        if generation_ids:
            KnowledgeChunk.query.filter(KnowledgeChunk.generation_id.in_(generation_ids)).delete(synchronize_session=False)
            KnowledgeIndexGeneration.query.filter(KnowledgeIndexGeneration.id.in_(generation_ids)).delete(synchronize_session=False)
        KnowledgeEntry.query.filter(KnowledgeEntry.id.in_(legacy_entry_ids)).delete(synchronize_session=False)
    KnowledgeChunk.query.filter(KnowledgeChunk.class_id.in_(legacy_class_ids)).delete(synchronize_session=False)
    if legacy_user_ids:
        LoginSession.query.filter(LoginSession.user_id.in_(legacy_user_ids)).delete(synchronize_session=False)
        ClassMembership.query.filter(ClassMembership.user_id.in_(legacy_user_ids)).delete(synchronize_session=False)
        ClassAdminGrant.query.filter(ClassAdminGrant.admin_user_id.in_(legacy_user_ids)).delete(synchronize_session=False)
        TeacherSubjectAssignment.query.filter(TeacherSubjectAssignment.teacher_id.in_(legacy_user_ids)).delete(synchronize_session=False)
    ClassMembership.query.filter(ClassMembership.class_id.in_(legacy_class_ids)).delete(synchronize_session=False)
    ClassAdminGrant.query.filter(ClassAdminGrant.class_id.in_(legacy_class_ids)).delete(synchronize_session=False)
    if legacy_subject_ids:
        TeacherSubjectAssignment.query.filter(TeacherSubjectAssignment.subject_id.in_(legacy_subject_ids)).delete(synchronize_session=False)
    Assignment.query.filter(Assignment.class_id.in_(legacy_class_ids)).delete(synchronize_session=False)
    Material.query.filter(Material.class_id.in_(legacy_class_ids)).delete(synchronize_session=False)
    ClassSubject.query.filter(ClassSubject.class_id.in_(legacy_class_ids)).delete(synchronize_session=False)
    if legacy_user_ids:
        User.query.filter(User.id.in_(legacy_user_ids)).delete(synchronize_session=False)
    SchoolClass.query.filter(SchoolClass.id.in_(legacy_class_ids)).delete(synchronize_session=False)
    db.session.commit()


def _demo_passwords() -> dict[str, str]:
    raw = current_app.config.get("DEMO_ACCOUNT_PASSWORDS", "")
    try:
        passwords = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as error:
        raise RuntimeError("demo seed mode requires a valid complete credential mapping") from error
    if not isinstance(passwords, dict):
        raise RuntimeError("demo seed mode requires a valid complete credential mapping")
    expected = {username for username, _, _ in DEMO_USERS}
    if set(passwords) != expected or any(not isinstance(password, str) or not password.strip() for password in passwords.values()):
        raise RuntimeError("demo seed mode requires a valid complete credential mapping")
    return passwords


def _ensure_membership(user: User, school_class: SchoolClass, *, is_teacher: bool) -> None:
    membership = ClassMembership.query.filter_by(user_id=user.id, class_id=school_class.id).one_or_none()
    if not membership:
        db.session.add(ClassMembership(user_id=user.id, class_id=school_class.id, is_teacher=is_teacher))


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
