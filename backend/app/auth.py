from __future__ import annotations

import secrets
from hashlib import sha256
import hmac
from datetime import timedelta, timezone
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request, session

from .database import db
from .models import LoginAttempt, LoginSession, User, utc_now
from .repositories import find_user_by_username
from .security import hash_password, verify_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


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
    if not user or not user.is_active:
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


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def _attempt_key(username: str) -> str:
    return hmac.new(
        current_app.config["SECRET_KEY"].encode("utf-8"),
        username.casefold().encode("utf-8"),
        sha256,
    ).hexdigest()


def _is_rate_limited(attempt: LoginAttempt | None, now) -> bool:
    return bool(attempt and attempt.blocked_until and _utc(attempt.blocked_until) > now)


def _record_failed_login(subject_key: str, now) -> None:
    attempt = db.session.get(LoginAttempt, subject_key)
    window = timedelta(seconds=current_app.config["LOGIN_FAILURE_WINDOW_SECONDS"])
    if not attempt:
        attempt = LoginAttempt(subject_key=subject_key, failure_count=0, window_started_at=now)
        db.session.add(attempt)
    elif _utc(attempt.window_started_at) + window <= now:
        attempt.failure_count = 0
        attempt.window_started_at = now
        attempt.blocked_until = None
    attempt.failure_count += 1
    if attempt.failure_count >= current_app.config["LOGIN_FAILURE_LIMIT"]:
        attempt.blocked_until = now + window
    db.session.commit()


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or request.form
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    user = find_user_by_username(username)
    password_valid = verify_password(password, user.password_hash if user and user.is_active else DUMMY_PASSWORD_HASH)
    now = utc_now()
    subject_key = _attempt_key(username)
    attempt = db.session.get(LoginAttempt, subject_key)
    if not user or not user.is_active or not password_valid or _is_rate_limited(attempt, now):
        if not _is_rate_limited(attempt, now):
            _record_failed_login(subject_key, now)
        return json_error(401, "invalid credentials")

    user = User.query.filter_by(id=user.id).with_for_update().one()
    LoginSession.query.filter(
        LoginSession.user_id == user.id,
        LoginSession.revoked_at.is_(None),
    ).update({LoginSession.revoked_at: utc_now()}, synchronize_session=False)
    existing_attempt = db.session.get(LoginAttempt, subject_key)
    if existing_attempt:
        db.session.delete(existing_attempt)
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
