from __future__ import annotations

from uuid import uuid4

from flask import Blueprint, g, jsonify, request

from .auth import json_error, require_auth, require_csrf
from .authorization import effective_class_id, is_class_admin_for, is_super_admin, subject_scope
from .database import db
from .models import ClassAdminGrant, ClassMembership, ClassSubject, KnowledgeChunk, KnowledgeEntry, Material, SchoolClass, TeacherSubjectAssignment, User, utc_now
from .security import hash_password


admin_bp = Blueprint("administration", __name__, url_prefix="/api")


def _class_admin_scope(class_id: int) -> bool:
    return is_super_admin(g.current_user) or is_class_admin_for(g.current_user, class_id)


def _subject_payload(subject: ClassSubject) -> dict:
    return {"id": subject.id, "class_id": subject.class_id, "key": subject.subject_key, "name": subject.name, "status": subject.status}


def _normal_name(value: str) -> str:
    return " ".join((value or "").strip().split()).casefold()


@admin_bp.get("/admin/classes")
@require_auth
def list_admin_classes():
    if not is_super_admin(g.current_user):
        return json_error(403, "super administrator role required")
    return jsonify(items=[{"id": item.id, "code": item.code, "name": item.name} for item in SchoolClass.query.order_by(SchoolClass.id).all()])


@admin_bp.get("/admin/class-admins")
@require_auth
def list_class_admins():
    if not is_super_admin(g.current_user):
        return json_error(403, "super administrator role required")
    admins = User.query.filter_by(role="class_admin").order_by(User.id).all()
    return jsonify(items=[{"id": user.id, "username": user.username, "is_active": user.is_active, "class_ids": [grant.class_id for grant in ClassAdminGrant.query.filter_by(admin_user_id=user.id).all()]} for user in admins])


@admin_bp.post("/admin/class-admins")
@require_auth
@require_csrf
def create_class_admin():
    if not is_super_admin(g.current_user):
        return json_error(403, "super administrator role required")
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    class_id = payload.get("class_id")
    if not username or len(username) > 128 or not password or not isinstance(class_id, int):
        return json_error(400, "username, password, and class_id are required")
    school_class = db.session.get(SchoolClass, class_id)
    if not school_class or User.query.filter_by(username=username).one_or_none():
        return json_error(400, "class administrator could not be created")
    user = User(username=username, password_hash=hash_password(password), role="class_admin", class_id=school_class.id, is_active=True)
    db.session.add(user)
    db.session.flush()
    db.session.add(ClassAdminGrant(admin_user_id=user.id, class_id=school_class.id, created_by=g.current_user.id))
    db.session.commit()
    return jsonify(admin={"id": user.id, "username": user.username, "is_active": user.is_active, "class_ids": [school_class.id]}), 201


@admin_bp.put("/admin/class-admins/<int:user_id>/active")
@require_auth
@require_csrf
def set_class_admin_active(user_id: int):
    if not is_super_admin(g.current_user):
        return json_error(403, "super administrator role required")
    admin = User.query.filter_by(id=user_id, role="class_admin").one_or_none()
    active = (request.get_json(silent=True) or {}).get("is_active")
    if not admin or not isinstance(active, bool):
        return json_error(404 if not admin else 400, "class administrator not found" if not admin else "is_active must be boolean")
    admin.is_active = active
    db.session.commit()
    return jsonify(admin={"id": admin.id, "username": admin.username, "is_active": admin.is_active})


@admin_bp.put("/admin/class-admins/<int:user_id>/classes/<int:class_id>")
@require_auth
@require_csrf
def grant_class_admin(user_id: int, class_id: int):
    if not is_super_admin(g.current_user):
        return json_error(403, "super administrator role required")
    admin = User.query.filter_by(id=user_id, role="class_admin").one_or_none()
    school_class = db.session.get(SchoolClass, class_id)
    if not admin or not school_class:
        return json_error(404, "class administrator grant not found")
    if not ClassAdminGrant.query.filter_by(admin_user_id=admin.id, class_id=class_id).one_or_none():
        db.session.add(ClassAdminGrant(admin_user_id=admin.id, class_id=class_id, created_by=g.current_user.id))
        db.session.commit()
    return "", 204


@admin_bp.delete("/admin/class-admins/<int:user_id>/classes/<int:class_id>")
@require_auth
@require_csrf
def revoke_class_admin(user_id: int, class_id: int):
    if not is_super_admin(g.current_user):
        return json_error(403, "super administrator role required")
    grant = ClassAdminGrant.query.filter_by(admin_user_id=user_id, class_id=class_id).one_or_none()
    if not grant:
        return json_error(404, "class administrator grant not found")
    db.session.delete(grant)
    db.session.commit()
    return "", 204


@admin_bp.get("/classes/<int:class_id>/subjects")
@require_auth
def list_subjects(class_id: int):
    user = g.current_user
    if _class_admin_scope(class_id):
        subjects = ClassSubject.query.filter_by(class_id=class_id).order_by(ClassSubject.name).all()
    else:
        scope = subject_scope(user)
        if not scope:
            return json_error(403, "class access denied")
        subjects = ClassSubject.query.filter(ClassSubject.class_id == scope.class_id, ClassSubject.id.in_(scope.subject_ids)).order_by(ClassSubject.name).all()
    return jsonify(items=[_subject_payload(subject) for subject in subjects])


@admin_bp.post("/classes/<int:class_id>/subjects")
@require_auth
@require_csrf
def create_subject(class_id: int):
    if not _class_admin_scope(class_id):
        return json_error(403, "class administrator role required")
    payload = request.get_json(silent=True) or {}
    name = " ".join((payload.get("name") or "").strip().split())
    normalized = _normal_name(name)
    key = _normal_name(payload.get("key") or "").replace(" ", "-") or uuid4().hex
    if not name or len(name) > 128 or len(key) > 64:
        return json_error(400, "valid subject name is required")
    if ClassSubject.query.filter_by(class_id=class_id, normalized_name=normalized).one_or_none() or ClassSubject.query.filter_by(class_id=class_id, subject_key=key).one_or_none():
        return json_error(409, "subject already exists")
    subject = ClassSubject(class_id=class_id, subject_key=key, name=name, normalized_name=normalized, created_by=g.current_user.id)
    db.session.add(subject)
    db.session.commit()
    return jsonify(subject=_subject_payload(subject)), 201


@admin_bp.get("/classes/<int:class_id>/teachers")
@require_auth
def list_class_teachers(class_id: int):
    if not _class_admin_scope(class_id):
        return json_error(403, "class administrator role required")
    rows = (
        db.session.query(User)
        .join(ClassMembership, ClassMembership.user_id == User.id)
        .filter(User.role == "teacher", User.is_active.is_(True), ClassMembership.class_id == class_id, ClassMembership.is_teacher.is_(True))
        .order_by(User.username)
        .all()
    )
    return jsonify(items=[{"id": teacher.id, "username": teacher.username} for teacher in rows])


@admin_bp.put("/classes/<int:class_id>/subjects/<int:subject_id>")
@require_auth
@require_csrf
def update_subject(class_id: int, subject_id: int):
    if not _class_admin_scope(class_id):
        return json_error(403, "class administrator role required")
    subject = ClassSubject.query.filter_by(id=subject_id, class_id=class_id).one_or_none()
    if not subject:
        return json_error(404, "subject not found")
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        name = " ".join((payload.get("name") or "").strip().split())
        normalized = _normal_name(name)
        conflict = ClassSubject.query.filter(ClassSubject.class_id == class_id, ClassSubject.normalized_name == normalized, ClassSubject.id != subject.id).one_or_none()
        if not name or conflict:
            return json_error(409 if conflict else 400, "subject name is invalid or already exists")
        subject.name, subject.normalized_name = name, normalized
    if "status" in payload:
        if payload["status"] not in {"active", "archived"}:
            return json_error(400, "unsupported subject status")
        subject.status = payload["status"]
        subject.archived_at = utc_now() if subject.status == "archived" else None
    db.session.commit()
    return jsonify(subject=_subject_payload(subject))


@admin_bp.delete("/classes/<int:class_id>/subjects/<int:subject_id>")
@require_auth
@require_csrf
def delete_subject(class_id: int, subject_id: int):
    if not _class_admin_scope(class_id):
        return json_error(403, "class administrator role required")
    subject = ClassSubject.query.filter_by(id=subject_id, class_id=class_id).one_or_none()
    if not subject:
        return json_error(404, "subject not found")
    if Material.query.filter_by(subject_id=subject.id).first():
        return json_error(409, "subject contains materials and must be archived or reassigned")
    TeacherSubjectAssignment.query.filter_by(subject_id=subject.id).delete(synchronize_session=False)
    db.session.delete(subject)
    db.session.commit()
    return "", 204


@admin_bp.post("/classes/<int:class_id>/subjects/<int:subject_id>/teachers")
@require_auth
@require_csrf
def assign_teacher(class_id: int, subject_id: int):
    if not _class_admin_scope(class_id):
        return json_error(403, "class administrator role required")
    subject = ClassSubject.query.filter_by(id=subject_id, class_id=class_id, status="active").one_or_none()
    teacher_id = (request.get_json(silent=True) or {}).get("teacher_id")
    teacher = db.session.get(User, teacher_id) if isinstance(teacher_id, int) else None
    membership = ClassMembership.query.filter_by(user_id=teacher_id, class_id=class_id, is_teacher=True).one_or_none() if teacher else None
    if not subject or not teacher or teacher.role != "teacher" or not membership:
        return json_error(404, "teacher or subject not found")
    assignment = TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id, subject_id=subject.id).one_or_none()
    if assignment and assignment.is_active:
        return json_error(409, "teacher is already assigned")
    if assignment:
        assignment.is_active, assignment.revoked_at, assignment.granted_by = True, None, g.current_user.id
    else:
        db.session.add(TeacherSubjectAssignment(teacher_id=teacher.id, subject_id=subject.id, granted_by=g.current_user.id))
    db.session.commit()
    return "", 204


@admin_bp.get("/classes/<int:class_id>/subjects/<int:subject_id>/teachers")
@require_auth
def list_assigned_teachers(class_id: int, subject_id: int):
    if not _class_admin_scope(class_id):
        return json_error(403, "class administrator role required")
    subject = ClassSubject.query.filter_by(id=subject_id, class_id=class_id).one_or_none()
    if not subject:
        return json_error(404, "subject not found")
    rows = (
        db.session.query(User)
        .join(TeacherSubjectAssignment, TeacherSubjectAssignment.teacher_id == User.id)
        .filter(TeacherSubjectAssignment.subject_id == subject.id, TeacherSubjectAssignment.is_active.is_(True))
        .order_by(User.username)
        .all()
    )
    return jsonify(items=[{"id": teacher.id, "username": teacher.username} for teacher in rows])


@admin_bp.delete("/classes/<int:class_id>/subjects/<int:subject_id>/teachers/<int:teacher_id>")
@require_auth
@require_csrf
def revoke_teacher(class_id: int, subject_id: int, teacher_id: int):
    if not _class_admin_scope(class_id):
        return json_error(403, "class administrator role required")
    subject = ClassSubject.query.filter_by(id=subject_id, class_id=class_id).one_or_none()
    assignment = TeacherSubjectAssignment.query.filter_by(teacher_id=teacher_id, subject_id=subject_id, is_active=True).one_or_none()
    if not subject or not assignment:
        return json_error(404, "teacher assignment not found")
    assignment.is_active, assignment.revoked_at = False, utc_now()
    db.session.commit()
    return "", 204


@admin_bp.post("/classes/<int:class_id>/subjects/<int:subject_id>/reassign")
@require_auth
@require_csrf
def reassign_subject_materials(class_id: int, subject_id: int):
    if not _class_admin_scope(class_id):
        return json_error(403, "class administrator role required")
    source = ClassSubject.query.filter_by(id=subject_id, class_id=class_id).one_or_none()
    target_id = (request.get_json(silent=True) or {}).get("target_subject_id")
    target = ClassSubject.query.filter_by(id=target_id, class_id=class_id).one_or_none() if isinstance(target_id, int) else None
    if not source or not target or source.id == target.id:
        return json_error(400, "valid target subject is required")
    materials = Material.query.filter_by(class_id=class_id, subject_id=source.id).all()
    for material in materials:
        material.subject_id = target.id
        entry = KnowledgeEntry.query.filter_by(material_id=material.id).one_or_none()
        if entry:
            entry.subject_id = target.id
            KnowledgeChunk.query.filter_by(knowledge_entry_id=entry.id).update({KnowledgeChunk.subject_id: target.id}, synchronize_session=False)
    db.session.commit()
    return jsonify(reassigned=len(materials), subject=_subject_payload(target))
