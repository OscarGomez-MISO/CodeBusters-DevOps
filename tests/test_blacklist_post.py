from datetime import timedelta
from unittest.mock import patch

from flask_jwt_extended import create_access_token
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
            with patch.dict(app.config, {"JWT_SECRET_KEY": "another-test-key"}):
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
