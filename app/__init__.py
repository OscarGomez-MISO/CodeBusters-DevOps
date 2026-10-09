import os

import click
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_jwt_extended import create_access_token
from flask_restful import Api
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .extensions import db, jwt, ma


class JsonApi(Api):
    def error_router(self, original_handler, error):
        # Keep Flask error handlers, including JWT callbacks, for RESTful routes.
        return original_handler(error)


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", ""),
        JWT_ACCESS_TOKEN_EXPIRES=False,
        MAX_CONTENT_LENGTH=16 * 1024,
        TRUST_PROXY_HEADERS=os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true",
        PROXY_HOPS=int(os.getenv("PROXY_HOPS", "2")),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SQLALCHEMY_DATABASE_URI"]:
        raise RuntimeError("DATABASE_URL is required. See .env.example.")
    if not app.config["JWT_SECRET_KEY"]:
        raise RuntimeError("JWT_SECRET_KEY is required. See .env.example.")

    if app.config["TRUST_PROXY_HEADERS"]:
        # A load-balanced Beanstalk environment has ALB and nginx in front.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["PROXY_HOPS"], x_proto=1)
    db.init_app(app)
    ma.init_app(app)
    jwt.init_app(app)

    from .resources import BlacklistCollection, BlacklistItem, Health

    api = JsonApi(app)
    api.add_resource(BlacklistCollection, "/blacklists")
    api.add_resource(BlacklistItem, "/blacklists/<string:email>")
    api.add_resource(Health, "/", "/health")

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify(message="Bearer token required"), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify(message="Invalid Bearer token"), 401

    @jwt.expired_token_loader
    def expired_token(token):
        return jsonify(message="Expired Bearer token"), 401

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(message=error.description), error.code

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception("Database operation failed")
        return jsonify(message="Database unavailable"), 503

    @app.cli.command("init-db")
    def init_db():
        """Create the initial database tables without removing existing data."""
        db.create_all()
        click.echo("Database tables ready.")

    @app.cli.command("generate-token")
    def generate_token():
        """Generate a reusable Bearer JWT for the assignment."""
        click.echo(create_access_token(identity="blacklists-client"))

    return app
