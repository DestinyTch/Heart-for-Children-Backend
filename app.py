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
    # FIX: The original code passed send_wildcard as a top-level kwarg
    # alongside a resources dict. In Flask-CORS 4.x these two config paths
    # conflict — send_wildcard was ignored for per-resource entries, so "*"
    # was never actually sent even when ALLOWED_ORIGINS=["*"].
    # All options now live inside the per-resource dict where they are applied.
    # When ALLOWED_ORIGINS is empty (misconfigured .env) we fall back to "*"
    # so the app stays reachable in development.
    origins = Config.ALLOWED_ORIGINS if Config.ALLOWED_ORIGINS else ["*"]

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins":              origins,
                "methods":              ["GET", "POST", "OPTIONS"],
                "allow_headers":        ["Content-Type", "X-Admin-Secret"],
                "expose_headers":       ["Content-Type"],
                "supports_credentials": False,
                "max_age":              3600,
                "send_wildcard":        origins == ["*"],
            }
        },
    )

    logger.info(f"✅ CORS configured — origins: {origins}")

    # ── Guarantee CORS headers on every response (including 4xx / 5xx) ───────
    # Flask-CORS only patches successful responses. When an unhandled exception
    # produces a 500 before the response object is built, the ACAO header is
    # missing and the browser reports a CORS error instead of the real problem.
    # This after_request hook ensures the header is always present.
    @app.after_request
    def _add_cors_headers(response):
        request_origin = None
        try:
            from flask import request as _req
            request_origin = _req.headers.get("Origin", "")
        except Exception:
            pass

        if request_origin:
            if origins == ["*"]:
                response.headers["Access-Control-Allow-Origin"] = "*"
            elif request_origin.rstrip("/") in [o.rstrip("/") for o in origins]:
                response.headers["Access-Control-Allow-Origin"] = request_origin
                response.headers["Vary"] = "Origin"

        response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, X-Admin-Secret")
        return response

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
