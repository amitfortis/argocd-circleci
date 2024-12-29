from flask import Flask
import os


def create_app():
    app = Flask(__name__)

    from board.pages import bp as pages_bp, location_not_found, api_bad_request

    app.register_blueprint(pages_bp)
    app.register_error_handler(400, location_not_found)
    app.register_error_handler(500, api_bad_request)

    app.config["BG_COLOR"] = os.environ.get("BG_COLOR", "#000000")

    from .pages import bp

    app.register_blueprint(bp, name="pages_blueprint")

    return app
