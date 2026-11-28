"""Load test settings and stage plans, kept free of Locust imports so CI can test them."""
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import uuid


DEFAULT_APP_UUID = "4f47a63e-32d9-441b-bf25-7d14b0ca434e"
MAX_USERS = 50
MAX_SEED_EMAILS = 200
RUN_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,32}$")

# Task weights out of 20: 14 DB lookups (70 %), 5 unique creations (25 %),
# 1 health/version (5 %). The locustfile uses these values directly.
WEIGHT_LOOKUP = 14
WEIGHT_CREATE = 5
WEIGHT_PROBE = 1


@dataclass(frozen=True)
class Stage:
    """Hold `users` for `duration` seconds, reaching them at `spawn_rate` users/s."""

    users: int
    duration: int
    spawn_rate: float


def build_stages(scenario, e2_max_users=25):
    """Return the stage plan for E1 (baseline) or E2 (stress)."""
    scenario = scenario.strip().lower()
    if scenario == "e1":
        return [Stage(1, 60, 1), Stage(5, 120, 1)]
    if scenario == "e2":
        if e2_max_users not in (25, 50):
            raise ValueError("LOCUST_E2_MAX_USERS must be 25 or 50.")
        stages = [Stage(10, 180, 1), Stage(25, 180, 1)]
        if e2_max_users == 50:
            stages.append(Stage(50, 180, 2))
        return stages
    raise ValueError("LOCUST_SCENARIO must be e1 or e2.")


def stage_at(stages, run_time):
    """Return the active stage for `run_time` seconds, or None once the plan ends."""
    elapsed = 0
    for stage in stages:
        elapsed += stage.duration
        if run_time < elapsed:
            return stage
    return None


def total_duration(stages):
    return sum(stage.duration for stage in stages)


@dataclass(frozen=True)
class Settings:
    token: str
    app_uuid: str
    run_id: str
    seed_count: int
    scenario: str
    e2_max_users: int
    max_failure_ratio: float
    guard_window: int


def _int(env, name, default, low, high):
    raw = env.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        raise ValueError("{} must be an integer.".format(name))
    if not low <= value <= high:
        raise ValueError("{} must be between {} and {}.".format(name, low, high))
    return value


def load_settings(env):
    """Validate the LOCUST_* environment variables; the JWT is never logged."""
    token = env.get("LOCUST_TOKEN", "").strip()
    if not token:
        raise ValueError("LOCUST_TOKEN is required (JWT of the target environment).")
    if token.lower().startswith("bearer "):
        raise ValueError("LOCUST_TOKEN must be the bare JWT, without 'Bearer '.")

    app_uuid = env.get("LOCUST_APP_UUID", "").strip() or DEFAULT_APP_UUID
    try:
        uuid.UUID(app_uuid)
    except ValueError:
        raise ValueError("LOCUST_APP_UUID must be a valid UUID.")

    run_id = env.get("LOCUST_RUN_ID", "").strip().lower()
    if not run_id:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S")
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("LOCUST_RUN_ID may only contain a-z, 0-9 and '-', up to 32 characters.")

    scenario = env.get("LOCUST_SCENARIO", "").strip().lower()
    e2_max_users = _int(env, "LOCUST_E2_MAX_USERS", 25, 25, MAX_USERS)
    if scenario:
        build_stages(scenario, e2_max_users)

    raw_ratio = env.get("LOCUST_MAX_FAILURE_RATIO", "").strip()
    try:
        max_failure_ratio = float(raw_ratio) if raw_ratio else 0.05
    except ValueError:
        raise ValueError("LOCUST_MAX_FAILURE_RATIO must be a number.")
    if not 0 < max_failure_ratio <= 1:
        raise ValueError("LOCUST_MAX_FAILURE_RATIO must be in (0, 1].")

    return Settings(
        token=token,
        app_uuid=app_uuid,
        run_id=run_id,
        seed_count=_int(env, "LOCUST_SEED_EMAILS", 20, 1, MAX_SEED_EMAILS),
        scenario=scenario,
        e2_max_users=e2_max_users,
        max_failure_ratio=max_failure_ratio,
        guard_window=_int(env, "LOCUST_GUARD_WINDOW", 60, 10, 600),
    )


def seed_emails(count):
    """Stable seed addresses: reruns reuse them (409) instead of growing the table."""
    return ["seed-{:03d}@example.com".format(i) for i in range(count)]


def unique_email(run_id):
    return "load-{}-{}@example.com".format(run_id, uuid.uuid4().hex[:12])


class FailureGuard:
    """Sliding-window failure ratio over cumulative (requests, failures) samples."""

    def __init__(self, window, max_ratio, min_requests=20):
        self.window = window
        self.max_ratio = max_ratio
        self.min_requests = min_requests
        self.samples = []

    def add(self, now, requests, failures):
        """Record a sample; return the window failure ratio if it exceeds the limit."""
        self.samples.append((now, requests, failures))
        while len(self.samples) > 1 and now - self.samples[1][0] >= self.window:
            self.samples.pop(0)
        start_time, start_requests, start_failures = self.samples[0]
        if now - start_time < self.window:
            return None
        delta_requests = requests - start_requests
        if delta_requests < self.min_requests:
            return None
        ratio = (failures - start_failures) / delta_requests
        return ratio if ratio > self.max_ratio else None
