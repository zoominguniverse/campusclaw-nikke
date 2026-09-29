from __future__ import annotations

import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

from .auth import json_error, require_auth, require_csrf
from .database import db
from .indexing import IndexingFailed, index_entry, reindex_entry
from .models import ClassMembership, KnowledgeChunk, KnowledgeEntry, KnowledgeIndexGeneration, Material
from .repositories import find_material_in_class, find_membership, query_materials_for_class

materials_bp = Blueprint("materials", __name__, url_prefix="/api/classes")
ALLOWED_EXTENSIONS = {".txt": "text/plain", ".md": "text/markdown"}


def _effective_class_id() -> int:
    return g.current_user.class_id


def _assert_class_scope(*, teacher_required: bool = False):
    user = g.current_user
    membership = find_membership(user.id, _effective_class_id())
    if not membership:
        return json_error(403, "class access denied")
    if teacher_required and (user.role != "teacher" or not membership.is_teacher):
        return json_error(403, "teacher role required")
    return None


def _material_payload(material: Material) -> dict:
    entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=material.class_id).one_or_none()
    generation = (
        KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id, is_current=True).one_or_none()
        if entry
        else None
    )
    return {
        "id": material.id,
        "title": material.title,
        "original_filename": material.original_filename,
        "created_at": material.created_at.isoformat(),
        "index_status": generation.status if generation else "pending",
    }


@materials_bp.get("/<int:class_id>/materials")
@require_auth
def list_materials(class_id: int):
    denied = _assert_class_scope()
    if denied:
        return denied
    class_id = _effective_class_id()
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
    denied = _assert_class_scope()
    if denied:
        return denied
    class_id = _effective_class_id()
    material = find_material_in_class(material_id, class_id)
    if not material:
        return json_error(404, "material not found")
    entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=class_id).one_or_none()
    return jsonify(material=_material_payload(material), body_text=entry.body_text if entry else "")


@materials_bp.get("/<int:class_id>/materials/<string:material_id>/download")
@require_auth
def download_material(class_id: int, material_id: str):
    denied = _assert_class_scope()
    if denied:
        return denied
    class_id = _effective_class_id()
    material = find_material_in_class(material_id, class_id)
    if not material:
        return json_error(404, "material not found")

    if material.storage_path == "seeded":
        entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=class_id).one_or_none()
        return send_file(
            BytesIO((entry.body_text if entry else "").encode("utf-8")),
            mimetype=material.content_type,
            as_attachment=True,
            download_name=material.original_filename,
        )

    upload_root = Path(current_app.config["UPLOAD_DIR"]).resolve()
    file_path = (upload_root / material.storage_path).resolve()
    try:
        file_path.relative_to(upload_root)
    except ValueError:
        return json_error(404, "material file not found")
    if not file_path.is_file():
        return json_error(404, "material file not found")
    return send_file(
        file_path,
        mimetype=material.content_type,
        as_attachment=True,
        download_name=material.original_filename,
    )


@materials_bp.post("/<int:class_id>/materials")
@require_auth
@require_csrf
def upload_material(class_id: int):
    denied = _assert_class_scope(teacher_required=True)
    if denied:
        return denied
    class_id = _effective_class_id()
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
        entry = KnowledgeEntry(material_id=material.id, class_id=class_id, body_text=body_text)
        db.session.add(entry)
        db.session.flush()
        options = _chunking_options_from_form()
        index_result = index_entry(entry, options)
        shutil.move(str(temp_path), str(final_path))
        db.session.commit()
        committed = True
        return jsonify(material=_material_payload(material), indexing=index_result), 201
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


def _chunking_options_from_form() -> dict:
    strategy = request.form.get("strategy") or "auto"
    if strategy != "custom":
        return {"strategy": strategy}
    options: dict = {"strategy": "custom"}
    if request.form.get("max_length"):
        options["max_length"] = request.form.get("max_length", type=int)
    if request.form.get("overlap_percent"):
        options["overlap_percent"] = request.form.get("overlap_percent", type=float)
    return options


@materials_bp.post("/<int:class_id>/materials/<string:material_id>/reindex")
@require_auth
@require_csrf
def reindex_material(class_id: int, material_id: str):
    denied = _assert_class_scope(teacher_required=True)
    if denied:
        return denied
    class_id = _effective_class_id()
    material = find_material_in_class(material_id, class_id)
    if not material:
        return json_error(404, "material not found")
    entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=class_id).one_or_none()
    if not entry:
        return json_error(404, "material not found")
    payload = request.get_json(silent=True) or {}
    try:
        result = reindex_entry(entry, payload.get("chunking"))
        db.session.commit()
        return jsonify(material=_material_payload(material), indexing=result)
    except ValueError as error:
        db.session.rollback()
        return json_error(400, str(error))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("material reindex failed")
        return json_error(500, "material reindex failed")


@materials_bp.put("/<int:class_id>/materials/<string:material_id>")
@require_auth
@require_csrf
def rename_material(class_id: int, material_id: str):
    denied = _assert_class_scope(teacher_required=True)
    if denied:
        return denied
    class_id = _effective_class_id()
    material = find_material_in_class(material_id, class_id)
    if not material:
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
    denied = _assert_class_scope(teacher_required=True)
    if denied:
        return denied
    class_id = _effective_class_id()
    material = find_material_in_class(material_id, class_id)
    if not material:
        return json_error(404, "material not found")
    file_path = Path(current_app.config["UPLOAD_DIR"]) / material.storage_path
    is_seeded = material.storage_path == "seeded"
    entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=class_id).one_or_none()
    if entry:
        generations = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id).all()
        generation_ids = [generation.id for generation in generations]
        if generation_ids:
            KnowledgeChunk.query.filter(KnowledgeChunk.generation_id.in_(generation_ids)).delete(synchronize_session=False)
            KnowledgeIndexGeneration.query.filter(KnowledgeIndexGeneration.id.in_(generation_ids)).delete(synchronize_session=False)
        db.session.delete(entry)
    db.session.delete(material)
    db.session.commit()
    if file_path.exists() and not is_seeded:
        file_path.unlink(missing_ok=True)
    return "", 204
