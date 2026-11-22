"""Optional APM helpers and an opt-in, bounded laboratory error."""
from threading import Lock
from time import monotonic

from flask import current_app, jsonify, request
from flask_jwt_extended import jwt_required


class ControlledMonitoringError(RuntimeError):
    pass


def _agent():
    if not current_app.config["NEW_RELIC_ENABLED"]:
        return None
    import newrelic.agent
    return newrelic.agent


def configure_observability(app):
    @app.before_request
    def name_apm_transaction():
        try:
            agent = _agent()
            if agent is None:
                return
            # Route templates keep client emails out of transaction names.
            route = request.url_rule.rule if request.url_rule else "<unmatched>"
            agent.set_transaction_name(request.method + " " + route, group="Flask", priority=10)
        except Exception:
            app.logger.warning("APM transaction naming failed")

    if not app.config["OBS_LAB_ENABLED"]:
        return

    lock = Lock()
    last_error_at = None

    @app.route("/observability/error", methods=["POST"])
    @jwt_required()
    def controlled_error():
        nonlocal last_error_at
        with lock:
            now = monotonic()
            if last_error_at is not None and now - last_error_at < 2:
                return jsonify(message="Lab error rate limited"), 429, {"Retry-After": "2"}
            last_error_at = now
        try:
            raise ControlledMonitoringError("Controlled error for the observability lab")
        except ControlledMonitoringError:
            try:
                agent = _agent()
                if agent is not None:
                    agent.notice_error(attributes={"lab.scenario": "controlled_error"})
            except Exception:
                app.logger.warning("APM error reporting failed")
            return jsonify(message="Controlled monitoring error", scenario="controlled_error"), 500
