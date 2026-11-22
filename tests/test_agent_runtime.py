"""Exercise the real SDK against its local developer collector, never an account."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PROBE = """
import newrelic.agent
from application import application
from flask_jwt_extended import create_access_token

newrelic.agent.register_application(timeout=5)
transactions = []
@application.after_request
def observe(response):
    transactions.append(newrelic.agent.current_transaction())
    return response

client = application.test_client()
assert client.get('/blacklists/fake-person@example.com').status_code == 401
transaction = transactions[-1]
assert transaction is not None
assert transaction.name == 'GET /blacklists/<string:email>', transaction.name
assert transaction.group == 'Flask'
with application.app_context():
    token = create_access_token(identity='offline-sdk-test')
assert client.post('/observability/error', headers={'Authorization': 'Bearer ' + token}).status_code == 500
assert transactions[-1].name == 'POST /observability/error'
assert client.get('/version').status_code == 200
print('AGENT_RUNTIME_OK')
"""


def test_real_agent_names_requests_with_an_offline_collector(tmp_path):
    config = tmp_path / "offline.ini"
    config.write_text(
        (ROOT / "newrelic.ini").read_text() + "\n"
        "monitor_mode = false\ndeveloper_mode = true\n"
        "utilization.detect_aws = false\nutilization.detect_azure = false\n"
        "utilization.detect_gcp = false\nutilization.detect_docker = false\n",
        encoding="utf-8",
    )
    env = dict(os.environ, DATABASE_URL="sqlite:///:memory:",
               JWT_SECRET_KEY="offline-sdk-test-only-not-for-production", NEW_RELIC_ENABLED="true",
               NEW_RELIC_LICENSE_KEY="0" * 40, NEW_RELIC_APP_NAME="cb-e4-offline-test",
               NEW_RELIC_CONFIG_FILE=str(config), NEW_RELIC_MONITOR_MODE="false",
               NEW_RELIC_DEVELOPER_MODE="true", OBS_LAB_ENABLED="true",
               NEW_RELIC_LOG="stderr")
    result = subprocess.run(
        [shutil.which("newrelic-admin"), "run-program", sys.executable, "-c", PROBE],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "AGENT_RUNTIME_OK" in result.stdout
