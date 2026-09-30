from app.config import validate_auth_config
from datetime import timedelta

from app.database import _upgrade_authorization_only_auth, db
from app.models import AuthToken, LoginSession, SchemaMigration, User, utc_now

from .conftest import LEGACY_TEST_USERNAMES


def _login_pair(client):
    response = client.post(
        "/api/auth/login",
        json={"username": LEGACY_TEST_USERNAMES["teacher_a"], "password": "teacher-password"},
    )
    assert response.status_code == 200
    return response.get_json()


def test_cookie_only_request_is_rejected(client):
    response = client.get("/api/auth/me", headers={"Cookie": "session=legacy-cookie-value"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["Cache-Control"] == "no-store"


def test_malformed_unknown_and_expired_bearer_values_are_generic_401(app, client):
    for value in ("Basic ignored", "Bearer", "Bearer unknown", "Bearer first, Bearer second"):
        response = client.get("/api/auth/me", headers={"Authorization": value})
        assert response.status_code == 401
        assert response.get_json() == {"error": "authentication required"}

    pair = _login_pair(client)
    with app.app_context():
        token = AuthToken.query.filter_by(token_type="access").one()
        token.expires_at = utc_now() - timedelta(seconds=1)
        db.session.commit()
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {pair['access_token']}"}).status_code == 401


def test_tokens_are_hashed_and_refresh_replay_revokes_family(app, client):
    pair = _login_pair(client)
    with app.app_context():
        persisted = AuthToken.query.all()
        assert len(persisted) == 2
        assert all(pair["access_token"] not in row.token_hash for row in persisted)
        assert all(pair["refresh_token"] not in row.token_hash for row in persisted)

    refresh_headers = {"Authorization": f"Bearer {pair['refresh_token']}"}
    refreshed = client.post("/api/auth/token/refresh", headers=refresh_headers)
    assert refreshed.status_code == 200
    replacement = refreshed.get_json()
    assert replacement["access_token"] != pair["access_token"]
    assert "Set-Cookie" not in refreshed.headers

    replay = client.post("/api/auth/token/refresh", headers=refresh_headers)
    assert replay.status_code == 401
    assert replay.headers["WWW-Authenticate"] == "Bearer"
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {replacement['access_token']}"}).status_code == 401


def test_cutover_revokes_legacy_sessions_idempotently(app):
    with app.app_context():
        user = User.query.filter_by(username=LEGACY_TEST_USERNAMES["teacher_a"]).one()
        legacy = LoginSession(id="legacy-cookie-session", user_id=user.id, expires_at=utc_now() + timedelta(hours=1))
        db.session.add(legacy)
        migration = db.session.get(SchemaMigration, "20260930_authorization_only_authentication")
        db.session.delete(migration)
        db.session.commit()

        _upgrade_authorization_only_auth()
        assert db.session.get(LoginSession, legacy.id).revoked_at is not None
        assert db.session.get(SchemaMigration, "20260930_authorization_only_authentication")
        _upgrade_authorization_only_auth()
        assert db.session.get(LoginSession, legacy.id).revoked_at is not None


def test_refresh_rejects_access_token_and_cors_is_exact_origin(client):
    pair = _login_pair(client)
    rejected = client.post("/api/auth/token/refresh", headers={"Authorization": f"Bearer {pair['access_token']}"})
    assert rejected.status_code == 401

    trusted = client.options(
        "/api/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert trusted.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert trusted.headers["Access-Control-Allow-Headers"] == "Authorization, Content-Type"
    assert "Access-Control-Allow-Credentials" not in trusted.headers

    untrusted = client.get("/api/auth/me", headers={"Origin": "https://untrusted.example"})
    assert "Access-Control-Allow-Origin" not in untrusted.headers


def test_deactivated_user_loses_access_immediately(app, client):
    pair = _login_pair(client)
    with app.app_context():
        user = User.query.filter_by(username=LEGACY_TEST_USERNAMES["teacher_a"]).one()
        user.is_active = False
        db.session.commit()
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {pair['access_token']}"})
    assert response.status_code == 401


def test_auth_configuration_rejects_unsafe_values():
    base = {"SECRET_KEY": "server-secret", "AUTH_TOKEN_SECRET": "token-secret", "AUTH_ACCESS_TTL_SECONDS": 900, "AUTH_REFRESH_TTL_SECONDS": 28800, "TRUSTED_ORIGINS": ("https://app.example",), "APP_ENV": "production"}
    validate_auth_config(base)
    for update in (
        {"AUTH_ACCESS_TTL_SECONDS": 0},
        {"AUTH_REFRESH_TTL_SECONDS": 900},
        {"AUTH_TOKEN_SECRET": "server-secret"},
        {"TRUSTED_ORIGINS": ("*",)},
        {"TRUSTED_ORIGINS": ("http://app.example",)},
    ):
        candidate = {**base, **update}
        try:
            validate_auth_config(candidate)
        except RuntimeError:
            continue
        raise AssertionError(f"unsafe configuration was accepted: {update}")
