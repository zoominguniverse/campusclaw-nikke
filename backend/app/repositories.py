from __future__ import annotations

from .models import ClassMembership, Material, User


def find_user_by_username(username: str) -> User | None:
    return User.query.filter_by(username=username).one_or_none()


def find_membership(user_id: int, class_id: int) -> ClassMembership | None:
    return ClassMembership.query.filter_by(user_id=user_id, class_id=class_id).one_or_none()


def find_material_in_class(material_id: str, class_id: int) -> Material | None:
    return Material.query.filter_by(id=material_id, class_id=class_id).one_or_none()


def query_materials_for_class(class_id: int, search: str, page: int, limit: int):
    query = Material.query.filter_by(class_id=class_id)
    if search:
        query = query.filter(Material.title.ilike(f"%{search}%"))
    return query.order_by(Material.created_at.desc(), Material.id.desc()).paginate(
        page=page, per_page=limit, error_out=False
    )

