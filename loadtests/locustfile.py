"""Reproducible load for the blacklists API (Entrega 4, E1 baseline and E2 stress).

Run from the repository root with the separate tools environment, for example:

    LOCUST_SCENARIO=e1 locust -f loadtests/locustfile.py --headless \
        --host http://<own-alb> --csv "$HOME/cb-e4-load/e1" --csv-full-history

See docs/Entrega-4-Pruebas-Estres.md for the variables, scenarios and safety rules.
"""
import logging
import os
import random
import sys
import time

import gevent
import requests
from locust import LoadTestShape, HttpUser, between, events, task

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import (  # noqa: E402
    WEIGHT_CREATE,
    WEIGHT_LOOKUP,
    WEIGHT_PROBE,
    FailureGuard,
    build_stages,
    load_settings,
    seed_emails,
    stage_at,
    total_duration,
    unique_email,
)

log = logging.getLogger("cb-e4-load")

try:
    SETTINGS = load_settings(os.environ)
except ValueError as error:
    sys.stderr.write("loadtests: {}\n".format(error))
    sys.exit(2)

SEEDS = seed_emails(SETTINGS.seed_count)
_guard_greenlet = None


def _auth_headers():
    return {"Authorization": "Bearer " + SETTINGS.token}


@events.test_start.add_listener
def seed_and_guard(environment, **kwargs):
    """Create the seed emails once (201 or 409 are both fine) and start the failure guard."""
    global _guard_greenlet
    host = (environment.host or "").rstrip("/")
    if not host:
        _abort(environment, "Set the target with --host; there is no default host.")
        return
    created = existing = 0
    for email in SEEDS:
        try:
            response = requests.post(
                host + "/blacklists",
                json={"email": email, "app_uuid": SETTINGS.app_uuid,
                      "blocked_reason": "seed carga E4"},
                headers=_auth_headers(),
                timeout=10,
            )
        except requests.RequestException as error:
            _abort(environment, "Seeding failed: {}.".format(type(error).__name__))
            return
        if response.status_code == 201:
            created += 1
        elif response.status_code == 409:
            existing += 1
        else:
            _abort(environment, "Seeding failed with HTTP {} (check host and JWT).".format(
                response.status_code))
            return
    log.info(
        "run_id=%s scenario=%s seeds created=%d existing=%d start_utc=%s",
        SETTINGS.run_id, SETTINGS.scenario or "manual", created, existing,
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    if environment.runner is not None:
        _guard_greenlet = gevent.spawn(_failure_guard, environment)


@events.test_stop.add_listener
def stop_guard(environment, **kwargs):
    global _guard_greenlet
    if _guard_greenlet is not None:
        _guard_greenlet.kill(block=False)
        _guard_greenlet = None
    log.info("run_id=%s stop_utc=%s", SETTINGS.run_id,
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def _abort(environment, message):
    log.error(message)
    environment.process_exit_code = 2
    if environment.runner is not None:
        gevent.spawn_later(0, environment.runner.quit)


def _failure_guard(environment):
    """Stop the run if unexpected failures exceed the limit during the guard window."""
    guard = FailureGuard(SETTINGS.guard_window, SETTINGS.max_failure_ratio)
    while True:
        gevent.sleep(5)
        total = environment.runner.stats.total
        ratio = guard.add(time.monotonic(), total.num_requests, total.num_failures)
        if ratio is not None:
            log.error(
                "Stopping: %.1f %% failures in the last %d s (limit %.1f %%).",
                ratio * 100, SETTINGS.guard_window, SETTINGS.max_failure_ratio * 100,
            )
            environment.process_exit_code = 3
            environment.runner.quit()
            return


class BlacklistUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(WEIGHT_LOOKUP)
    def lookup_seeded_email(self):
        email = random.choice(SEEDS)
        with self.client.get(
            "/blacklists/" + email,
            headers=_auth_headers(),
            name="GET /blacklists/[email]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure("HTTP {}".format(response.status_code))
            elif response.json().get("is_blacklisted") is not True:
                response.failure("seed email not blacklisted")

    @task(WEIGHT_CREATE)
    def create_unique_email(self):
        with self.client.post(
            "/blacklists",
            json={
                "email": unique_email(SETTINGS.run_id),
                "app_uuid": SETTINGS.app_uuid,
                "blocked_reason": "carga E4 " + SETTINGS.run_id,
            },
            headers=_auth_headers(),
            name="POST /blacklists",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure("HTTP {}".format(response.status_code))

    @task(WEIGHT_PROBE)
    def health_or_version(self):
        path = random.choice(("/health", "/version"))
        with self.client.get(path, name="GET " + path, catch_response=True) as response:
            if response.status_code != 200:
                response.failure("HTTP {}".format(response.status_code))


if SETTINGS.scenario:

    class ScenarioShape(LoadTestShape):
        """E1/E2 stage plan; it overrides -u, -r and -t when LOCUST_SCENARIO is set."""

        stages = build_stages(SETTINGS.scenario, SETTINGS.e2_max_users)

        def tick(self):
            stage = stage_at(self.stages, self.get_run_time())
            if stage is None:
                return None
            return stage.users, stage.spawn_rate

    log.info("Scenario %s: %d s in total", SETTINGS.scenario,
             total_duration(ScenarioShape.stages))
