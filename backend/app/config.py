from __future__ import annotations

import os
from pathlib import Path


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured as a server environment variable")
    return value


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = _required("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _required("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(Path.cwd() / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_BYTES", "5242880"))
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    AUTH_TOKEN_SECRET = _required("AUTH_TOKEN_SECRET")
    AUTH_ACCESS_TTL_SECONDS = int(os.getenv("AUTH_ACCESS_TTL_SECONDS", "900"))
    AUTH_REFRESH_TTL_SECONDS = int(os.getenv("AUTH_REFRESH_TTL_SECONDS", "28800"))
    TRUSTED_ORIGINS = tuple(item.strip().rstrip("/") for item in os.getenv("TRUSTED_ORIGINS", os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")).split(",") if item.strip())
    LOGIN_FAILURE_LIMIT = int(os.getenv("LOGIN_FAILURE_LIMIT", "5"))
    LOGIN_FAILURE_WINDOW_SECONDS = int(os.getenv("LOGIN_FAILURE_WINDOW_SECONDS", "60"))
    SEED_DEMO_DATA = _as_bool(os.getenv("SEED_DEMO_DATA"))
    INITIALIZE_DATABASE = _as_bool(os.getenv("INITIALIZE_DATABASE", "true"))
    # A JSON object mapping every fixed local demo username to its password.
    # It is deliberately kept in the ignored runtime .env, never source code.
    DEMO_ACCOUNT_PASSWORDS = os.getenv("DEMO_ACCOUNT_PASSWORDS", "")
    PURGE_LEGACY_DEMO_DATA = _as_bool(os.getenv("PURGE_LEGACY_DEMO_DATA"))
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "deterministic")
    EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "").rstrip("/")
    EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "campusclaw-deterministic")
    EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "64"))
    CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "deterministic")
    CHAT_API_URL = os.getenv("CHAT_API_URL", "").rstrip("/")
    CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")
    CHAT_MODEL = os.getenv("CHAT_MODEL", "campusclaw-deterministic")
    RETRIEVAL_MAX_HITS = int(os.getenv("RETRIEVAL_MAX_HITS", "10"))
    ANSWER_HISTORY_LIMIT = int(os.getenv("ANSWER_HISTORY_LIMIT", "6"))


def validate_auth_config(config) -> None:
    if not config["AUTH_TOKEN_SECRET"] or config["AUTH_TOKEN_SECRET"] == config["SECRET_KEY"]:
        raise RuntimeError("AUTH_TOKEN_SECRET must be configured and distinct from SECRET_KEY")
    if config["AUTH_ACCESS_TTL_SECONDS"] <= 0 or config["AUTH_REFRESH_TTL_SECONDS"] <= config["AUTH_ACCESS_TTL_SECONDS"]:
        raise RuntimeError("AUTH_REFRESH_TTL_SECONDS must be greater than AUTH_ACCESS_TTL_SECONDS and both must be positive")
    if not config["TRUSTED_ORIGINS"] or "*" in config["TRUSTED_ORIGINS"]:
        raise RuntimeError("TRUSTED_ORIGINS must contain exact origins, never '*'")
    if config["APP_ENV"] == "production" and any(not origin.startswith("https://") for origin in config["TRUSTED_ORIGINS"]):
        raise RuntimeError("production TRUSTED_ORIGINS must use HTTPS")
