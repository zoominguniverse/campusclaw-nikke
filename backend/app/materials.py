from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.utils import secure_filename

from .auth import json_error, require_auth, require_csrf
from .database import db
from .models import ClassMembership, KnowledgeEntry, Material
from .repositories import find_material_in_class, find_membership, query_materials_for_class

materials_bp = Blueprint("materials", __name__, url_prefix="/api/classes")
ALLOWED_EXTENSIONS = {".txt": "text/plain", ".md": "text/markdown"}


def _assert_class_scope(class_id: int, *, teacher_required: bool = False):
    user = g.current_user
    membership = find_membership(user.id, class_id)
    if not membership:
        return json_error(403, "class access denied")
    if teacher_required and (user.role != "teacher" or not membership.is_teacher):
        return json_error(403, "teacher role required")
    return None


def _material_payload(material: Material) -> dict:
    return {
        "id": material.id,
        "title": material.title,
        "original_filename": material.original_filename,
        "created_at": material.created_at.isoformat(),
    }


@materials_bp.get("/<int:class_id>/materials")
@require_auth
def list_materials(class_id: int):
    denied = _assert_class_scope(class_id)
    if denied:
        return denied
    page = max(request.args.get("page", 1, type=int), 1)
    limit = min(max(request.args.get("limit", 20, type=int), 1), 100)
    search = (request.args.get("search") or "").strip()
    pagination = query_materials_for_class(class_id, search, page, limit)
    return jsonify(
        items=[_material_payload(material) for material in pagination.items],
        page=page,
        total=pagination.total,
    )


@materials_bp.get("/<int:class_id>/materials/<string:material_id>")
@require_auth
def get_material(class_id: int, material_id: str):
    denied = _assert_class_scope(class_id)
    if denied:
        return denied
    material = find_material_in_class(material_id, class_id)
    if not material:
        other = db.session.get(Material, material_id)
        if other and other.class_id != class_id:
            return json_error(403, "class access denied")
        return json_error(404, "material not found")
    entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=class_id).one_or_none()
    return jsonify(material=_material_payload(material), body_text=entry.body_text if entry else "")


@materials_bp.post("/<int:class_id>/materials")
@require_auth
@require_csrf
def upload_material(class_id: int):
    denied = _assert_class_scope(class_id, teacher_required=True)
    if denied:
        return denied
    file = request.files.get("file")
    if not file or not file.filename:
        return json_error(400, "a material file is required")
    safe_name = secure_filename(file.filename)
    suffix = Path(safe_name).suffix.lower()
    if not safe_name or suffix not in ALLOWED_EXTENSIONS:
        return json_error(400, "only .txt and .md files are supported")

    upload_root = Path(current_app.config["UPLOAD_DIR"])
    temp_dir = upload_root / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = None
    final_path = None
    committed = False
    try:
        with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as temporary:
            temp_path = Path(temporary.name)
            total = 0
            while chunk := file.stream.read(64 * 1024):
                total += len(chunk)
                if total > current_app.config["MAX_CONTENT_LENGTH"]:
                    raise ValueError("file exceeds the configured size limit")
                temporary.write(chunk)
        body_text = temp_path.read_text(encoding="utf-8")
        if not body_text.strip():
            raise ValueError("file must not be empty")

        title = (request.form.get("title") or Path(safe_name).stem).strip()[:255]
        if not title:
            raise ValueError("material title is required")
        class_dir = upload_root / str(class_id)
        class_dir.mkdir(parents=True, exist_ok=True)
        final_path = class_dir / f"{uuid4()}{suffix}"
        material = Material(
            class_id=class_id,
            uploader_id=g.current_user.id,
            title=title,
            original_filename=safe_name,
            storage_path=str(final_path.relative_to(upload_root)),
            content_type=ALLOWED_EXTENSIONS[suffix],
        )
        db.session.add(material)
        db.session.flush()
        db.session.add(KnowledgeEntry(material_id=material.id, class_id=class_id, body_text=body_text))
        shutil.move(str(temp_path), str(final_path))
        db.session.commit()
        committed = True
        return jsonify(material=_material_payload(material)), 201
    except ValueError as error:
        db.session.rollback()
        return json_error(400, str(error))
    except UnicodeDecodeError:
        db.session.rollback()
        return json_error(400, "material must be valid UTF-8 text")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("material upload failed")
        return json_error(500, "material upload failed")
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        if final_path and final_path.exists() and not committed:
            final_path.unlink(missing_ok=True)


@materials_bp.put("/<int:class_id>/materials/<string:material_id>")
@require_auth
@require_csrf
def rename_material(class_id: int, material_id: str):
    denied = _assert_class_scope(class_id, teacher_required=True)
    if denied:
        return denied
    material = find_material_in_class(material_id, class_id)
    if not material:
        if db.session.get(Material, material_id):
            return json_error(403, "class access denied")
        return json_error(404, "material not found")
    title = ((request.get_json(silent=True) or {}).get("title") or "").strip()[:255]
    if not title:
        return json_error(400, "material title is required")
    material.title = title
    db.session.commit()
    return jsonify(material=_material_payload(material))


@materials_bp.delete("/<int:class_id>/materials/<string:material_id>")
@require_auth
@require_csrf
def delete_material(class_id: int, material_id: str):
    denied = _assert_class_scope(class_id, teacher_required=True)
    if denied:
        return denied
    material = find_material_in_class(material_id, class_id)
    if not material:
        if db.session.get(Material, material_id):
            return json_error(403, "class access denied")
        return json_error(404, "material not found")
    file_path = Path(current_app.config["UPLOAD_DIR"]) / material.storage_path
    is_seeded = material.storage_path == "seeded"
    KnowledgeEntry.query.filter_by(material_id=material.id, class_id=class_id).delete()
    db.session.delete(material)
    db.session.commit()
    if file_path.exists() and not is_seeded:
        file_path.unlink(missing_ok=True)
    return "", 204
