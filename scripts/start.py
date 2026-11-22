"""Start the existing WSGI server, optionally under the New Relic wrapper."""
import os
from pathlib import Path
import sys


GUNICORN = [
    "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1",
    "--access-logfile", "-", "--error-logfile", "-", "--no-control-socket",
    "application:application",
]


def build_command(env):
    enabled = env.get("NEW_RELIC_ENABLED", "false").strip().lower()
    if enabled not in ("true", "false"):
        raise ValueError("NEW_RELIC_ENABLED must be true or false.")
    if enabled == "false":
        return list(GUNICORN)
    for name in ("NEW_RELIC_LICENSE_KEY", "NEW_RELIC_APP_NAME"):
        if not env.get(name, "").strip():
            raise ValueError("{} is required when monitoring is enabled.".format(name))
    return ["newrelic-admin", "run-program"] + GUNICORN


def main():
    env = dict(os.environ)
    env.setdefault("NEW_RELIC_CONFIG_FILE", str(Path(__file__).resolve().parents[1] / "newrelic.ini"))
    env.setdefault("NEW_RELIC_LOG", "stderr")
    try:
        command = build_command(env)
    except ValueError as error:
        print("start: " + str(error), file=sys.stderr)
        return 1
    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    sys.exit(main())
