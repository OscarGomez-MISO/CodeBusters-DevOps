import sys
from unittest.mock import Mock, patch

import pytest
from flask_jwt_extended import create_access_token

from app import create_app


@pytest.fixture
def lab_app():
    return create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "lab-test-key-only-not-for-production", "NEW_RELIC_ENABLED": True,
        "OBS_LAB_ENABLED": True, "TRUST_PROXY_HEADERS": False,
    })


@pytest.fixture
def lab_auth(lab_app):
    with lab_app.app_context():
        return {"Authorization": "Bearer " + create_access_token(identity="lab-test")}


@pytest.fixture
def agent():
    with patch("app.observability._agent", return_value=Mock()) as get_agent:
        yield get_agent.return_value


def test_lab_route_is_absent_by_default(client, auth):
    assert client.post("/observability/error", headers=auth).status_code == 404


def test_disabled_monitoring_never_imports_the_sdk(app, client):
    app.config["NEW_RELIC_ENABLED"] = False
    with patch.dict(sys.modules, {"newrelic": None, "newrelic.agent": None}):
        assert client.get("/version").status_code == 200


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}])
def test_lab_requires_valid_auth(lab_app, agent, headers):
    assert lab_app.test_client().post("/observability/error", headers=headers).status_code == 401
    agent.notice_error.assert_not_called()


def test_lab_does_not_accept_get(lab_app, agent, lab_auth):
    assert lab_app.test_client().get("/observability/error", headers=lab_auth).status_code == 405
    agent.notice_error.assert_not_called()


def test_lab_reports_a_caught_exception_and_service_recovers(lab_app, agent, lab_auth):
    client = lab_app.test_client()
    response = client.post("/observability/error", headers=lab_auth)
    assert response.status_code == 500
    assert response.json == {"message": "Controlled monitoring error", "scenario": "controlled_error"}
    agent.notice_error.assert_called_once_with(attributes={"lab.scenario": "controlled_error"})
    assert client.get("/version").status_code == 200


def test_lab_is_rate_limited_per_process(lab_app, agent, lab_auth):
    client = lab_app.test_client()
    with patch("app.observability.monotonic", side_effect=[10, 11, 12]):
        assert client.post("/observability/error", headers=lab_auth).status_code == 500
        response = client.post("/observability/error", headers=lab_auth)
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "2"
        assert client.post("/observability/error", headers=lab_auth).status_code == 500
    assert agent.notice_error.call_count == 2


def test_lab_works_without_monitoring(lab_app, lab_auth):
    lab_app.config["NEW_RELIC_ENABLED"] = False
    with patch("app.observability._agent", return_value=None):
        assert lab_app.test_client().post("/observability/error", headers=lab_auth).status_code == 500


def test_sdk_failure_does_not_expose_its_error_or_break_the_api(lab_app, agent, lab_auth, caplog):
    agent.notice_error.side_effect = RuntimeError("fake-private-license")
    client = lab_app.test_client()
    assert client.post("/observability/error", headers=lab_auth).status_code == 500
    assert client.get("/version").status_code == 200
    assert "APM error reporting failed" in caplog.text
    assert "fake-private-license" not in caplog.text


def test_dynamic_email_is_not_part_of_transaction_name(lab_app, agent):
    lab_app.test_client().get("/blacklists/private-person@example.com")
    agent.set_transaction_name.assert_called_once_with(
        "GET /blacklists/<string:email>", group="Flask", priority=10)


def test_unmatched_url_has_a_fixed_transaction_name(lab_app, agent):
    lab_app.test_client().get("/private-person@example.com")
    agent.set_transaction_name.assert_called_once_with("GET <unmatched>", group="Flask", priority=10)


def test_transaction_naming_failure_does_not_break_requests(lab_app, agent, caplog):
    agent.set_transaction_name.side_effect = RuntimeError("fake-private-license")
    assert lab_app.test_client().get("/version").status_code == 200
    assert "APM transaction naming failed" in caplog.text
    assert "fake-private-license" not in caplog.text


def test_unavailable_sdk_does_not_break_requests(lab_app, lab_auth, caplog):
    with patch("app.observability._agent", side_effect=ImportError("fake-private-license")):
        client = lab_app.test_client()
        assert client.get("/version").status_code == 200
        assert client.post("/observability/error", headers=lab_auth).status_code == 500
    assert "fake-private-license" not in caplog.text
