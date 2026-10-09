import os
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.extensions import db
from app.models import Blacklist


@pytest.mark.skipif(not os.getenv("POSTGRES_TEST_URL"), reason="POSTGRES_TEST_URL not configured")
def test_postgres_persistence_across_app_instances():
    config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": os.getenv("POSTGRES_TEST_URL"),
        "JWT_SECRET_KEY": "postgres-integration-test-key",
        "TRUST_PROXY_HEADERS": True,
    }
    app = create_app(config)
    email = "integration-{}@example.com".format(uuid4())
    app_uuid = str(uuid4())
    with app.app_context():
        db.create_all()
        token = create_access_token(identity="integration-test")
    auth = {"Authorization": "Bearer " + token}
    try:
        response = app.test_client().post("/blacklists", headers=dict(auth, **{
            "X-Forwarded-For": "198.51.100.10, 192.0.2.10",
        }), json={"email": email, "app_uuid": app_uuid, "blocked_reason": "Integration test"})
        assert response.status_code == 201
        second_app = create_app(config)
        client = second_app.test_client()
        assert client.get("/blacklists/" + email, headers=auth).json == {
            "email": email, "is_blacklisted": True, "blocked_reason": "Integration test",
        }
        assert client.post("/blacklists", headers=auth, json={
            "email": email.upper(), "app_uuid": app_uuid,
        }).status_code == 409
        assert client.get("/health").status_code == 200
        with second_app.app_context():
            entry = Blacklist.query.filter_by(email=email).one()
            assert entry.ip_address == "198.51.100.10"
            assert entry.created_at.utcoffset().total_seconds() == 0
    finally:
        with app.app_context():
            Blacklist.query.filter_by(email=email).delete()
            db.session.commit()
            db.session.remove()
