from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from marshmallow import ValidationError, fields, validate
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .extensions import db
from .models import Blacklist
from .schemas import blacklist_schema


class BlacklistCollection(Resource):
    @jwt_required
    def post(self):
        if not request.is_json:
            return {"message": "Content-Type must be application/json"}, 415
        try:
            data = blacklist_schema.load(request.get_json())
        except ValidationError as error:
            return {"message": "Invalid request", "errors": error.messages}, 400

        entry = Blacklist(
            email=data["email"],
            app_uuid=str(data["app_uuid"]),
            blocked_reason=data["blocked_reason"],
            ip_address=request.remote_addr or "unknown",
        )
        db.session.add(entry)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"created": False, "message": "Email already blacklisted"}, 409
        return {
            "created": True,
            "message": "Email added to blacklist",
            "email": entry.email,
        }, 201


class BlacklistItem(Resource):
    @jwt_required
    def get(self, email):
        email = email.strip().lower()
        try:
            fields.Email(validate=validate.Length(max=254)).deserialize(email)
        except ValidationError:
            return {"message": "Invalid email"}, 400
        entry = Blacklist.query.filter_by(email=email).first()
        return {
            "email": email,
            "is_blacklisted": entry is not None,
            "blocked_reason": entry.blocked_reason if entry else None,
        }, 200


class Health(Resource):
    def get(self):
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db.session.rollback()
            return {"status": "unavailable"}, 503
        return {"status": "ok"}, 200
