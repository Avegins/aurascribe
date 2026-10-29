"""AuraScribe Flask application factory and entry point."""

import os
from pathlib import Path
from flask import Flask, jsonify
from aurascribe.api.routes import api_bp
from aurascribe.utils.config import Settings, get_settings
from aurascribe.utils.errors import AuraScribeError
from aurascribe.utils.logger import configure_logging, get_logger

logger = get_logger("main")


def create_app(settings: Settings | None = None) -> Flask:
    """Factory creating and configuring the Flask application instance."""
    cfg = settings or get_settings()

    # Configure centralized application logging
    configure_logging(log_level=cfg.log_level)
    logger.info("Initializing AuraScribe application in %s environment", cfg.aurascribe_env)

    # Determine templates and static directories relative to project root
    base_dir = Path(__file__).resolve().parent.parent.parent
    templates_dir = base_dir / "templates"
    static_dir = base_dir / "static"

    app = Flask(
        __name__,
        template_folder=str(templates_dir),
        static_folder=str(static_dir),
    )

    # Attach settings to app config
    app.config["AURASCRIBE_SETTINGS"] = cfg
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_audio_size_bytes

    # Register API blueprint
    app.register_blueprint(api_bp)

    # Standard error handlers
    @app.errorhandler(413)
    def request_entity_too_large(e):
        return (
            jsonify(
                {
                    "error": {
                        "category": "audio_validation_error",
                        "message": f"Upload payload exceeds maximum allowable size of {cfg.max_audio_size_bytes} bytes.",
                        "details": {},
                    }
                }
            ),
            413,
        )

    @app.errorhandler(404)
    def not_found_error(e):
        return (
            jsonify(
                {
                    "error": {
                        "category": "not_found",
                        "message": "The requested resource was not found.",
                        "details": {},
                    }
                }
            ),
            404,
        )

    @app.errorhandler(405)
    def method_not_allowed_error(e):
        return (
            jsonify(
                {
                    "error": {
                        "category": "method_not_allowed",
                        "message": "HTTP method not allowed for this endpoint.",
                        "details": {},
                    }
                }
            ),
            405,
        )

    @app.errorhandler(AuraScribeError)
    def handle_domain_error(e: AuraScribeError):
        return jsonify(e.to_dict()), e.status_code

    @app.errorhandler(Exception)
    def handle_generic_exception(e: Exception):
        logger.error("Unhandled top-level application exception: %s", str(e), exc_info=True)
        return (
            jsonify(
                {
                    "error": {
                        "category": "internal_error",
                        "message": "An internal server error occurred.",
                        "details": {},
                    }
                }
            ),
            500,
        )

    return app


# WSGI application instance for Gunicorn
app = create_app()

if __name__ == "__main__":
    current_settings = get_settings()
    app.run(
        host=current_settings.host,
        port=current_settings.port,
        debug=(current_settings.aurascribe_env == "development"),
    )

