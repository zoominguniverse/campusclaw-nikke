"""Additive upgrade for the original unscoped id/name skills placeholder."""
from sqlalchemy import inspect, text

from .extensions import db

VERSION = "20261014_tutor_conversations"
SKILL_COLUMNS = {
    "class_id": "INTEGER REFERENCES classes(id)",
    "trigger_text": "VARCHAR(120) NOT NULL DEFAULT ''",
    "description": "TEXT NOT NULL DEFAULT ''",
    "tools_json": "JSON NOT NULL DEFAULT '[]'",
    "source_text": "TEXT NOT NULL DEFAULT ''",
    "subject_text": "VARCHAR(32) NOT NULL DEFAULT ''",
    "enabled": "BOOLEAN NOT NULL DEFAULT FALSE",
    "legacy_placeholder": "BOOLEAN NOT NULL DEFAULT TRUE",
    "seed_key": "VARCHAR(64)",
    "created_by": "INTEGER REFERENCES users(id)",
    "updated_by": "INTEGER REFERENCES users(id)",
    "created_at": "TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:00'",
    "updated_at": "TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:00'",
}
DEFINITION = "legacy_placeholder OR (class_id IS NOT NULL AND length(name) BETWEEN 1 AND 32 AND length(trigger_text) BETWEEN 1 AND 120 AND length(description) BETWEEN 1 AND 2000 AND length(source_text) <= 8000 AND length(subject_text) <= 32)"


def prepare_tutor_upgrade():
    if "skills" not in inspect(db.engine).get_table_names():
        return
    columns = {c["name"] for c in inspect(db.engine).get_columns("skills")}
    for name, ddl in SKILL_COLUMNS.items():
        if name not in columns:
            db.session.execute(text(f"ALTER TABLE skills ADD COLUMN {name} {ddl}"))
    db.session.commit()


def finish_tutor_upgrade():
    for name, fields in [("uq_skill_class_name", "class_id, name"), ("uq_skill_class_seed", "class_id, seed_key")]:
        db.session.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON skills ({fields})"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_skills_class_id ON skills (class_id)"))
    constraints = {c["name"] for c in inspect(db.engine).get_check_constraints("skills")}
    checks = {"ck_skill_definition": DEFINITION, "ck_skill_legacy_disabled": "NOT legacy_placeholder OR NOT enabled"}
    for name, expression in checks.items():
        if name in constraints:
            continue
        if db.engine.dialect.name == "postgresql":
            db.session.execute(text(f"ALTER TABLE skills ADD CONSTRAINT {name} CHECK ({expression})"))
        else:
            # SQLite cannot add CHECK to an existing table. Triggers preserve old rows
            # without rebuilding tables or disabling referential constraints.
            import re
            new_expression = re.sub(r"\b(class_id|name|trigger_text|description|source_text|subject_text|legacy_placeholder|enabled)\b", r"NEW.\1", expression)
            for operation in ("INSERT", "UPDATE"):
                db.session.execute(text(f"CREATE TRIGGER IF NOT EXISTS {name}_{operation.lower()} BEFORE {operation} ON skills WHEN NOT ({new_expression}) BEGIN SELECT RAISE(ABORT, '{name}'); END"))
    db.session.commit()
    from .database import _record_schema_upgrade
    _record_schema_upgrade(VERSION)
