from marshmallow import fields, pre_load, validate

from .extensions import ma


class BlacklistSchema(ma.Schema):
    email = fields.Email(required=True, validate=validate.Length(max=254))
    app_uuid = fields.UUID(required=True)
    blocked_reason = fields.String(
        allow_none=True, load_default=None, validate=validate.Length(max=255)
    )

    @pre_load
    def normalize_email(self, data, **kwargs):
        if isinstance(data, dict) and isinstance(data.get("email"), str):
            data = dict(data)
            data["email"] = data["email"].strip().lower()
        return data


blacklist_schema = BlacklistSchema()
