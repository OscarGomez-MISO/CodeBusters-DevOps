import re

import pytest

from loadtests import settings as s


BASE_ENV = {"LOCUST_TOKEN": "eyJ.fake.jwt"}


def env(**extra):
    data = dict(BASE_ENV)
    data.update(extra)
    return data


def test_defaults():
    cfg = s.load_settings(env(LOCUST_RUN_ID="r1"))
    assert cfg.app_uuid == s.DEFAULT_APP_UUID
    assert cfg.seed_count == 20
    assert cfg.scenario == ""
    assert cfg.max_failure_ratio == 0.05
    assert cfg.guard_window == 60


def test_generated_run_id_is_valid():
    cfg = s.load_settings(env())
    assert s.RUN_ID_PATTERN.match(cfg.run_id)


@pytest.mark.parametrize("extra, message", [
    ({"LOCUST_TOKEN": ""}, "LOCUST_TOKEN is required"),
    ({"LOCUST_TOKEN": "Bearer eyJ.a.b"}, "bare JWT"),
    ({"LOCUST_APP_UUID": "not-a-uuid"}, "valid UUID"),
    ({"LOCUST_RUN_ID": "Run_01!"}, "LOCUST_RUN_ID"),
    ({"LOCUST_SCENARIO": "e9"}, "e1 or e2"),
    ({"LOCUST_E2_MAX_USERS": "40", "LOCUST_SCENARIO": "e2"}, "25 or 50"),
    ({"LOCUST_E2_MAX_USERS": "100"}, "between 25 and 50"),
    ({"LOCUST_SEED_EMAILS": "0"}, "between 1 and 200"),
    ({"LOCUST_SEED_EMAILS": "abc"}, "integer"),
    ({"LOCUST_MAX_FAILURE_RATIO": "0"}, "(0, 1]"),
    ({"LOCUST_GUARD_WINDOW": "5"}, "between 10 and 600"),
])
def test_invalid_settings(extra, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        s.load_settings(env(**extra))


def test_error_message_never_contains_token():
    with pytest.raises(ValueError) as error:
        s.load_settings(env(LOCUST_TOKEN="Bearer secret-value"))
    assert "secret-value" not in str(error.value)


def test_e1_plan():
    stages = s.build_stages("e1")
    assert [(st.users, st.duration) for st in stages] == [(1, 60), (5, 120)]
    assert s.total_duration(stages) == 180


def test_e2_plan_default_and_extended():
    assert [st.users for st in s.build_stages("E2")] == [10, 25]
    extended = s.build_stages("e2", 50)
    assert [st.users for st in extended] == [10, 25, 50]
    assert max(st.users for st in extended) <= s.MAX_USERS


def test_stage_at_walks_the_plan_and_ends():
    stages = s.build_stages("e1")
    assert s.stage_at(stages, 0).users == 1
    assert s.stage_at(stages, 59.9).users == 1
    assert s.stage_at(stages, 60).users == 5
    assert s.stage_at(stages, 179).users == 5
    assert s.stage_at(stages, 180) is None


def test_weights_match_the_70_25_5_mix():
    total = s.WEIGHT_LOOKUP + s.WEIGHT_CREATE + s.WEIGHT_PROBE
    assert (s.WEIGHT_LOOKUP / total, s.WEIGHT_CREATE / total, s.WEIGHT_PROBE / total) == (
        0.70, 0.25, 0.05)


def test_seed_emails_are_stable_and_fictitious():
    assert s.seed_emails(3) == s.seed_emails(3)
    assert all(e.endswith("@example.com") for e in s.seed_emails(3))


def test_unique_emails_carry_run_id():
    first, second = s.unique_email("r1"), s.unique_email("r1")
    assert first != second
    assert first.startswith("load-r1-") and first.endswith("@example.com")


def test_failure_guard_waits_for_a_full_window():
    guard = s.FailureGuard(window=60, max_ratio=0.05, min_requests=20)
    assert guard.add(0, 0, 0) is None
    assert guard.add(30, 100, 50) is None  # window not complete yet


def test_failure_guard_trips_only_above_limit():
    guard = s.FailureGuard(window=60, max_ratio=0.05, min_requests=20)
    guard.add(0, 0, 0)
    assert guard.add(60, 100, 5) is None  # exactly 5 % is allowed
    assert guard.add(120, 200, 20) == pytest.approx(0.15)


def test_failure_guard_slides_past_old_failures():
    guard = s.FailureGuard(window=60, max_ratio=0.05, min_requests=20)
    guard.add(0, 0, 0)
    guard.add(60, 100, 50)  # bad first minute
    assert guard.add(120, 200, 50) is None  # last minute had no failures


def test_failure_guard_ignores_low_traffic():
    guard = s.FailureGuard(window=60, max_ratio=0.05, min_requests=20)
    guard.add(0, 0, 0)
    assert guard.add(60, 10, 10) is None
