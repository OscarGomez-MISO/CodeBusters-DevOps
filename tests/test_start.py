import configparser
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import start


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("env", [{}, {"NEW_RELIC_ENABLED": "false"}])
def test_monitoring_disabled_does_not_require_a_license(env):
    assert start.build_command(env) == start.GUNICORN


def test_enabled_monitoring_wraps_the_same_server():
    env = {"NEW_RELIC_ENABLED": "true", "NEW_RELIC_LICENSE_KEY": "fake-test-key",
           "NEW_RELIC_APP_NAME": "test-local"}
    assert start.build_command(env) == ["newrelic-admin", "run-program"] + start.GUNICORN


@pytest.mark.parametrize("missing", ["NEW_RELIC_LICENSE_KEY", "NEW_RELIC_APP_NAME"])
def test_enabled_monitoring_requires_runtime_identity(missing):
    env = {"NEW_RELIC_ENABLED": "true", "NEW_RELIC_LICENSE_KEY": "fake-test-key",
           "NEW_RELIC_APP_NAME": "test-local", missing: " "}
    with pytest.raises(ValueError, match=missing):
        start.build_command(env)


def test_invalid_enabled_flag_fails_without_echoing_secrets():
    with pytest.raises(ValueError, match="must be true or false"):
        start.build_command({"NEW_RELIC_ENABLED": "invalid-secret-value"})


def test_start_replaces_the_process_and_sets_non_secret_defaults(monkeypatch):
    monkeypatch.setenv("NEW_RELIC_ENABLED", "false")
    monkeypatch.delenv("NEW_RELIC_CONFIG_FILE", raising=False)
    monkeypatch.delenv("NEW_RELIC_LOG", raising=False)
    with patch.object(start.os, "execvpe") as execute:
        start.main()
    binary, command, env = execute.call_args.args
    assert binary == "gunicorn"
    assert command == start.GUNICORN
    assert env["NEW_RELIC_CONFIG_FILE"] == str(ROOT / "newrelic.ini")
    assert env["NEW_RELIC_LOG"] == "stderr"


def test_start_rejects_missing_license_without_starting_server(monkeypatch, capsys):
    monkeypatch.setenv("NEW_RELIC_ENABLED", "true")
    monkeypatch.setenv("NEW_RELIC_LICENSE_KEY", "")
    with patch.object(start.os, "execvpe") as execute:
        assert start.main() == 1
    execute.assert_not_called()
    assert "NEW_RELIC_LICENSE_KEY is required" in capsys.readouterr().err


def test_agent_config_has_no_identity_and_restricts_data_collection():
    config = configparser.ConfigParser()
    config.read(ROOT / "newrelic.ini")
    settings = config["newrelic"]
    assert "license_key" not in settings
    assert "app_name" not in settings
    assert settings["transaction_tracer.record_sql"] == "obfuscated"
    assert "request.headers.*" in settings["attributes.exclude"]
    assert "request.parameters.*" in settings["attributes.exclude"]
    assert "request.uri" in settings["attributes.exclude"]
    assert not settings.getboolean("application_logging.forwarding.enabled")
