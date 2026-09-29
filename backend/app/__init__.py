from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify
from sqlalchemy import text

from .auth import auth_bp
from .config import Config
from .database import db, initialize_database
from .materials import materials_bp
from .knowledge import knowledge_bp
from .administration import admin_bp


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config["EMBEDDING_DIMENSIONS"] != 64:
        raise RuntimeError("EMBEDDING_DIMENSIONS must match the PostgreSQL VECTOR(64) schema")

    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"], ".tmp").mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    if app.config["INITIALIZE_DATABASE"]:
        with app.app_context():
            initialize_database()

    app.register_blueprint(auth_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(admin_bp)

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            upload_dir = Path(app.config["UPLOAD_DIR"])
            if not upload_dir.is_dir():
                raise OSError("upload directory is unavailable")
        except Exception:
            db.session.rollback()
            return jsonify(status="unavailable"), 503
        return jsonify(status="ok"), 200

    return app
