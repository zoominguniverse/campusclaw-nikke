from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Role(db.Model):
    __tablename__ = "roles"
    name = db.Column(db.String(32), primary_key=True)


class SchoolClass(db.Model):
    __tablename__ = "classes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), db.ForeignKey("roles.name"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class ClassMembership(db.Model):
    __tablename__ = "class_memberships"
    __table_args__ = (db.UniqueConstraint("user_id", "class_id", name="uq_membership_user_class"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    is_teacher = db.Column(db.Boolean, nullable=False, default=False)


class LoginSession(db.Model):
    __tablename__ = "sessions"
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class Material(db.Model):
    __tablename__ = "materials"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(512), nullable=False)
    content_type = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeEntry(db.Model):
    __tablename__ = "knowledge_entries"
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String(36), db.ForeignKey("materials.id"), nullable=False, unique=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    body_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)


class Assistant(db.Model):
    __tablename__ = "assistants"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)


class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
