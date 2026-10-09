from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import Blacklist

PAYLOAD = {
    "email": "person@example.com",
    "app_uuid": "4f47a63e-32d9-441b-bf25-7d14b0ca434e",
    "blocked_reason": "Spam",
}


def test_create_query_and_audit_fields(app, client, auth):
    payload = dict(PAYLOAD, email=" Person@Example.com ")
    response = client.post("/blacklists", json=payload, headers=auth,
                           environ_overrides={"REMOTE_ADDR": "192.0.2.10"})
    assert response.status_code == 201
    assert response.json["created"] is True
    assert client.get("/blacklists/PERSON@example.com", headers=auth).json == {
        "email": "person@example.com", "is_blacklisted": True, "blocked_reason": "Spam"
    }
    with app.app_context():
        entry = Blacklist.query.one()
        assert entry.ip_address == "192.0.2.10"
        assert entry.app_uuid == PAYLOAD["app_uuid"]
        assert isinstance(entry.created_at, datetime)


def test_not_blacklisted(client, auth):
    response = client.get("/blacklists/absent@example.com", headers=auth)
    assert response.status_code == 200
    assert response.json["is_blacklisted"] is False
    assert response.json["blocked_reason"] is None


def test_duplicate_is_case_insensitive(client, auth):
    assert client.post("/blacklists", json=PAYLOAD, headers=auth).status_code == 201
    response = client.post("/blacklists", json=dict(PAYLOAD, email="PERSON@example.com"), headers=auth)
    assert response.status_code == 409
    assert response.json["created"] is False
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}])
@pytest.mark.parametrize("method,path", [("post", "/blacklists"), ("get", "/blacklists/person@example.com")])
def test_authorization_required(client, headers, method, path):
    assert getattr(client, method)(path, headers=headers).status_code == 401


@pytest.mark.parametrize("changes", [
    {"email": "invalid"}, {"email": None}, {"app_uuid": "invalid"},
    {"app_uuid": None}, {"blocked_reason": "x" * 256}, {"blocked_reason": 123},
    {"unexpected": "field"},
])
def test_invalid_payload(client, auth, changes):
    assert client.post("/blacklists", json=dict(PAYLOAD, **changes), headers=auth).status_code == 400


@pytest.mark.parametrize("missing", ["email", "app_uuid"])
def test_required_fields(client, auth, missing):
    payload = dict(PAYLOAD)
    del payload[missing]
    assert client.post("/blacklists", json=payload, headers=auth).status_code == 400


@pytest.mark.parametrize("payload", [[], "string", None])
def test_non_object_json(client, auth, payload):
    import json
    response = client.post("/blacklists", data=json.dumps(payload),
                           content_type="application/json", headers=auth)
    assert response.status_code == 400


def test_optional_reason(client, auth):
    payload = dict(PAYLOAD)
    del payload["blocked_reason"]
    assert client.post("/blacklists", json=payload, headers=auth).status_code == 201
    assert client.get("/blacklists/person@example.com", headers=auth).json["blocked_reason"] is None


def test_reason_boundary(client, auth):
    assert client.post("/blacklists", json=dict(PAYLOAD, blocked_reason="x" * 255), headers=auth).status_code == 201


def test_content_type_and_malformed_json(client, auth):
    assert client.post("/blacklists", data="text", headers=auth).status_code == 415
    assert client.post("/blacklists", data="{", content_type="application/json", headers=auth).status_code == 400


def test_invalid_email_query(client, auth):
    assert client.get("/blacklists/invalid", headers=auth).status_code == 400


def test_forwarded_header_is_ignored_without_proxy_trust(app, client, auth):
    headers = dict(auth, **{"X-Forwarded-For": "198.51.100.10"})
    client.post("/blacklists", json=PAYLOAD, headers=headers)
    with app.app_context():
        assert Blacklist.query.one().ip_address == "127.0.0.1"


def test_health_database_failure(client):
    with patch.object(db.session, "execute", side_effect=OperationalError("SELECT 1", {}, Exception())):
        assert client.get("/health").status_code == 503


def test_health_and_cli(app, client):
    assert client.get("/health").json == {"status": "ok"}
    runner = app.test_cli_runner()
    assert runner.invoke(args=["init-db"]).exit_code == 0
    result = runner.invoke(args=["generate-token"])
    assert result.exit_code == 0
    assert client.get("/blacklists/person@example.com", headers={"Authorization": "Bearer " + result.output.strip()}).status_code == 200
