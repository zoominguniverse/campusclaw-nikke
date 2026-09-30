from __future__ import annotations

import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request, send_file

from .auth import json_error, require_auth
from .database import db
from .indexing import IndexingFailed, index_entry, reindex_entry
from .authorization import subject_in_class, subject_is_allowed, subject_scope
from .models import ClassMembership, ClassSubject, KnowledgeChunk, KnowledgeEntry, KnowledgeIndexGeneration, Material
from .repositories import find_membership

materials_bp = Blueprint("materials", __name__, url_prefix="/api/classes")
ALLOWED_EXTENSIONS = {".txt": "text/plain", ".md": "text/markdown"}
SUPPORTED_TEXT_ENCODINGS = ("utf-8-sig", "gb18030", "gbk")


def _effective_class_id() -> int:
    return g.current_user.class_id


def _material_scope():
    return subject_scope(g.current_user)


def _validated_upload_name(filename: str) -> tuple[str, str]:
    """Keep a Unicode display name separate from the UUID storage path."""
    display_name = (filename or "").strip()
    if not display_name or len(display_name) > 255 or "\x00" in display_name:
        raise ValueError("material filename is invalid")
    if "/" in display_name or "\\" in display_name:
        raise ValueError("material filename must not contain a path")
    suffix = Path(display_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("only .txt and .md files are supported")
    return display_name, suffix


def _decode_text_upload(raw_bytes: bytes) -> str:
    for encoding in SUPPORTED_TEXT_ENCODINGS:
        try:
            # PostgreSQL TEXT rejects NUL. Keep the original bytes on disk for
            # download, but remove this storage-prohibited padding from the
            # Unicode body used for preview, chunking, and embeddings.
            return raw_bytes.decode(encoding).replace("\x00", "")
        except UnicodeDecodeError:
            continue
    raise ValueError("material text must use UTF-8, GB18030, or GBK encoding")


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
        "subject_id": material.subject_id,
        "subject_name": subject.name if (subject := ClassSubject.query.filter_by(id=material.subject_id, class_id=material.class_id).one_or_none()) else "",
        "original_filename": material.original_filename,
        "created_at": material.created_at.isoformat(),
        "index_status": generation.status if generation else "pending",
    }


def _allowed_material(material_id: str, scope):
    material = Material.query.filter_by(id=material_id, class_id=scope.class_id).one_or_none() if scope else None
    return material if material and subject_is_allowed(scope, material.subject_id) else None


@materials_bp.get("/<int:class_id>/materials")
@require_auth
def list_materials(class_id: int):
    denied = _assert_class_scope()
    if denied:
        return denied
    scope = _material_scope()
    if not scope:
        return json_error(403, "class access denied")
    page = max(request.args.get("page", 1, type=int), 1)
    limit = min(max(request.args.get("limit", 20, type=int), 1), 100)
    search = (request.args.get("search") or "").strip()
    selected_subject = request.args.get("subject_id", type=int)
    if selected_subject is not None and not subject_is_allowed(scope, selected_subject):
        return jsonify(items=[], page=page, total=0)
    query = Material.query.filter(Material.class_id == scope.class_id, Material.subject_id.in_(scope.subject_ids))
    if selected_subject is not None:
        query = query.filter(Material.subject_id == selected_subject)
    if search:
        query = query.filter(Material.title.ilike(f"%{search}%"))
    pagination = query.order_by(Material.created_at.desc(), Material.id.desc()).paginate(page=page, per_page=limit, error_out=False)
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
    scope = _material_scope()
    material = _allowed_material(material_id, scope)
    if not material:
        return json_error(404, "material not found")
    entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=scope.class_id).one_or_none()
    return jsonify(material=_material_payload(material), body_text=entry.body_text if entry else "")


@materials_bp.get("/<int:class_id>/materials/<string:material_id>/download")
@require_auth
def download_material(class_id: int, material_id: str):
    denied = _assert_class_scope()
    if denied:
        return denied
    scope = _material_scope()
    material = _allowed_material(material_id, scope)
    if not material:
        return json_error(404, "material not found")

    if material.storage_path == "seeded":
        entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=scope.class_id).one_or_none()
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
def upload_material(class_id: int):
    denied = _assert_class_scope(teacher_required=True)
    if denied:
        return denied
    scope = _material_scope()
    if not scope or g.current_user.role != "teacher":
        return json_error(403, "teacher subject assignment required")
    class_id = scope.class_id
    file = request.files.get("file")
    if not file or not file.filename:
        return json_error(400, "a material file is required")
    try:
        display_name, suffix = _validated_upload_name(file.filename)
    except ValueError as error:
        return json_error(400, str(error))

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
        body_text = _decode_text_upload(temp_path.read_bytes())
        if not body_text.strip():
            raise ValueError("file must not be empty")

        title = (request.form.get("title") or Path(display_name).stem).strip()[:255]
        if not title:
            raise ValueError("material title is required")
        subject_id = request.form.get("subject_id", type=int)
        subject = subject_in_class(subject_id, class_id)
        if not subject or subject.status != "active" or not subject_is_allowed(scope, subject_id):
            raise ValueError("an assigned active subject is required")
        subject_dir = upload_root / str(class_id) / str(subject.id)
        subject_dir.mkdir(parents=True, exist_ok=True)
        final_path = subject_dir / f"{uuid4()}{suffix}"
        material = Material(
            class_id=class_id,
            subject_id=subject.id,
            uploader_id=g.current_user.id,
            title=title,
            original_filename=display_name,
            storage_path=str(final_path.relative_to(upload_root)),
            content_type=ALLOWED_EXTENSIONS[suffix],
        )
        db.session.add(material)
        db.session.flush()
        entry = KnowledgeEntry(material_id=material.id, class_id=class_id, subject_id=subject.id, body_text=body_text)
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
def reindex_material(class_id: int, material_id: str):
    denied = _assert_class_scope(teacher_required=True)
    if denied:
        return denied
    scope = _material_scope()
    material = _allowed_material(material_id, scope)
    if not material:
        return json_error(404, "material not found")
    entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=scope.class_id).one_or_none()
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
def rename_material(class_id: int, material_id: str):
    denied = _assert_class_scope(teacher_required=True)
    if denied:
        return denied
    scope = _material_scope()
    material = _allowed_material(material_id, scope)
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
def delete_material(class_id: int, material_id: str):
    denied = _assert_class_scope(teacher_required=True)
    if denied:
        return denied
    scope = _material_scope()
    material = _allowed_material(material_id, scope)
    if not material:
        return json_error(404, "material not found")
    upload_root = Path(current_app.config["UPLOAD_DIR"]).resolve()
    file_path = (upload_root / material.storage_path).resolve()
    is_seeded = material.storage_path == "seeded"
    entry = KnowledgeEntry.query.filter_by(material_id=material.id, class_id=scope.class_id).one_or_none()
    if entry:
        generations = KnowledgeIndexGeneration.query.filter_by(knowledge_entry_id=entry.id).all()
        generation_ids = [generation.id for generation in generations]
        if generation_ids:
            KnowledgeChunk.query.filter(KnowledgeChunk.generation_id.in_(generation_ids)).delete(synchronize_session=False)
            KnowledgeIndexGeneration.query.filter(KnowledgeIndexGeneration.id.in_(generation_ids)).delete(synchronize_session=False)
        db.session.delete(entry)
    db.session.delete(material)
    db.session.commit()
    if not is_seeded and file_path.is_relative_to(upload_root) and file_path.exists():
        file_path.unlink(missing_ok=True)
    return "", 204
