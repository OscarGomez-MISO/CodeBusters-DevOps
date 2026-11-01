"""Pruebas unitarias de GET /blacklists/<email>, /health, / y /version.

Usan SQLite en memoria (fixtures de conftest.py) y simulan los fallos de base
de datos con mocks, de modo que no dependen de PostgreSQL/RDS durante el CI.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import Blacklist

PAYLOAD = {
    "email": "person@example.com",
    "app_uuid": "4f47a63e-32d9-441b-bf25-7d14b0ca434e",
    "blocked_reason": "Spam",
}

HEALTH_PATHS = ["/health", "/"]


def _block(client, auth, **changes):
    response = client.post("/blacklists", json=dict(PAYLOAD, **changes), headers=auth)
    assert response.status_code == 201
    return response


# ---------------------------------------------------------------------------
# GET /blacklists/<email>
# ---------------------------------------------------------------------------

def test_get_blacklisted_email_returns_flag_and_reason(client, auth):
    _block(client, auth)
    response = client.get("/blacklists/person@example.com", headers=auth)
    assert response.status_code == 200
    assert response.is_json
    assert response.json == {
        "email": "person@example.com",
        "is_blacklisted": True,
        "blocked_reason": "Spam",
    }


def test_get_normalizes_case_and_surrounding_spaces(client, auth):
    _block(client, auth)
    response = client.get("/blacklists/%20PERSON@Example.COM%20", headers=auth)
    assert response.status_code == 200
    assert response.json["email"] == "person@example.com"
    assert response.json["is_blacklisted"] is True


def test_get_url_encoded_special_characters(client, auth):
    _block(client, auth, email="first.last+tag@example.com", blocked_reason="Fraude")
    response = client.get("/blacklists/first.last%2Btag%40example.com", headers=auth)
    assert response.status_code == 200
    assert response.json == {
        "email": "first.last+tag@example.com",
        "is_blacklisted": True,
        "blocked_reason": "Fraude",
    }


def test_get_only_matches_the_exact_email(client, auth):
    _block(client, auth)
    response = client.get("/blacklists/other.person@example.com", headers=auth)
    assert response.status_code == 200
    assert response.json["is_blacklisted"] is False
    assert response.json["blocked_reason"] is None


def test_get_is_read_only(app, client, auth):
    assert client.get("/blacklists/absent@example.com", headers=auth).status_code == 200
    with app.app_context():
        assert Blacklist.query.count() == 0


def test_get_rejects_email_longer_than_254_characters(client, auth):
    long_email = "a" * 250 + "@example.com"
    response = client.get("/blacklists/" + long_email, headers=auth)
    assert response.status_code == 400


@pytest.mark.parametrize("token_case", ["expired", "different-signing-key"])
def test_get_rejects_untrusted_token(app, client, token_case):
    with app.app_context():
        if token_case == "expired":
            token = create_access_token(identity="test-client", expires_delta=timedelta(seconds=-60))
        else:
            with patch.dict(app.config, {"JWT_SECRET_KEY": "another-test-key"}):
                token = create_access_token(identity="test-client")
    response = client.get("/blacklists/person@example.com",
                          headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /health y su alias GET /
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_ok_without_authentication(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.is_json
    assert response.json["status"] == "ok"


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_ignores_invalid_authorization_header(client, path):
    response = client.get(path, headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 200
    assert response.json["status"] == "ok"


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_reports_database_failure_and_recovers(client, path):
    error = OperationalError("SELECT 1", {}, Exception("Simulated database failure"))
    with patch.object(db.session, "execute", side_effect=error):
        response = client.get(path)
    assert response.status_code == 503
    assert response.json["status"] == "unavailable"
    # Al restablecerse la base, la siguiente consulta vuelve a responder ok.
    recovered = client.get(path)
    assert recovered.status_code == 200
    assert recovered.json["status"] == "ok"


# ---------------------------------------------------------------------------
# GET /version
# ---------------------------------------------------------------------------

def test_version_without_authentication(client):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.is_json
    assert response.json == {"version": "2.0.0"}


def test_version_rejects_unsupported_method(client):
    assert client.post("/version").status_code == 405
