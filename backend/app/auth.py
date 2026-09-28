from __future__ import annotations

import secrets
from datetime import timedelta, timezone
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request, session

from .database import db
from .models import LoginSession, User, utc_now
from .repositories import find_user_by_username
from .security import verify_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def json_error(status: int, message: str):
    return jsonify(error=message), status


def _load_identity():
    sid = session.get("sid")
    user_id = session.get("user_id")
    if not sid or not user_id:
        return None
    login_session = db.session.get(LoginSession, sid)
    if not login_session or login_session.user_id != user_id or login_session.revoked_at:
        return None
    expiry = login_session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= utc_now():
        return None
    user = db.session.get(User, user_id)
    if not user:
        return None
    return user


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = _load_identity()
        if not user:
            session.clear()
            return json_error(401, "authentication required")
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def require_csrf(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not token or not expected or not secrets.compare_digest(token, expected):
            return json_error(403, "invalid csrf token")
        return view(*args, **kwargs)

    return wrapped


def serialize_user(user: User) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role, "class_id": user.class_id}


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or request.form
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    user = find_user_by_username(username)
    if not user or not verify_password(password, user.password_hash):
        return json_error(401, "invalid credentials")

    session.clear()
    sid = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    db.session.add(
        LoginSession(
            id=sid,
            user_id=user.id,
            expires_at=utc_now() + timedelta(hours=current_app.config["SESSION_TTL_HOURS"]),
        )
    )
    db.session.commit()
    session.update(
        sid=sid,
        user_id=user.id,
        role=user.role,
        class_id=user.class_id,
        csrf_token=csrf_token,
    )
    return jsonify(username=user.username, role=user.role, class_id=user.class_id), 200


@auth_bp.post("/logout")
@require_auth
@require_csrf
def logout():
    login_session = db.session.get(LoginSession, session["sid"])
    if login_session:
        login_session.revoked_at = utc_now()
        db.session.commit()
    session.clear()
    return "", 204


@auth_bp.get("/me")
@require_auth
def me():
    return jsonify(user=serialize_user(g.current_user), csrf_token=session["csrf_token"])
