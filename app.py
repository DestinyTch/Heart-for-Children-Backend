"""
Hearts for Children — Flask REST API
=====================================
Entry point. Initialises extensions, registers blueprints, and starts the
development server.
"""
import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_pymongo import PyMongo
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

mongo = PyMongo()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    logger.info("🚀 Initializing Hearts for Children API")
    logger.info(f"📍 Debug mode: {Config.DEBUG}")
    logger.info(f"🔐 Allowed origins: {Config.ALLOWED_ORIGINS}")

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Allows cross-origin requests from whitelisted origins.
    # Handles preflight OPTIONS requests automatically.
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": Config.ALLOWED_ORIGINS,
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "X-Admin-Secret"],
                "expose_headers": ["Content-Type"],
                "max_age": 3600,
                "supports_credentials": False,
            }
        },
        send_wildcard=Config.ALLOWED_ORIGINS == ["*"],
    )

    logger.info("✅ CORS configured")

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongo.init_app(app)
    logger.info("✅ MongoDB initialized")

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.donations import donations_bp
    from routes.stats import stats_bp

    app.register_blueprint(donations_bp, url_prefix="/api")
    app.register_blueprint(stats_bp, url_prefix="/api")

    logger.info("✅ Blueprints registered")

    # ── Health-check (no auth needed) ─────────────────────────────────────────
    @app.get("/health")
    def health():
        return {"status": "ok", "service": "hearts-for-children-api"}, 200

    # ── Error handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Endpoint not found"}, 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return {"error": "Method not allowed"}, 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Internal server error")
        return {"error": "Internal server error"}, 500

    logger.info("✅ Hearts for Children API ready!")

    return app


if __name__ == "__main__":
    application = create_app()
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 Starting server on http://0.0.0.0:{port}")
    application.run(host="0.0.0.0", port=port, debug=True)
