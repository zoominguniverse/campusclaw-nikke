from __future__ import annotations

import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta, timezone
from functools import wraps
from hashlib import sha256
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request

from .database import db
from .models import AuthToken, LoginAttempt, LoginSession, User, utc_now
from .repositories import find_user_by_username
from .security import hash_password, verify_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthContext:
    user: User
    session_id: str
    token_id: str


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def json_error(status: int, message: str, *, bearer: bool = False):
    response = jsonify(error=message)
    response.status_code = status
    if bearer:
        response.headers["WWW-Authenticate"] = "Bearer"
    return _no_store(response) if status in {401, 429} else response


def _token_hash(value: str) -> str:
    return hmac.new(current_app.config["AUTH_TOKEN_SECRET"].encode("utf-8"), value.encode("utf-8"), sha256).hexdigest()


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def _is_live(record: AuthToken | LoginSession | None) -> bool:
    return bool(record and not record.revoked_at and _utc(record.expires_at) > utc_now())


def _authorization_value() -> str | None:
    values = request.headers.getlist("Authorization")
    if len(values) != 1:
        return None
    scheme, separator, value = values[0].partition(" ")
    return value if scheme.lower() == "bearer" and separator and value and value.strip() == value else None


def _find_token(expected_type: str, *, lock: bool = False) -> AuthToken | None:
    raw = _authorization_value()
    if not raw:
        return None
    query = AuthToken.query.filter_by(token_hash=_token_hash(raw), token_type=expected_type)
    if lock:
        query = query.with_for_update()
    token = query.one_or_none()
    return token if token and hmac.compare_digest(token.token_hash, _token_hash(raw)) and _is_live(token) else None


def _load_access_context() -> AuthContext | None:
    token = _find_token("access")
    if not token:
        return None
    family = db.session.get(LoginSession, token.session_id)
    user = db.session.get(User, family.user_id) if _is_live(family) else None
    return AuthContext(user=user, session_id=family.id, token_id=token.id) if user and user.is_active else None


def _audit(event: str, *, user_id: int | None = None, session_id: str | None = None) -> None:
    logger.info("auth_event=%s user_id=%s session_id=%s", event, user_id, session_id)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        context = _load_access_context()
        if not context:
            _audit("rejected")
            return json_error(401, "authentication required", bearer=True)
        g.current_user, g.auth_context = context.user, context
        return view(*args, **kwargs)

    return wrapped


def serialize_user(user: User) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role, "class_id": user.class_id}


def _attempt_key(username: str) -> str:
    return hmac.new(current_app.config["SECRET_KEY"].encode("utf-8"), username.casefold().encode("utf-8"), sha256).hexdigest()


def _is_rate_limited(attempt: LoginAttempt | None, now) -> bool:
    return bool(attempt and attempt.blocked_until and _utc(attempt.blocked_until) > now)


def _record_failed_login(key: str, now) -> None:
    attempt = db.session.get(LoginAttempt, key)
    window = timedelta(seconds=current_app.config["LOGIN_FAILURE_WINDOW_SECONDS"])
    if not attempt:
        attempt = LoginAttempt(subject_key=key, failure_count=0, window_started_at=now)
        db.session.add(attempt)
    elif _utc(attempt.window_started_at) + window <= now:
        attempt.failure_count, attempt.window_started_at, attempt.blocked_until = 0, now, None
    attempt.failure_count += 1
    if attempt.failure_count >= current_app.config["LOGIN_FAILURE_LIMIT"]:
        attempt.blocked_until = now + window
    db.session.commit()


def _revoke_family(session_id: str) -> None:
    family = db.session.get(LoginSession, session_id)
    if family:
        family.revoked_at = utc_now()
    AuthToken.query.filter_by(session_id=session_id, revoked_at=None).update({AuthToken.revoked_at: utc_now()}, synchronize_session=False)


def _pair(user: User, family: LoginSession) -> tuple[dict, list[AuthToken]]:
    access, refresh = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    access_row = AuthToken(id=str(uuid4()), session_id=family.id, token_hash=_token_hash(access), token_type="access", expires_at=utc_now() + timedelta(seconds=current_app.config["AUTH_ACCESS_TTL_SECONDS"]))
    refresh_row = AuthToken(id=str(uuid4()), session_id=family.id, token_hash=_token_hash(refresh), token_type="refresh", expires_at=family.expires_at)
    return ({"user": serialize_user(user), "token_type": "Bearer", "access_token": access, "expires_in": current_app.config["AUTH_ACCESS_TTL_SECONDS"], "refresh_token": refresh, "refresh_expires_in": current_app.config["AUTH_REFRESH_TTL_SECONDS"]}, [access_row, refresh_row])


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or request.form
    username, password = (payload.get("username") or "").strip(), payload.get("password") or ""
    user = find_user_by_username(username)
    valid = verify_password(password, user.password_hash if user and user.is_active else DUMMY_PASSWORD_HASH)
    now, key = utc_now(), _attempt_key(username)
    attempt = db.session.get(LoginAttempt, key)
    if not user or not user.is_active or not valid or _is_rate_limited(attempt, now):
        if not _is_rate_limited(attempt, now):
            _record_failed_login(key, now)
        return json_error(401, "invalid credentials", bearer=True)
    user = User.query.filter_by(id=user.id).with_for_update().one()
    for family in LoginSession.query.filter_by(user_id=user.id, revoked_at=None).all():
        _revoke_family(family.id)
    if attempt:
        db.session.delete(attempt)
    family = LoginSession(id=secrets.token_urlsafe(32), user_id=user.id, expires_at=utc_now() + timedelta(seconds=current_app.config["AUTH_REFRESH_TTL_SECONDS"]))
    db.session.add(family)
    # Persist the parent explicitly: AuthToken exposes the foreign-key scalar
    # rather than an ORM relationship, so PostgreSQL cannot infer insert order.
    db.session.flush()
    payload, rows = _pair(user, family)
    db.session.add_all(rows)
    db.session.commit()
    _audit("issued", user_id=user.id, session_id=family.id)
    return _no_store(jsonify(payload))


@auth_bp.post("/token/refresh")
def refresh():
    raw = _authorization_value()
    if not raw:
        return json_error(401, "authentication required", bearer=True)
    token = AuthToken.query.filter_by(token_hash=_token_hash(raw), token_type="refresh").with_for_update().one_or_none()
    family = db.session.get(LoginSession, token.session_id) if token else None
    if not token or not hmac.compare_digest(token.token_hash, _token_hash(raw)) or not _is_live(token) or not _is_live(family):
        if token:
            _revoke_family(token.session_id)
            db.session.commit()
        return json_error(401, "authentication required", bearer=True)
    user = db.session.get(User, family.user_id)
    if not user or not user.is_active:
        _revoke_family(family.id)
        db.session.commit()
        return json_error(401, "authentication required", bearer=True)
    token.revoked_at = utc_now()
    payload, rows = _pair(user, family)
    token.replaced_by_id = rows[1].id
    db.session.add_all(rows)
    db.session.commit()
    _audit("refreshed", user_id=user.id, session_id=family.id)
    return _no_store(jsonify(payload))


@auth_bp.post("/logout")
@require_auth
def logout():
    _revoke_family(g.auth_context.session_id)
    db.session.commit()
    _audit("logout", user_id=g.current_user.id, session_id=g.auth_context.session_id)
    return _no_store(current_app.response_class(status=204))


@auth_bp.get("/me")
@require_auth
def me():
    return _no_store(jsonify(user=serialize_user(g.current_user)))
