"""Additive, repeatable lesson-six migration; never rewrites existing content."""
from sqlalchemy import inspect, text
from .extensions import db

VERSION = "20261021_mcp_tools"

def prepare_mcp_upgrade():
    inspector = inspect(db.engine)
    for table, column, ddl in (("conversations", "mcp_attempt_count", "INTEGER NOT NULL DEFAULT 0 CHECK (mcp_attempt_count >= 0)"), ("messages", "tool_calls_json", "JSON NOT NULL DEFAULT '[]'")):
        if table in inspector.get_table_names() and column not in {c["name"] for c in inspector.get_columns(table)}:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    db.session.commit()

def finish_mcp_upgrade():
    from .database import _record_schema_upgrade
    _record_schema_upgrade(VERSION)
