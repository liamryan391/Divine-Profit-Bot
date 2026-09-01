from __future__ import annotations

import ipaddress
import json
import logging
import mimetypes
import secrets
import ssl
import time
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from . import __version__
from .core import (
    WORKER_STATUS_BUDGET_MS,
    AuthenticationError,
    DivineToolError,
    LoginThrottledError,
    WorkerCycleBusyError,
    add_exception,
    add_income,
    add_lead_note,
    advance_lead,
    auth_status,
    create_account,
    create_session,
    create_approval_draft,
    create_lead,
    create_receivable,
    create_recurring_revenue_template,
    create_revenue_rule,
    create_temple,
    confirm_reconciliation_match,
    dashboard_snapshot,
    destroy_session,
    enqueue_command,
    ensure_state,
    external_connections_snapshot,
    follow_up_summary,
    format_money,
    generate_opportunities,
    generate_report,
    import_income_csv,
    import_reconciliation_csv,
    ignore_reconciliation_transaction,
    lead_conversion_summary,
    list_approval_actions,
    list_events,
    list_income,
    lead_pipeline_summary,
    list_leads_page,
    list_revenue_rules,
    list_temples,
    link_income_to_lead,
    load_config,
    parse_date,
    parse_money_to_minor,
    process_follow_up_cadences,
    process_recurring_revenue,
    record_follow_up_outcome,
    record_lead_conversion,
    record_receivable_payment,
    receivables_summary,
    recurring_revenue_summary,
    reconciliation_summary,
    revenue_rules_summary,
    run_worker_cycle,
    review_approval_action,
    row_to_dict,
    queue_receivable_reminder,
    set_mood,
    set_quota,
    strategy_roi_summary,
    switch_temple,
    temple_summary,
    update_lead,
    update_receivable_status,
    update_recurring_revenue_template_status,
    update_revenue_rule,
    update_account_profile,
    update_client_contact_state,
    update_follow_up_cadence,
    worker_status,
)
from .deployment import deployment_environment, normalize_origin


STATIC_DIR = Path(__file__).with_name("static")
SESSION_COOKIE = "divine_session"
MAX_JSON_BODY_BYTES = 256 * 1024
MAX_CSV_IMPORT_BODY_BYTES = 5 * 1024 * 1024
MAX_CSV_TEXT_BYTES = 4 * 1024 * 1024
LOGGER = logging.getLogger("divine_tool.web")


class RequestPolicyError(Exception):
    def __init__(
        self,
        message: str,
        status: HTTPStatus,
        *,
        headers: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.headers = headers or []


def session_cookie_header(token: str, expires_at: str, secure: bool | None = None) -> str:
    try:
        expires = datetime.fromisoformat(expires_at)
        max_age = max(int((expires - datetime.now()).total_seconds()), 60)
    except ValueError:
        max_age = 12 * 60 * 60
    if secure is None:
        secure = bool(deployment_environment()["cookie_secure"])
    attributes = [f"{SESSION_COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Strict", f"Max-Age={max_age}"]
    if secure:
        attributes.append("Secure")
    return "Set-Cookie: " + "; ".join(attributes)


def clear_session_cookie_header(secure: bool | None = None) -> str:
    if secure is None:
        secure = bool(deployment_environment()["cookie_secure"])
    attributes = [f"{SESSION_COOKIE}=", "Path=/", "HttpOnly", "SameSite=Strict", "Max-Age=0"]
    if secure:
        attributes.append("Secure")
    return "Set-Cookie: " + "; ".join(attributes)


def deployment_health(environment: Mapping[str, Any] | None = None) -> dict[str, Any]:
    env = environment if environment is not None else deployment_environment()
    return {
        "mode": env["mode"],
        "public_url": env["public_url"],
        "cookie_secure": env["cookie_secure"],
        "allowed_origins": env["allowed_origins"],
        "csrf_require_origin": env["csrf_require_origin"],
        "trust_proxy": env["trust_proxy"],
        "force_https": env["force_https"],
    }


def run_web(data_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    ensure_state(data_dir)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = make_handler(data_dir)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}"
    print(f"Divine Tool web app running at {url}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def make_handler(
    data_dir: Path,
    environ: Mapping[str, str] | None = None,
) -> type[BaseHTTPRequestHandler]:
    security = deployment_environment(environ)

    class DivineRequestHandler(BaseHTTPRequestHandler):
        server_version = "DivineToolHTTP/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                self.enforce_secure_transport(parsed.path)
                if parsed.path == "/api/auth/status":
                    self.send_json({"auth": auth_status(data_dir, self.session_token())})
                    return
                if parsed.path.startswith("/api/") and parsed.path != "/api/health":
                    account = self.require_auth()
                    if account is None:
                        return
                else:
                    account = None
                if parsed.path == "/api/status":
                    self.send_json(dashboard_payload(data_dir, account))
                    return
                if parsed.path == "/api/worker/status":
                    started = time.perf_counter()
                    worker = worker_status(data_dir)
                    duration_ms = round((time.perf_counter() - started) * 1000, 2)
                    self.send_json(
                        {
                            "version": __version__,
                            "checked_at": datetime.now().isoformat(timespec="seconds"),
                            "duration_ms": duration_ms,
                            "budget_ms": WORKER_STATUS_BUDGET_MS,
                            "within_budget": duration_ms <= WORKER_STATUS_BUDGET_MS,
                            "worker": worker,
                        }
                    )
                    return
                if parsed.path == "/api/health":
                    worker = worker_status(data_dir)
                    self.send_json(
                        {
                            "ok": True,
                            "version": __version__,
                            "liveness": {"ok": True, "state": "live", "component": "web"},
                            "readiness": {"ok": True, "state": "ready", "component": "web"},
                            "worker": worker,
                            "auth": auth_status(data_dir),
                            "deployment": deployment_health(security),
                        }
                    )
                    return
                if parsed.path == "/api/logs":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["50"])[0])
                    self.send_json({"events": serialize_rows(list_events(data_dir, limit=limit))})
                    return
                if parsed.path == "/api/income":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["20"])[0])
                    self.send_json({"income": serialize_income(list_income(data_dir, limit=limit))})
                    return
                if parsed.path == "/api/opportunities":
                    opportunities = generate_opportunities(data_dir)
                    self.send_json({"opportunities": opportunities, "top_opportunity": opportunities[0] if opportunities else None})
                    return
                if parsed.path == "/api/strategy-roi":
                    self.send_json({"strategy_roi": strategy_roi_summary(data_dir)})
                    return
                if parsed.path == "/api/conversions/summary":
                    self.send_json({"conversions": lead_conversion_summary(data_dir)})
                    return
                if parsed.path == "/api/receivables":
                    query = parse_qs(parsed.query)
                    status = query.get("status", ["all"])[0]
                    limit = int(query.get("limit", ["60"])[0])
                    self.send_json({"receivables": receivables_summary(data_dir, status=status, limit=limit)})
                    return
                if parsed.path == "/api/reconciliation":
                    query = parse_qs(parsed.query)
                    status = query.get("status", ["all"])[0]
                    limit = int(query.get("limit", ["60"])[0])
                    self.send_json({"reconciliation": reconciliation_summary(data_dir, status=status, limit=limit)})
                    return
                if parsed.path == "/api/follow-ups":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["60"])[0])
                    self.send_json({"follow_ups": follow_up_summary(data_dir, limit=limit)})
                    return
                if parsed.path == "/api/recurring-revenue":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["60"])[0])
                    self.send_json({"recurring_revenue": recurring_revenue_summary(data_dir, limit=limit)})
                    return
                if parsed.path == "/api/revenue-rules/summary":
                    self.send_json({"revenue_rules": revenue_rules_summary(data_dir)})
                    return
                if parsed.path == "/api/revenue-rules":
                    query = parse_qs(parsed.query)
                    status = query.get("status", ["all"])[0]
                    limit = int(query.get("limit", ["100"])[0])
                    self.send_json({"revenue_rules": list_revenue_rules(data_dir, status=status, limit=limit)})
                    return
                if parsed.path == "/api/report":
                    query = parse_qs(parsed.query)
                    period = query.get("period", ["week"])[0]
                    self.send_json({"report": generate_report(data_dir, period_name=period)})
                    return
                if parsed.path == "/api/external":
                    self.send_json({"external": external_connections_snapshot(data_dir)})
                    return
                if parsed.path == "/api/approvals":
                    query = parse_qs(parsed.query)
                    status = query.get("status", ["pending"])[0]
                    limit = int(query.get("limit", ["20"])[0])
                    self.send_json({"approvals": serialize_approval_actions(list_approval_actions(data_dir, status=status, limit=limit))})
                    return
                if parsed.path == "/api/leads/summary":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["60"])[0])
                    offset = int(query.get("offset", ["0"])[0])
                    self.send_json({"leads": lead_pipeline_summary(data_dir, limit=limit, offset=offset)})
                    return
                if parsed.path == "/api/leads":
                    query = parse_qs(parsed.query)
                    stage = query.get("stage", ["all"])[0]
                    limit = int(query.get("limit", ["50"])[0])
                    offset = int(query.get("offset", ["0"])[0])
                    page = list_leads_page(data_dir, stage=stage, limit=limit, offset=offset)
                    self.send_json({"leads": page["items"], "pagination": page["pagination"]})
                    return
                if parsed.path == "/api/temples":
                    self.send_json({"temples": temple_summary(data_dir), "items": list_temples(data_dir)})
                    return
                self.serve_static(parsed.path)
            except RequestPolicyError as exc:
                self.send_json({"error": str(exc)}, exc.status, extra_headers=exc.headers)
            except DivineToolError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_internal_error(exc)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                self.enforce_secure_transport(parsed.path)
                self.enforce_unsafe_origin()
                payload = self.read_json(self.request_body_limit(parsed.path))
                if parsed.path == "/api/auth/setup":
                    account = create_account(
                        data_dir,
                        username=str(payload["username"]),
                        password=str(payload["password"]),
                        display_name=str(payload.get("display_name", "")),
                        recovery_email=str(payload.get("recovery_email", "")),
                    )
                    session = create_session(
                        data_dir,
                        username=account["username"],
                        password=str(payload["password"]),
                        user_agent=self.headers.get("User-Agent", ""),
                        client_key=self.client_identity(),
                    )
                    self.send_json(
                        {
                            "ok": True,
                            "auth": auth_status(data_dir, session["token"]),
                            "state": dashboard_payload(data_dir, session["account"]),
                        },
                        extra_headers=[
                            session_cookie_header(
                                session["token"],
                                session["expires_at"],
                                secure=bool(security["cookie_secure"]),
                            )
                        ],
                    )
                    return
                if parsed.path == "/api/auth/login":
                    session = create_session(
                        data_dir,
                        username=str(payload["username"]),
                        password=str(payload["password"]),
                        user_agent=self.headers.get("User-Agent", ""),
                        client_key=self.client_identity(),
                    )
                    self.send_json(
                        {
                            "ok": True,
                            "auth": auth_status(data_dir, session["token"]),
                            "state": dashboard_payload(data_dir, session["account"]),
                        },
                        extra_headers=[
                            session_cookie_header(
                                session["token"],
                                session["expires_at"],
                                secure=bool(security["cookie_secure"]),
                            )
                        ],
                    )
                    return
                if parsed.path == "/api/auth/logout":
                    destroy_session(data_dir, self.session_token())
                    self.send_json(
                        {"ok": True, "auth": auth_status(data_dir)},
                        extra_headers=[clear_session_cookie_header(secure=bool(security["cookie_secure"]))],
                    )
                    return
                account = self.require_auth()
                if account is None:
                    return
                if parsed.path == "/api/account/profile":
                    updated_account = update_account_profile(
                        data_dir,
                        account_id=int(account["id"]),
                        display_name=str(payload.get("display_name", "")),
                        recovery_email=str(payload.get("recovery_email", "")),
                    )
                    self.send_json({"ok": True, "account": updated_account, "state": dashboard_payload(data_dir, updated_account)})
                    return
                if parsed.path == "/api/income":
                    income_id = add_income(
                        data_dir,
                        amount_minor=parse_money_to_minor(payload["amount"]),
                        currency=str(payload.get("currency", "GBP")),
                        gbp_minor=parse_money_to_minor(payload["gbp_equivalent"])
                        if payload.get("gbp_equivalent")
                        else None,
                        source=str(payload["source"]),
                        note=str(payload.get("note", "")),
                        strategy=str(payload.get("strategy", "")),
                        occurred_on=parse_date(payload["date"]) if payload.get("date") else None,
                        lead_id=int(payload["lead_id"]) if payload.get("lead_id") else None,
                    )
                    self.send_json({"ok": True, "id": income_id, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/conversions/record":
                    result = record_lead_conversion(
                        data_dir,
                        lead_id=int(payload["lead_id"]),
                        amount_minor=parse_money_to_minor(payload["amount"]),
                        currency=str(payload.get("currency", "GBP")),
                        gbp_minor=parse_money_to_minor(payload["gbp_equivalent"])
                        if payload.get("gbp_equivalent")
                        else None,
                        source=str(payload.get("source", "")),
                        note=str(payload.get("note", "")),
                        occurred_on=parse_date(payload["date"]) if payload.get("date") else None,
                    )
                    self.send_json(
                        {
                            "ok": True,
                            "income_id": result["income_id"],
                            "lead": result["lead"],
                            "conversions": result["summary"],
                            "state": dashboard_payload(data_dir, account),
                        }
                    )
                    return
                if parsed.path == "/api/conversions/link":
                    lead = link_income_to_lead(data_dir, lead_id=int(payload["lead_id"]), income_id=int(payload["income_id"]))
                    self.send_json({"ok": True, "lead": lead, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/receivables":
                    receivable_id = create_receivable(
                        data_dir,
                        client=str(payload["client"]),
                        reference=str(payload["reference"]),
                        amount_minor=parse_money_to_minor(payload["amount"]),
                        due_on=parse_date(payload["due_on"]),
                        currency=str(payload.get("currency", "GBP")),
                        gbp_minor=parse_money_to_minor(payload["gbp_equivalent"])
                        if payload.get("gbp_equivalent")
                        else None,
                        description=str(payload.get("description", "")),
                        issued_on=parse_date(payload["issued_on"]) if payload.get("issued_on") else None,
                        lead_id=int(payload["lead_id"]) if payload.get("lead_id") else None,
                        notes=str(payload.get("notes", "")),
                    )
                    self.send_json({"ok": True, "id": receivable_id, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/receivables/payment":
                    result = record_receivable_payment(
                        data_dir,
                        receivable_id=int(payload["receivable_id"]),
                        amount_minor=parse_money_to_minor(payload["amount"]),
                        currency=str(payload.get("currency", "GBP")),
                        gbp_minor=parse_money_to_minor(payload["gbp_equivalent"])
                        if payload.get("gbp_equivalent")
                        else None,
                        occurred_on=parse_date(payload["occurred_on"]) if payload.get("occurred_on") else None,
                        payment_reference=str(payload.get("payment_reference", "")),
                        note=str(payload.get("note", "")),
                        count_as_income=bool_payload(payload.get("count_as_income", False)),
                    )
                    self.send_json(
                        {
                            "ok": True,
                            "payment": result["payment"],
                            "receivable": result["receivable"],
                            "state": dashboard_payload(data_dir, account),
                        }
                    )
                    return
                if parsed.path == "/api/reconciliation/import":
                    csv_text = str(payload["csv_text"])
                    if len(csv_text.encode("utf-8")) > MAX_CSV_TEXT_BYTES:
                        raise RequestPolicyError(
                            "CSV content exceeds the 4 MiB import limit.",
                            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        )
                    result = import_reconciliation_csv(
                        data_dir,
                        csv_text=csv_text,
                        provider=str(payload.get("provider", "generic")),
                        dry_run=bool_payload(payload.get("dry_run", False)),
                        filename=str(payload.get("filename", "")),
                    )
                    self.send_json(
                        {
                            "ok": True,
                            "reconciliation_import": result,
                            "state": dashboard_payload(data_dir, account),
                        }
                    )
                    return
                if parsed.path == "/api/follow-ups/cadence":
                    cadence = update_follow_up_cadence(
                        data_dir,
                        due_soon_days=str(payload["due_soon_days"]),
                        overdue_days=str(payload["overdue_days"]),
                        minimum_gap_days=int(payload["minimum_gap_days"]),
                        max_reminders=int(payload["max_reminders"]),
                        stop_after_overdue_days=int(payload["stop_after_overdue_days"]),
                        enabled=bool_payload(payload.get("enabled", True)),
                    )
                    self.send_json(
                        {"ok": True, "cadence": cadence, "state": dashboard_payload(data_dir, account)}
                    )
                    return
                if parsed.path == "/api/follow-ups/client":
                    client_state = update_client_contact_state(
                        data_dir,
                        client=str(payload["client"]),
                        status=str(payload["status"]),
                        suppress_until=parse_date(payload["suppress_until"])
                        if payload.get("suppress_until")
                        else None,
                        reason=str(payload.get("reason", "")),
                    )
                    self.send_json(
                        {"ok": True, "client_state": client_state, "state": dashboard_payload(data_dir, account)}
                    )
                    return
                if parsed.path == "/api/follow-ups/run":
                    run = process_follow_up_cadences(
                        data_dir,
                        today=parse_date(payload["date"]) if payload.get("date") else None,
                    )
                    self.send_json({"ok": True, "run": run, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/recurring-revenue/templates":
                    template_id = create_recurring_revenue_template(
                        data_dir,
                        name=str(payload["name"]),
                        kind=str(payload["kind"]),
                        client=str(payload["client"]),
                        reference_prefix=str(payload["reference_prefix"]),
                        amount_minor=parse_money_to_minor(payload["amount"]),
                        cadence=str(payload.get("cadence", "monthly")),
                        start_on=parse_date(payload["start_on"]),
                        currency=str(payload.get("currency", "GBP")),
                        gbp_minor=parse_money_to_minor(payload["gbp_equivalent"])
                        if payload.get("gbp_equivalent")
                        else None,
                        description=str(payload.get("description", "")),
                        payment_terms_days=int(payload.get("payment_terms_days", 14)),
                        generate_ahead_days=int(payload.get("generate_ahead_days", 7)),
                        end_on=parse_date(payload["end_on"]) if payload.get("end_on") else None,
                        renewal_on=parse_date(payload["renewal_on"])
                        if payload.get("renewal_on")
                        else None,
                        renewal_notice_days=int(payload.get("renewal_notice_days", 30)),
                        total_occurrences=int(payload["total_occurrences"])
                        if payload.get("total_occurrences")
                        else None,
                        notes=str(payload.get("notes", "")),
                    )
                    self.send_json(
                        {"ok": True, "id": template_id, "state": dashboard_payload(data_dir, account)}
                    )
                    return
                if parsed.path == "/api/recurring-revenue/run":
                    run = process_recurring_revenue(
                        data_dir,
                        today=parse_date(payload["date"]) if payload.get("date") else None,
                        template_id=int(payload["template_id"]) if payload.get("template_id") else None,
                    )
                    self.send_json({"ok": True, "run": run, "state": dashboard_payload(data_dir, account)})
                    return
                recurring_parts = recurring_revenue_path_parts(parsed.path)
                if (
                    recurring_parts
                    and len(recurring_parts) == 3
                    and recurring_parts[0] == "templates"
                    and recurring_parts[2] == "status"
                ):
                    template = update_recurring_revenue_template_status(
                        data_dir,
                        template_id=int(recurring_parts[1]),
                        status=str(payload["status"]),
                    )
                    self.send_json(
                        {"ok": True, "template": template, "state": dashboard_payload(data_dir, account)}
                    )
                    return
                follow_up_parts = follow_up_path_parts(parsed.path)
                if follow_up_parts and len(follow_up_parts) == 2 and follow_up_parts[1] == "outcome":
                    result = record_follow_up_outcome(
                        data_dir,
                        event_id=int(follow_up_parts[0]),
                        outcome=str(payload["outcome"]),
                        note=str(payload.get("note", "")),
                    )
                    self.send_json(
                        {"ok": True, "event": result["event"], "state": dashboard_payload(data_dir, account)}
                    )
                    return
                reconciliation_parts = reconciliation_path_parts(parsed.path)
                if reconciliation_parts and len(reconciliation_parts) == 2 and reconciliation_parts[1] == "confirm":
                    result = confirm_reconciliation_match(
                        data_dir,
                        transaction_id=int(reconciliation_parts[0]),
                        receivable_id=int(payload["receivable_id"]),
                        count_as_income=bool_payload(payload.get("count_as_income", False)),
                        note=str(payload.get("note", "")),
                    )
                    self.send_json(
                        {
                            "ok": True,
                            "decision_id": result["decision_id"],
                            "transaction": result["transaction"],
                            "payment": result["payment"],
                            "receivable": result["receivable"],
                            "state": dashboard_payload(data_dir, account),
                        }
                    )
                    return
                if reconciliation_parts and len(reconciliation_parts) == 2 and reconciliation_parts[1] == "ignore":
                    result = ignore_reconciliation_transaction(
                        data_dir,
                        transaction_id=int(reconciliation_parts[0]),
                        reason=str(payload["reason"]),
                    )
                    self.send_json(
                        {
                            "ok": True,
                            "decision_id": result["decision_id"],
                            "transaction": result["transaction"],
                            "state": dashboard_payload(data_dir, account),
                        }
                    )
                    return
                receivable_parts = receivable_path_parts(parsed.path)
                if receivable_parts and len(receivable_parts) == 2 and receivable_parts[1] == "reminder":
                    result = queue_receivable_reminder(data_dir, int(receivable_parts[0]))
                    self.send_json(
                        {
                            "ok": True,
                            "approval_id": result["approval_id"],
                            "state": dashboard_payload(data_dir, account),
                        }
                    )
                    return
                if receivable_parts and len(receivable_parts) == 2 and receivable_parts[1] == "status":
                    receivable = update_receivable_status(
                        data_dir,
                        int(receivable_parts[0]),
                        str(payload["status"]),
                    )
                    self.send_json(
                        {"ok": True, "receivable": receivable, "state": dashboard_payload(data_dir, account)}
                    )
                    return
                if parsed.path == "/api/revenue-rules":
                    rule_id = create_revenue_rule(
                        data_dir,
                        name=str(payload["name"]),
                        rule_type=str(payload.get("rule_type", "require_approval")),
                        metric=str(payload.get("metric", "open_weighted_value")),
                        operator=str(payload.get("operator", "gte")),
                        threshold_value=payload.get("threshold", payload.get("threshold_value")),
                        action=str(payload["action"]),
                        strategy=str(payload.get("strategy", "")),
                        approval_required=bool_payload(payload.get("approval_required", True)),
                        notes=str(payload.get("notes", "")),
                    )
                    self.send_json({"ok": True, "id": rule_id, "state": dashboard_payload(data_dir, account)})
                    return
                rule_parts = revenue_rule_path_parts(parsed.path)
                if rule_parts and len(rule_parts) == 2 and rule_parts[1] == "status":
                    rule = update_revenue_rule(data_dir, int(rule_parts[0]), {"status": str(payload["status"])})
                    self.send_json({"ok": True, "rule": rule, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/quota":
                    set_quota(
                        data_dir,
                        mood_name=str(payload["mood"]),
                        amount_minor=parse_money_to_minor(payload["amount"]),
                        period=str(payload.get("period", "week")),
                    )
                    self.send_json({"ok": True, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/mood":
                    set_mood(data_dir, str(payload["mood"]))
                    self.send_json({"ok": True, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/temple/create":
                    temple = create_temple(
                        data_dir,
                        name=str(payload["name"]),
                        temple_id=str(payload.get("temple_id", "")),
                        description=str(payload.get("description", "")),
                        template=str(payload.get("template", "balanced")),
                    )
                    self.send_json({"ok": True, "temple": temple, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/temple/switch":
                    temple = switch_temple(data_dir, str(payload["temple_id"]))
                    self.send_json({"ok": True, "temple": temple, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/exception":
                    exception_id = add_exception(
                        data_dir,
                        reason=str(payload["reason"]),
                        starts_on=parse_date(payload["starts_on"]) if payload.get("starts_on") else None,
                        ends_on=parse_date(payload["until"]),
                    )
                    self.send_json({"ok": True, "id": exception_id, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/command/income":
                    command = {
                        "action": "add_income",
                        "amount": payload["amount"],
                        "currency": str(payload.get("currency", "GBP")),
                        "source": str(payload["source"]),
                        "note": str(payload.get("note", "")),
                        "strategy": str(payload.get("strategy", "")),
                    }
                    if payload.get("gbp_equivalent"):
                        command["gbp_equivalent"] = payload["gbp_equivalent"]
                    if payload.get("date"):
                        command["date"] = payload["date"]
                    if payload.get("lead_id"):
                        command["lead_id"] = payload["lead_id"]
                    enqueue_command(data_dir, command)
                    self.send_json({"ok": True, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/import/csv":
                    csv_text = str(payload["csv_text"])
                    if len(csv_text.encode("utf-8")) > MAX_CSV_TEXT_BYTES:
                        raise RequestPolicyError(
                            "CSV content exceeds the 4 MiB import limit.",
                            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        )
                    result = import_income_csv(
                        data_dir,
                        csv_text=csv_text,
                        source_type=str(payload.get("source_type", "generic")),
                        default_strategy=str(payload.get("default_strategy", "")),
                        dry_run=bool(payload.get("dry_run", False)),
                        filename=str(payload.get("filename", "")),
                    )
                    self.send_json({"ok": True, "import_result": result, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/approval/draft":
                    action_id = create_approval_draft(
                        data_dir,
                        kind=str(payload["kind"]),
                        target=str(payload.get("target", "")),
                        strategy=str(payload.get("strategy", "")),
                        amount_minor=parse_money_to_minor(payload["amount"]) if payload.get("amount") else None,
                        due_on=parse_date(payload["due"]) if payload.get("due") else None,
                        invoice=str(payload.get("invoice", "")),
                        offer=str(payload.get("offer", "")),
                        topic=str(payload.get("topic", "")),
                        goal=str(payload.get("goal", "")),
                        channel=str(payload.get("channel", "")),
                        context=str(payload.get("context", "")),
                        tone=str(payload.get("tone", "polite")),
                    )
                    self.send_json({"ok": True, "id": action_id, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/approval/review":
                    item = review_approval_action(
                        data_dir,
                        action_id=int(payload["id"]),
                        decision=str(payload["decision"]),
                        note=str(payload.get("note", "")),
                    )
                    self.send_json({"ok": True, "approval": item, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/leads":
                    lead_id = create_lead(
                        data_dir,
                        title=str(payload["title"]),
                        contact=str(payload.get("contact", "")),
                        source=str(payload.get("source", "")),
                        offer=str(payload.get("offer", "")),
                        estimated_value_minor=lead_estimated_value_minor(payload),
                        probability=parse_probability_payload(payload.get("probability", 50)),
                        stage=str(payload.get("stage", "new")),
                        strategy=str(payload.get("strategy", "")),
                        next_action=str(payload.get("next_action", "")),
                        follow_up_on=parse_date(payload["follow_up_on"]) if payload.get("follow_up_on") else None,
                        notes=str(payload.get("notes", "")),
                    )
                    self.send_json({"ok": True, "id": lead_id, "state": dashboard_payload(data_dir, account)})
                    return
                lead_parts = lead_path_parts(parsed.path)
                if lead_parts and len(lead_parts) == 2 and lead_parts[1] == "note":
                    note = add_lead_note(data_dir, int(lead_parts[0]), str(payload.get("note", "")))
                    self.send_json({"ok": True, "note": note, "state": dashboard_payload(data_dir, account)})
                    return
                if lead_parts and len(lead_parts) == 2 and lead_parts[1] == "advance":
                    lead = advance_lead(
                        data_dir,
                        int(lead_parts[0]),
                        str(payload["stage"]),
                        note=str(payload.get("note", "")),
                    )
                    self.send_json({"ok": True, "lead": lead, "state": dashboard_payload(data_dir, account)})
                    return
                if parsed.path == "/api/daemon/run-once":
                    cycle = run_worker_cycle(data_dir, trigger="browser", worker_name="browser")
                    self.send_json(
                        {
                            "ok": True,
                            "cycle": cycle,
                            "outcomes": cycle["outcome"]["commands"]["outcomes"],
                            "state": dashboard_payload(data_dir, account),
                        }
                    )
                    return
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            except RequestPolicyError as exc:
                self.send_json({"error": str(exc)}, exc.status, extra_headers=exc.headers)
            except LoginThrottledError as exc:
                self.send_json(
                    {"error": str(exc), "retry_after_seconds": exc.retry_after_seconds},
                    HTTPStatus.TOO_MANY_REQUESTS,
                    extra_headers=[f"Retry-After: {exc.retry_after_seconds}"],
                )
            except WorkerCycleBusyError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
            except AuthenticationError:
                self.send_json({"error": "Invalid username or password."}, HTTPStatus.UNAUTHORIZED)
            except KeyError as exc:
                self.send_json({"error": f"Missing required field: {exc.args[0]}"}, HTTPStatus.BAD_REQUEST)
            except DivineToolError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except json.JSONDecodeError:
                self.send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_internal_error(exc)

        def do_PATCH(self) -> None:
            parsed = urlparse(self.path)
            try:
                self.enforce_secure_transport(parsed.path)
                self.enforce_unsafe_origin()
                payload = self.read_json(self.request_body_limit(parsed.path))
                account = self.require_auth()
                if account is None:
                    return
                lead_parts = lead_path_parts(parsed.path)
                if lead_parts and len(lead_parts) == 1:
                    updates = lead_updates_from_payload(payload)
                    lead = update_lead(data_dir, int(lead_parts[0]), updates)
                    self.send_json({"ok": True, "lead": lead, "state": dashboard_payload(data_dir, account)})
                    return
                rule_parts = revenue_rule_path_parts(parsed.path)
                if rule_parts and len(rule_parts) == 1:
                    rule = update_revenue_rule(data_dir, int(rule_parts[0]), revenue_rule_updates_from_payload(payload))
                    self.send_json({"ok": True, "rule": rule, "state": dashboard_payload(data_dir, account)})
                    return
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            except RequestPolicyError as exc:
                self.send_json({"error": str(exc)}, exc.status, extra_headers=exc.headers)
            except KeyError as exc:
                self.send_json({"error": f"Missing required field: {exc.args[0]}"}, HTTPStatus.BAD_REQUEST)
            except DivineToolError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except json.JSONDecodeError:
                self.send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_internal_error(exc)

        def request_body_limit(self, path: str) -> int:
            return (
                MAX_CSV_IMPORT_BODY_BYTES
                if path in {"/api/import/csv", "/api/reconciliation/import"}
                else MAX_JSON_BODY_BYTES
            )

        def read_json(self, max_bytes: int = MAX_JSON_BODY_BYTES) -> dict[str, Any]:
            if self.headers.get("Transfer-Encoding"):
                raise RequestPolicyError(
                    "Chunked request bodies are not supported.",
                    HTTPStatus.BAD_REQUEST,
                )
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return {}
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise RequestPolicyError("Content-Length must be an integer.", HTTPStatus.BAD_REQUEST) from exc
            if length < 0:
                raise RequestPolicyError("Content-Length cannot be negative.", HTTPStatus.BAD_REQUEST)
            if length > max_bytes:
                self.close_connection = True
                size_mib = max_bytes / (1024 * 1024)
                label = f"{int(size_mib)} MiB" if size_mib >= 1 else f"{max_bytes // 1024} KiB"
                raise RequestPolicyError(
                    f"Request body exceeds the {label} limit.",
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                )
            if length == 0:
                return {}
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise RequestPolicyError("Content-Type must be application/json.", HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            body = self.rfile.read(length)
            if len(body) != length:
                raise RequestPolicyError("Request body ended before Content-Length bytes were received.", HTTPStatus.BAD_REQUEST)
            try:
                raw = body.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RequestPolicyError("Request body must use UTF-8 encoding.", HTTPStatus.BAD_REQUEST) from exc
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise DivineToolError("Request body must be a JSON object.")
            return value

        def request_scheme(self) -> str:
            if security["trust_proxy"]:
                forwarded = self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower()
                if forwarded:
                    if forwarded not in {"http", "https"}:
                        raise RequestPolicyError("Invalid forwarded transport protocol.", HTTPStatus.BAD_REQUEST)
                    return forwarded
            return "https" if isinstance(self.connection, ssl.SSLSocket) else "http"

        def direct_client_is_loopback(self) -> bool:
            try:
                return ipaddress.ip_address(str(self.client_address[0])).is_loopback
            except ValueError:
                return False

        def client_identity(self) -> str:
            direct = str(self.client_address[0])
            if not security["trust_proxy"]:
                return direct[:120]
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if not forwarded:
                return direct[:120]
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                return direct[:120]

        def enforce_secure_transport(self, path: str) -> None:
            if not security["force_https"]:
                return
            if path == "/api/health" and self.direct_client_is_loopback():
                return
            if self.request_scheme() != "https":
                raise RequestPolicyError("HTTPS is required for this deployment.", HTTPStatus.UPGRADE_REQUIRED)

        def enforce_unsafe_origin(self) -> None:
            fetch_site = self.headers.get("Sec-Fetch-Site", "").strip().lower()
            if fetch_site == "cross-site":
                raise RequestPolicyError("Cross-site requests are not permitted.", HTTPStatus.FORBIDDEN)

            supplied_origin = self.headers.get("Origin", "").strip()
            referer = self.headers.get("Referer", "").strip()
            if supplied_origin:
                candidate = supplied_origin
            elif referer:
                parsed_referer = urlparse(referer)
                candidate = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
            else:
                if security["csrf_require_origin"]:
                    raise RequestPolicyError(
                        "An approved Origin or Referer is required.",
                        HTTPStatus.FORBIDDEN,
                    )
                return

            try:
                origin = normalize_origin(candidate, name="request origin")
            except DivineToolError as exc:
                raise RequestPolicyError("Request origin is not permitted.", HTTPStatus.FORBIDDEN) from exc
            if origin in security["allowed_origins"]:
                return
            request_origin = self.loopback_request_origin()
            if request_origin and origin == request_origin:
                return
            raise RequestPolicyError("Request origin is not permitted.", HTTPStatus.FORBIDDEN)

        def loopback_request_origin(self) -> str:
            host = self.headers.get("Host", "").strip()
            if not host:
                return ""
            try:
                origin = normalize_origin(f"{self.request_scheme()}://{host}", name="request host")
                hostname = urlparse(origin).hostname or ""
                if hostname == "localhost" or ipaddress.ip_address(hostname).is_loopback:
                    return origin
            except (DivineToolError, ValueError):
                return ""
            return ""

        def request_id(self) -> str:
            current = getattr(self, "_divine_request_id", "")
            if current:
                return str(current)
            current = secrets.token_hex(8)
            self._divine_request_id = current
            return current

        def send_internal_error(self, exc: Exception) -> None:
            request_id = self.request_id()
            LOGGER.exception(
                "Unhandled request error request_id=%s method=%s path=%s client=%s",
                request_id,
                self.command,
                urlparse(self.path).path,
                self.client_identity(),
                exc_info=exc,
            )
            self.send_json(
                {"error": "Unexpected server error.", "request_id": request_id},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        def send_security_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
                "object-src 'none'; img-src 'self' data:; script-src 'self'; style-src 'self'; connect-src 'self'",
            )
            if security["force_https"]:
                self.send_header("Strict-Transport-Security", "max-age=31536000")

        def serve_static(self, path: str) -> None:
            if path == "/":
                path = "/index.html"
            if path == "/favicon.ico":
                path = "/favicon.svg"
            parts = [part for part in path.removeprefix("/").split("/") if part not in {"", ".", ".."}]
            target = (STATIC_DIR / Path(*parts)).resolve()
            root = STATIC_DIR.resolve()
            try:
                target.relative_to(root)
            except ValueError:
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            if not target.exists() or not target.is_file():
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Request-ID", self.request_id())
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(data)

        def session_token(self) -> str | None:
            raw = self.headers.get("Cookie", "")
            if not raw:
                return None
            cookie = SimpleCookie()
            cookie.load(raw)
            morsel = cookie.get(SESSION_COOKIE)
            return morsel.value if morsel else None

        def require_auth(self) -> dict[str, Any] | None:
            status = auth_status(data_dir, self.session_token())
            if not status["enabled"]:
                return {
                    "id": 0,
                    "username": "local",
                    "display_name": "Local User",
                    "role": "owner",
                    "created_at": "",
                    "last_login_at": "",
                    "disabled": False,
                }
            if status["setup_required"]:
                self.send_json({"error": "Owner account setup required.", "auth": status}, HTTPStatus.UNAUTHORIZED)
                return None
            if not status["authenticated"]:
                self.send_json({"error": "Authentication required.", "auth": status}, HTTPStatus.UNAUTHORIZED)
                return None
            return status["account"]

        def send_json(
            self,
            payload: dict[str, Any],
            status: HTTPStatus = HTTPStatus.OK,
            extra_headers: list[str] | None = None,
        ) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Request-ID", self.request_id())
            self.send_security_headers()
            for header in extra_headers or []:
                name, value = header.split(":", 1)
                self.send_header(name.strip(), value.strip())
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return DivineRequestHandler


def dashboard_payload(data_dir: Path, account: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = dashboard_snapshot(data_dir)
    config = snapshot["config"]
    active_temple = snapshot["active_temple"]
    opportunities = snapshot["opportunities"]
    return {
        "version": __version__,
        "snapshot": snapshot["snapshot"],
        "status": serialize_status(snapshot["status"]),
        "income": serialize_income(snapshot["income"]),
        "exceptions": serialize_rows(snapshot["exceptions"]),
        "events": serialize_rows(snapshot["events"]),
        "opportunities": opportunities,
        "top_opportunity": opportunities[0] if opportunities else None,
        "strategy_roi": snapshot["strategy_roi"],
        "report": dashboard_report_preview(snapshot["status"]),
        "upgrades": snapshot["upgrades"],
        "approvals": snapshot["approvals"],
        "leads": snapshot["leads"],
        "conversions": snapshot["conversions"],
        "receivables": snapshot["receivables"],
        "reconciliation": snapshot["reconciliation"],
        "follow_ups": snapshot["follow_ups"],
        "recurring_revenue": snapshot["recurring_revenue"],
        "revenue_rules": snapshot["revenue_rules"],
        "temples": snapshot["temples"],
        "auth": auth_status(data_dir) | {"account": account, "authenticated": bool(account)},
        "worker": worker_status(data_dir),
        "config": {
            "god_name": config.get("god_name", "Creator"),
            "active_mood": config.get("active_mood", "watchful"),
            "base_currency": config.get("base_currency", "GBP"),
            "active_temple": active_temple,
            "temples": snapshot["temple_items"],
            "strategy_templates": config.get("strategy_templates", {}),
            "moods": config.get("moods", {}),
            "channels": config.get("channels", []),
        },
    }


def dashboard_report_preview(status: dict[str, Any]) -> dict[str, Any]:
    period = status["period"]
    return {
        "title": "Generate a report",
        "markdown": "",
        "earned": format_money(int(status["earned_minor"])),
        "quota": format_money(int(status["quota_minor"])),
        "generated": False,
        "period": {
            "name": period.name,
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
        },
    }


def serialize_status(report: dict[str, Any]) -> dict[str, Any]:
    period = report["period"]
    return {
        "god_name": report["god_name"],
        "temple": report["temple"],
        "mood": report["mood"],
        "period": {
            "name": period.name,
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
        },
        "quota_minor": report["quota_minor"],
        "earned_minor": report["earned_minor"],
        "remaining_minor": report["remaining_minor"],
        "quota": format_money(int(report["quota_minor"])),
        "earned": format_money(int(report["earned_minor"])),
        "remaining": format_money(int(report["remaining_minor"])),
        "progress": report["progress"],
        "progress_pct": round(float(report["progress"]) * 100, 1),
        "days_left": report["days_left"],
        "judgement": report["judgement"],
        "punishment": report["punishment"],
        "exception": report["exception"],
    }


def serialize_income(rows: list[Any]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        item = row_to_dict(row)
        item["amount"] = format_money(int(item["amount_minor"]), str(item["currency"]))
        item["counted"] = format_money(int(item["gbp_minor"]))
        item["strategy"] = item.get("strategy") or ""
        output.append(item)
    return output


def serialize_rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def serialize_approval_actions(rows: list[Any]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        item = row_to_dict(row)
        try:
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        except json.JSONDecodeError:
            item["metadata"] = {}
        item["kind_label"] = item["kind"].replace("_", " ").title()
        output.append(item)
    return output


def lead_path_parts(path: str) -> list[str] | None:
    if not path.startswith("/api/leads/"):
        return None
    parts = [part for part in path.removeprefix("/api/leads/").split("/") if part]
    if not parts:
        return None
    return parts


def receivable_path_parts(path: str) -> list[str] | None:
    if not path.startswith("/api/receivables/"):
        return None
    parts = [part for part in path.removeprefix("/api/receivables/").split("/") if part]
    if not parts:
        return None
    return parts


def reconciliation_path_parts(path: str) -> list[str] | None:
    if not path.startswith("/api/reconciliation/"):
        return None
    parts = [part for part in path.removeprefix("/api/reconciliation/").split("/") if part]
    if not parts:
        return None
    return parts


def follow_up_path_parts(path: str) -> list[str] | None:
    if not path.startswith("/api/follow-ups/"):
        return None
    parts = [part for part in path.removeprefix("/api/follow-ups/").split("/") if part]
    if not parts:
        return None
    return parts


def recurring_revenue_path_parts(path: str) -> list[str] | None:
    if not path.startswith("/api/recurring-revenue/"):
        return None
    parts = [part for part in path.removeprefix("/api/recurring-revenue/").split("/") if part]
    if not parts:
        return None
    return parts


def revenue_rule_path_parts(path: str) -> list[str] | None:
    if not path.startswith("/api/revenue-rules/"):
        return None
    parts = [part for part in path.removeprefix("/api/revenue-rules/").split("/") if part]
    if not parts:
        return None
    return parts


def bool_payload(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_probability_payload(value: Any) -> float:
    if isinstance(value, str):
        cleaned = value.strip().removesuffix("%")
        if not cleaned:
            return 0.5
        return float(cleaned)
    return float(value)


def lead_estimated_value_minor(payload: dict[str, Any]) -> int:
    if "estimated_value" in payload:
        return parse_money_to_minor(payload["estimated_value"])
    if "estimated_value_minor" in payload:
        return int(payload["estimated_value_minor"])
    return 0


def lead_updates_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    passthrough = {"title", "contact", "source", "offer", "stage", "strategy", "next_action", "notes", "converted_income_id"}
    for key in passthrough:
        if key in payload:
            updates[key] = payload[key]
    if "estimated_value" in payload:
        updates["estimated_value_minor"] = parse_money_to_minor(payload["estimated_value"])
    if "estimated_value_minor" in payload:
        updates["estimated_value_minor"] = int(payload["estimated_value_minor"])
    if "probability" in payload:
        updates["probability"] = parse_probability_payload(payload["probability"])
    if "follow_up_on" in payload:
        updates["follow_up_on"] = parse_date(payload["follow_up_on"]) if payload["follow_up_on"] else ""
    return updates


def revenue_rule_updates_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    passthrough = {"name", "strategy", "rule_type", "metric", "operator", "action", "status", "notes"}
    for key in passthrough:
        if key in payload:
            updates[key] = payload[key]
    if "threshold" in payload:
        updates["threshold"] = payload["threshold"]
    if "threshold_value" in payload:
        updates["threshold_value"] = payload["threshold_value"]
    if "approval_required" in payload:
        updates["approval_required"] = bool_payload(payload["approval_required"])
    return updates
