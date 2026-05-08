"""
Hearts for Children — Flask REST API
=====================================
Entry point. Initialises extensions, registers blueprints, and starts the
development server.
"""

from flask import Flask
from flask_cors import CORS
from flask_pymongo import PyMongo
from config import Config

mongo = PyMongo()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Restricts cross-origin requests to whitelisted origins only.
    CORS(
        app,
        resources={r"/api/*": {"origins": Config.ALLOWED_ORIGINS}},
        supports_credentials=False,
    )

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongo.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.donations import donations_bp
    from routes.stats import stats_bp

    app.register_blueprint(donations_bp, url_prefix="/api")
    app.register_blueprint(stats_bp, url_prefix="/api")

    # ── Health-check (no auth needed) ─────────────────────────────────────────
    @app.get("/health")
    def health():
        return {"status": "ok", "service": "hearts-for-children-api"}

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True, port=5000)
