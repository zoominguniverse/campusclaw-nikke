from __future__ import annotations

from dataclasses import dataclass

from .models import ClassAdminGrant, ClassMembership, ClassSubject, TeacherSubjectAssignment, User


@dataclass(frozen=True)
class SubjectScope:
    class_id: int
    role: str
    subject_ids: frozenset[int]


def is_super_admin(user: User) -> bool:
    return user.is_active and user.role == "super_admin"


def is_class_admin_for(user: User, class_id: int) -> bool:
    return bool(
        user.is_active
        and user.role == "class_admin"
        and ClassAdminGrant.query.filter_by(admin_user_id=user.id, class_id=class_id).one_or_none()
    )


def is_teacher_member(user: User, class_id: int) -> bool:
    return bool(
        user.is_active
        and user.role == "teacher"
        and ClassMembership.query.filter_by(user_id=user.id, class_id=class_id, is_teacher=True).one_or_none()
    )


def effective_class_id(user: User) -> int:
    """Teachers and students retain the existing one-home-class compatibility rule."""
    return user.class_id


def subject_scope(user: User) -> SubjectScope | None:
    class_id = effective_class_id(user)
    if user.role == "student" and user.is_active:
        ids = {subject.id for subject in ClassSubject.query.filter_by(class_id=class_id).all()}
        return SubjectScope(class_id=class_id, role=user.role, subject_ids=frozenset(ids))
    if is_teacher_member(user, class_id):
        ids = {
            assignment.subject_id
            for assignment in TeacherSubjectAssignment.query.filter_by(teacher_id=user.id, is_active=True).all()
            if (subject := ClassSubject.query.filter_by(id=assignment.subject_id, class_id=class_id, status="active").one_or_none())
        }
        return SubjectScope(class_id=class_id, role=user.role, subject_ids=frozenset(ids))
    return None


def subject_is_allowed(scope: SubjectScope | None, subject_id: int | None) -> bool:
    return bool(scope and subject_id is not None and subject_id in scope.subject_ids)


def subject_in_class(subject_id: int | None, class_id: int) -> ClassSubject | None:
    if subject_id is None:
        return None
    return ClassSubject.query.filter_by(id=subject_id, class_id=class_id).one_or_none()
