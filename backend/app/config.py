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
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _as_bool(os.getenv("SESSION_COOKIE_SECURE"))
    SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "8"))
    LOGIN_FAILURE_LIMIT = int(os.getenv("LOGIN_FAILURE_LIMIT", "5"))
    LOGIN_FAILURE_WINDOW_SECONDS = int(os.getenv("LOGIN_FAILURE_WINDOW_SECONDS", "60"))
    SEED_DEMO_DATA = _as_bool(os.getenv("SEED_DEMO_DATA"))
    INITIALIZE_DATABASE = _as_bool(os.getenv("INITIALIZE_DATABASE", "true"))
    DEMO_TEACHER_PASSWORD = os.getenv("DEMO_TEACHER_PASSWORD", "")
    DEMO_TEACHER_B_PASSWORD = os.getenv("DEMO_TEACHER_B_PASSWORD", "")
    DEMO_STUDENT_A_PASSWORD = os.getenv("DEMO_STUDENT_A_PASSWORD", "")
    DEMO_STUDENT_A2_PASSWORD = os.getenv("DEMO_STUDENT_A2_PASSWORD", "")
    DEMO_STUDENT_B_PASSWORD = os.getenv("DEMO_STUDENT_B_PASSWORD", "")
    DEMO_STUDENT_B2_PASSWORD = os.getenv("DEMO_STUDENT_B2_PASSWORD", "")
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
