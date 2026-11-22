from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from flask_jwt_extended import create_access_token
import jwt as pyjwt
import pytest
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import Blacklist


PAYLOAD = {
    "email": "person@example.com",
    "app_uuid": "4f47a63e-32d9-441b-bf25-7d14b0ca434e",
    "blocked_reason": "Original reason",
}


@pytest.mark.parametrize("reason", [None, ""])
def test_create_with_null_or_empty_reason(app, client, auth, reason):
    response = client.post("/blacklists", json=dict(PAYLOAD, blocked_reason=reason), headers=auth)
    assert response.status_code == 201
    with app.app_context():
        assert Blacklist.query.one().blocked_reason == reason


def test_duplicate_does_not_overwrite_original_record(app, client, auth):
    assert client.post("/blacklists", json=PAYLOAD, headers=auth).status_code == 201
    duplicate = dict(PAYLOAD, email=" PERSON@EXAMPLE.COM ",
                     app_uuid="0dc74c24-8033-4d37-9cb3-74e6b26dfb74",
                     blocked_reason="Replacement reason")
    response = client.post("/blacklists", json=duplicate, headers=auth)
    assert response.status_code == 409
    assert response.json["created"] is False
    with app.app_context():
        entry = Blacklist.query.one()
        assert entry.email == PAYLOAD["email"]
        assert entry.app_uuid == PAYLOAD["app_uuid"]
        assert entry.blocked_reason == PAYLOAD["blocked_reason"]


@pytest.mark.parametrize("token_case", ["expired", "different-signing-key"])
def test_rejects_untrusted_token_without_inserting(app, client, token_case):
    with app.app_context():
        if token_case == "expired":
            token = create_access_token(identity="test-client", expires_delta=timedelta(seconds=-60))
        else:
            with patch.dict(app.config, {"JWT_SECRET_KEY": "another-test-key-not-for-production"}):
                token = create_access_token(identity="test-client")
    response = client.post("/blacklists", json=PAYLOAD,
                           headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401
    with app.app_context():
        assert Blacklist.query.count() == 0


def test_failed_commit_rolls_back_and_allows_next_request(app, client, auth):
    error = OperationalError("INSERT", {}, Exception("Simulated database failure"))
    with patch.object(db.session, "commit", side_effect=error):
        response = client.post("/blacklists", json=PAYLOAD, headers=auth)
    assert response.status_code == 503
    assert response.json == {"message": "Database unavailable"}
    with app.app_context():
        assert Blacklist.query.count() == 0
    assert client.post("/blacklists", json=PAYLOAD, headers=auth).status_code == 201


def _legacy_claims():
    now = int(datetime.now(timezone.utc).timestamp())
    return {
        "identity": "blacklists-client", "type": "access", "fresh": False,
        "jti": str(uuid4()), "iat": now, "nbf": now, "user_claims": {},
    }


def test_accepts_legacy_identity_tokens_signed_with_the_same_key(app, client):
    token = pyjwt.encode(_legacy_claims(), app.config["JWT_SECRET_KEY"], algorithm="HS256")
    auth = {"Authorization": "Bearer " + token}
    assert client.post("/blacklists", json=PAYLOAD, headers=auth).status_code == 201
    assert client.get("/blacklists/person@example.com", headers=auth).json["is_blacklisted"] is True


def test_generated_tokens_preserve_identity_and_non_expiring_contract(app, client):
    result = app.test_cli_runner().invoke(args=["generate-token"])
    assert result.exit_code == 0
    claims = pyjwt.decode(result.output.strip(), app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
    assert claims["identity"] == "blacklists-client"
    assert "exp" not in claims
    assert "sub" not in claims
    assert client.get("/blacklists/absent@example.com", headers={
        "Authorization": "Bearer " + result.output.strip(),
    }).status_code == 200


@pytest.mark.parametrize("algorithm", ["none", "HS384", "HS512"])
def test_rejects_unapproved_signing_algorithms_without_writing(app, client, algorithm):
    # Use a long fixture for every HMAC variant, never a deployment credential.
    key = None if algorithm == "none" else "unapproved-algorithm-test-key-only-" * 2
    with patch.dict(app.config, {"JWT_SECRET_KEY": key or "unit-test-secret-only-not-for-production"}):
        token = pyjwt.encode(_legacy_claims(), key, algorithm=algorithm)
        response = client.post("/blacklists", json=PAYLOAD, headers={"Authorization": "Bearer " + token})
        assert response.status_code == 401
        assert response.json == {"message": "Invalid Bearer token"}
    with app.app_context():
        assert Blacklist.query.count() == 0
