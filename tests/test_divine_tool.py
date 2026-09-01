from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import threading
import time
import unittest
import zipfile
from contextlib import closing
from datetime import date, datetime, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from divine_tool.cli import main as cli_main
from divine_tool.core import (
    DASHBOARD_SNAPSHOT_BUDGET_MS,
    LATEST_SCHEMA_VERSION,
    SCHEMA_MIGRATIONS,
    AuthenticationError,
    LoginThrottledError,
    SchemaMigration,
    DivineToolError,
    WorkerCycleBusyError,
    add_income,
    approval_queue_summary,
    auth_status,
    advance_lead,
    create_account,
    create_approval_draft,
    create_lead,
    create_receivable,
    create_revenue_rule,
    create_session,
    create_temple,
    confirm_reconciliation_match,
    connect,
    database_status,
    destroy_session,
    enqueue_command,
    ensure_state,
    external_connections_snapshot,
    follow_up_summary,
    generate_opportunities,
    generate_report,
    import_income_csv,
    import_reconciliation_csv,
    ignore_reconciliation_transaction,
    lead_conversion_summary,
    lead_pipeline_summary,
    list_approval_actions,
    list_events,
    list_leads,
    list_leads_page,
    list_accounts,
    list_income,
    list_temples,
    list_worker_cycles,
    load_config,
    parse_money_to_minor,
    process_command_inbox,
    process_follow_up_cadences,
    record_lead_conversion,
    record_follow_up_outcome,
    record_receivable_payment,
    record_heartbeat,
    record_revenue_rule_runs,
    reset_account_password,
    revenue_rules_summary,
    run_worker_cycle,
    run_migrations,
    save_config,
    review_approval_action,
    queue_receivable_reminder,
    receivables_summary,
    reconciliation_summary,
    set_mood,
    set_quota,
    status_report,
    strategy_roi_summary,
    switch_temple,
    temple_summary,
    update_account_profile,
    update_client_contact_state,
    update_follow_up_cadence,
    update_receivable_status,
    update_revenue_rule,
    worker_status,
)
from divine_tool.deployment import (
    BACKUP_FORMAT_VERSION,
    create_backup,
    deployment_environment,
    deployment_preflight,
    restore_backup,
    run_recovery_drills,
    state_integrity,
    verify_backup,
)
from divine_tool.web import (
    MAX_CSV_IMPORT_BODY_BYTES,
    MAX_JSON_BODY_BYTES,
    dashboard_payload,
    make_handler,
)


def seed_representative_dashboard(data_dir: Path) -> None:
    ensure_state(data_dir)
    created_at = datetime.now().isoformat(timespec="seconds")
    occurred_at = date.today().isoformat()
    strategies = ("freelance_services", "digital_product", "affiliate_referral")
    stages = ("new", "contacted", "qualified", "proposal", "won", "lost")
    with closing(connect(data_dir)) as conn:
        conn.executemany(
            """
            INSERT INTO income
                (temple_id, amount_minor, currency, gbp_minor, strategy, source, note, occurred_at, created_at)
            VALUES ('main', ?, 'GBP', ?, ?, ?, '', ?, ?)
            """,
            [
                (1000 + index, 1000 + index, strategies[index % 3], f"benchmark income {index}", occurred_at, created_at)
                for index in range(180)
            ],
        )
        conn.executemany(
            """
            INSERT INTO leads
                (temple_id, title, contact, source, offer, estimated_value_minor, probability, stage, strategy,
                 next_action, follow_up_on, notes, created_at, updated_at, closed_at)
            VALUES ('main', ?, '', 'benchmark', 'offer', ?, ?, ?, ?, 'follow up', ?, '', ?, ?, ?)
            """,
            [
                (
                    f"Lead {index}",
                    5000 + index * 50,
                    0.25 + (index % 4) * 0.15,
                    stages[index % 6],
                    strategies[index % 3],
                    occurred_at if index % 5 == 0 else "",
                    created_at,
                    created_at,
                    created_at if stages[index % 6] in {"won", "lost"} else "",
                )
                for index in range(120)
            ],
        )
        conn.executemany(
            """
            INSERT INTO revenue_rules
                (temple_id, name, strategy, rule_type, metric, operator, threshold_value, action,
                 approval_required, status, notes, created_at, updated_at)
            VALUES ('main', ?, ?, 'require_approval', 'open_weighted_value', 'gte', ?, 'review', 1, 'active', '', ?, ?)
            """,
            [
                (f"Rule {index}", strategies[index % 3], 1000 + index * 100, created_at, created_at)
                for index in range(24)
            ],
        )
        conn.commit()


class DivineToolTests(unittest.TestCase):
    def test_weekly_quota_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("100"), "week")
            set_mood(data_dir, "watchful")
            add_income(
                data_dir,
                amount_minor=parse_money_to_minor("40"),
                currency="GBP",
                gbp_minor=None,
                source="test invoice",
                occurred_on=date(2026, 8, 19),
            )

            report = status_report(data_dir, today=date(2026, 8, 20))

            self.assertEqual(report["earned_minor"], 4000)
            self.assertEqual(report["remaining_minor"], 6000)
            self.assertEqual(report["judgement"], "on track")

    def test_non_gbp_requires_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DivineToolError):
                add_income(
                    Path(tmp),
                    amount_minor=parse_money_to_minor("0.01"),
                    currency="BTC",
                    gbp_minor=None,
                    source="crypto sale",
                )

    def test_command_inbox_processes_income(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("100"), "week")
            set_mood(data_dir, "watchful")
            enqueue_command(
                data_dir,
                {
                    "action": "add_income",
                    "amount": "25",
                    "currency": "GBP",
                    "source": "queued invoice",
                    "date": "2026-08-21",
                },
            )

            outcomes = process_command_inbox(data_dir)
            report = status_report(data_dir, today=date(2026, 8, 21))

            self.assertEqual(outcomes, ["added income #1"])
            self.assertEqual(report["earned_minor"], 2500)

    def test_worker_cycle_records_structured_outcomes_and_health_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            create_revenue_rule(
                data_dir,
                name="Review every open pipeline",
                rule_type="require_approval",
                metric="open_leads",
                operator="gte",
                threshold_value=0,
                action="Review the next pipeline action",
                approval_required=True,
            )
            create_approval_draft(
                data_dir,
                kind="outreach",
                target="Prospect",
                offer="Audit",
                goal="Book a call",
            )
            enqueue_command(
                data_dir,
                {"action": "set_mood", "mood": "watchful"},
            )
            enqueue_command(data_dir, {"action": "unsupported_action"})

            partial = run_worker_cycle(data_dir, trigger="test", worker_name="daemon")

            self.assertEqual(partial["status"], "partial")
            self.assertEqual(partial["commands"], {"total": 2, "succeeded": 1, "failed": 1})
            self.assertEqual(partial["rules"]["evaluated"], 1)
            self.assertEqual(partial["rules"]["triggered"], 1)
            self.assertEqual(partial["approvals"]["required"], 1)
            self.assertEqual(partial["approvals"]["pending"], 1)
            self.assertEqual(partial["failure_count"], 1)
            degraded = worker_status(data_dir)
            self.assertTrue(degraded["liveness"]["ok"])
            self.assertFalse(degraded["readiness"]["ok"])
            self.assertEqual(degraded["readiness"]["state"], "degraded")

            succeeded = run_worker_cycle(data_dir, trigger="test", worker_name="daemon")
            healthy = worker_status(data_dir)

            self.assertEqual(succeeded["status"], "succeeded")
            self.assertTrue(healthy["live"])
            self.assertTrue(healthy["ready"])
            self.assertFalse(healthy["stale"])
            self.assertEqual(healthy["health"], "healthy")
            self.assertEqual(healthy["latest_worker_cycle"]["id"], succeeded["id"])
            self.assertEqual(len(list_worker_cycles(data_dir)), 2)

    def test_daemon_cli_and_browser_share_worker_cycle_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            config = load_config(data_dir)
            config["auth"]["enabled"] = False
            config["integrations"]["currency_rates"]["enabled"] = False
            config["integrations"]["github"]["enabled"] = False
            save_config(data_dir, config)
            create_revenue_rule(
                data_dir,
                name="Observe worker parity",
                rule_type="promote",
                metric="open_leads",
                operator="gte",
                threshold_value=0,
                action="Keep the shared worker cycle",
                approval_required=False,
            )

            daemon_cycle = run_worker_cycle(data_dir, trigger="daemon", worker_name="daemon")
            cli_exit = cli_main(["--data-dir", str(data_dir), "daemon", "--once"])

            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_dir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/daemon/run-once",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request) as response:
                    browser_payload = json.loads(response.read().decode("utf-8"))
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/health") as response:
                    health_payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            cycles = list_worker_cycles(data_dir, limit=5)
            cycle_by_trigger = {cycle["trigger"]: cycle for cycle in cycles}
            self.assertEqual(cli_exit, 0)
            self.assertEqual(daemon_cycle["rules"]["evaluated"], 1)
            self.assertEqual(cycle_by_trigger["cli"]["rules"]["evaluated"], 1)
            self.assertEqual(browser_payload["cycle"]["trigger"], "browser")
            self.assertEqual(browser_payload["cycle"]["rules"]["evaluated"], 1)
            self.assertEqual(health_payload["liveness"]["state"], "live")
            self.assertEqual(health_payload["readiness"]["state"], "ready")
            self.assertTrue(health_payload["worker"]["liveness"]["ok"])
            self.assertTrue(health_payload["worker"]["readiness"]["ok"])
            self.assertEqual({cycle["trigger"] for cycle in cycles}, {"daemon", "cli", "browser"})
            self.assertEqual(len(revenue_rules_summary(data_dir)["recent_runs"]), 3)

    def test_worker_cycle_recovers_interrupted_run_and_reports_stale_liveness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ensure_state(data_dir)
            with closing(connect(data_dir)) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO worker_cycles (worker_name, trigger, status, started_at)
                    VALUES ('daemon', 'daemon', 'running', ?)
                    """,
                    (datetime.now().isoformat(timespec="seconds"),),
                )
                interrupted_id = int(cursor.lastrowid)
                conn.commit()

            with self.assertRaises(WorkerCycleBusyError):
                run_worker_cycle(data_dir, trigger="browser", worker_name="browser")

            interrupted_at = (datetime.now() - timedelta(minutes=11)).isoformat(timespec="seconds")
            with closing(connect(data_dir)) as conn:
                conn.execute(
                    "UPDATE worker_cycles SET started_at = ? WHERE id = ?",
                    (interrupted_at, interrupted_id),
                )
                conn.commit()

            recovered = run_worker_cycle(data_dir, trigger="daemon", worker_name="daemon")
            cycles = {cycle["id"]: cycle for cycle in list_worker_cycles(data_dir)}

            self.assertEqual(cycles[interrupted_id]["status"], "interrupted")
            self.assertEqual(cycles[interrupted_id]["failure_count"], 1)
            self.assertEqual(recovered["status"], "succeeded")

            stale_at = (datetime.now() - timedelta(minutes=11)).isoformat(timespec="seconds")
            with closing(connect(data_dir)) as conn:
                conn.execute(
                    "UPDATE worker_heartbeat SET last_seen_at = ? WHERE worker_name = 'daemon'",
                    (stale_at,),
                )
                conn.commit()
            stale = worker_status(data_dir)
            self.assertTrue(stale["stale"])
            self.assertFalse(stale["liveness"]["ok"])
            self.assertEqual(stale["liveness"]["state"], "stale")
            self.assertTrue(stale["readiness"]["ok"])

    def test_web_api_records_income(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("1000"), "week")
            config = load_config(data_dir)
            config["integrations"]["currency_rates"]["enabled"] = False
            config["integrations"]["github"]["enabled"] = False
            save_config(data_dir, config)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_dir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(f"{base_url}/") as response:
                    html = response.read()
                    html_text = html.decode("utf-8")
                    self.assertIn("Divine Income Engine", html_text)
                    css_match = re.search(r'href="(/assets/index-[^"]+\.css)"', html_text)
                    js_match = re.search(r'src="(/assets/index-[^"]+\.js)"', html_text)
                    self.assertIsNotNone(css_match)
                    self.assertIsNotNone(js_match)

                with urlopen(f"{base_url}{css_match.group(1)}") as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(b".temple-shell", response.read())

                with urlopen(f"{base_url}{js_match.group(1)}") as response:
                    self.assertEqual(response.status, 200)
                    js_body = response.read()
                    self.assertIn(b"Opening the temple", js_body)
                    self.assertIn(b"Lead Pipeline", js_body)
                    self.assertIn(b"Conversion Tracking", js_body)
                    self.assertIn(b"Revenue Rules", js_body)
                    self.assertIn(b"Receivables Pipeline", js_body)
                    self.assertIn(b"Collection Queue", js_body)
                    self.assertIn(b"Payment Reconciliation", js_body)
                    self.assertIn(b"Follow-Up Cadences", js_body)
                    self.assertIn(b"Reminder History", js_body)
                    self.assertIn(b"Human Review Queue", js_body)
                    self.assertIn(b"Worker Operations", js_body)
                    self.assertIn(b"Recent Worker Cycles", js_body)
                    self.assertIn(b"Restart the web server", js_body)
                    self.assertIn(b"Create Lead", js_body)
                    self.assertIn(b"Create Rule", js_body)
                    self.assertIn(b"/api/leads", js_body)
                    self.assertIn(b"/api/conversions/record", js_body)
                    self.assertIn(b"/api/revenue-rules", js_body)
                    self.assertIn(b"/api/receivables", js_body)
                    self.assertIn(b"/api/receivables/payment", js_body)
                    self.assertIn(b"/api/reconciliation/import", js_body)
                    self.assertIn(b"/api/follow-ups/cadence", js_body)
                    self.assertIn(b"/api/follow-ups/run", js_body)
                    self.assertIn(b"/api/worker/status", js_body)
                    self.assertIn(b"/api/daemon/run-once", js_body)

                try:
                    urlopen(f"{base_url}/api/status")
                    self.fail("Protected status endpoint should require authentication.")
                except HTTPError as blocked:
                    self.assertEqual(blocked.code, 401)
                    blocked.close()

                setup_body = json.dumps(
                    {
                        "username": "creator",
                        "display_name": "Creator",
                        "recovery_email": "Creator@Example.COM",
                        "password": "strong-pass-123",
                    }
                ).encode("utf-8")
                setup_request = Request(
                    f"{base_url}/api/auth/setup",
                    data=setup_body,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(setup_request) as response:
                    setup_payload = json.loads(response.read().decode("utf-8"))
                    cookie = response.headers["Set-Cookie"].split(";", 1)[0]

                self.assertTrue(setup_payload["ok"])
                self.assertTrue(setup_payload["auth"]["authenticated"])
                self.assertEqual(setup_payload["auth"]["account"]["role"], "owner")
                self.assertEqual(setup_payload["auth"]["account"]["recovery_email"], "creator@example.com")
                self.assertTrue(setup_payload["state"]["snapshot"]["within_budget"])
                self.assertFalse(setup_payload["state"]["report"]["generated"])

                json_headers = {"Content-Type": "application/json", "Cookie": cookie}
                auth_headers = {"Cookie": cookie}

                with urlopen(Request(f"{base_url}/api/worker/status", headers=auth_headers)) as response:
                    worker_payload = json.loads(response.read().decode("utf-8"))

                self.assertIn("worker", worker_payload)
                self.assertTrue(worker_payload["within_budget"])
                self.assertNotIn("status", worker_payload)
                self.assertNotIn("report", worker_payload)

                profile_body = json.dumps(
                    {"display_name": "Prime Creator", "recovery_email": "prime@example.com"}
                ).encode("utf-8")
                profile_request = Request(
                    f"{base_url}/api/account/profile",
                    data=profile_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(profile_request) as response:
                    profile_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(profile_payload["ok"])
                self.assertEqual(profile_payload["account"]["display_name"], "Prime Creator")
                self.assertEqual(profile_payload["state"]["auth"]["account"]["recovery_email"], "prime@example.com")

                body = json.dumps({"amount": "30", "source": "web invoice"}).encode("utf-8")
                request = Request(
                    f"{base_url}/api/income",
                    data=body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(request) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(payload["ok"])
                self.assertEqual(payload["state"]["status"]["earned_minor"], 3000)
                self.assertIn("strategy_roi", payload["state"])

                with urlopen(Request(f"{base_url}/api/report?period=week", headers=auth_headers)) as response:
                    report_payload = json.loads(response.read().decode("utf-8"))

                self.assertIn("report", report_payload)
                self.assertIn("markdown", report_payload["report"])
                self.assertTrue(report_payload["report"]["generated"])
                self.assertIn("Missed-Quota Review", report_payload["report"]["markdown"])

                import_body = json.dumps(
                    {
                        "csv_text": f"Date,Amount,Source,Strategy\n{date.today().isoformat()},15.00,web import,freelance_services\n",
                        "source_type": "payment",
                        "dry_run": False,
                        "filename": "web-import.csv",
                    }
                ).encode("utf-8")
                import_request = Request(
                    f"{base_url}/api/import/csv",
                    data=import_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(import_request) as response:
                    import_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(import_payload["ok"])
                self.assertEqual(import_payload["import_result"]["imported_count"], 1)
                self.assertEqual(import_payload["state"]["status"]["earned_minor"], 4500)

                with urlopen(Request(f"{base_url}/api/external", headers=auth_headers)) as response:
                    external_payload = json.loads(response.read().decode("utf-8"))

                self.assertIn("external", external_payload)
                self.assertEqual(external_payload["external"]["disabled_count"], 3)

                lead_body = json.dumps(
                    {
                        "title": "Acme Retainer",
                        "contact": "Acme Ops",
                        "source": "Referral",
                        "offer": "Monthly automation retainer",
                        "estimated_value": "750",
                        "probability": "70",
                        "strategy": "freelance_services",
                        "next_action": "Send the first proposal",
                        "follow_up_on": date.today().isoformat(),
                    }
                ).encode("utf-8")
                lead_request = Request(
                    f"{base_url}/api/leads",
                    data=lead_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(lead_request) as response:
                    lead_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(lead_payload["ok"])
                self.assertEqual(lead_payload["state"]["leads"]["open_count"], 1)
                self.assertEqual(lead_payload["state"]["leads"]["top"][0]["title"], "Acme Retainer")

                with urlopen(Request(f"{base_url}/api/leads?limit=1&offset=0", headers=auth_headers)) as response:
                    lead_page_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(len(lead_page_payload["leads"]), 1)
                self.assertEqual(lead_page_payload["pagination"]["total"], 1)
                self.assertEqual(lead_page_payload["pagination"]["returned"], 1)
                self.assertFalse(lead_page_payload["pagination"]["has_more"])

                advance_body = json.dumps({"stage": "contacted", "note": "Reached out"}).encode("utf-8")
                advance_request = Request(
                    f"{base_url}/api/leads/{lead_payload['id']}/advance",
                    data=advance_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(advance_request) as response:
                    advance_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(advance_payload["lead"]["stage"], "contacted")
                self.assertEqual(advance_payload["state"]["leads"]["counts"]["contacted"], 1)

                proposal_body = json.dumps({"stage": "proposal", "note": "Proposal accepted"}).encode("utf-8")
                proposal_request = Request(
                    f"{base_url}/api/leads/{lead_payload['id']}/advance",
                    data=proposal_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(proposal_request) as response:
                    proposal_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(proposal_payload["lead"]["stage"], "proposal")

                conversion_body = json.dumps(
                    {
                        "lead_id": lead_payload["id"],
                        "amount": "700",
                        "source": "Acme paid invoice",
                        "note": "Retainer booked",
                    }
                ).encode("utf-8")
                conversion_request = Request(
                    f"{base_url}/api/conversions/record",
                    data=conversion_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(conversion_request) as response:
                    conversion_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(conversion_payload["ok"])
                self.assertEqual(conversion_payload["lead"]["stage"], "won")
                self.assertEqual(conversion_payload["state"]["conversions"]["converted_count"], 1)
                self.assertEqual(conversion_payload["state"]["conversions"]["linked_revenue_minor"], 70000)
                self.assertEqual(conversion_payload["state"]["income"][0]["lead_id"], lead_payload["id"])

                rule_body = json.dumps(
                    {
                        "name": "Promote proven conversions",
                        "strategy": "freelance_services",
                        "rule_type": "require_approval",
                        "metric": "conversion_rate_pct",
                        "operator": "gte",
                        "threshold": "50",
                        "action": "Review the next qualified service lead",
                        "approval_required": True,
                    }
                ).encode("utf-8")
                rule_request = Request(
                    f"{base_url}/api/revenue-rules",
                    data=rule_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(rule_request) as response:
                    rule_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(rule_payload["ok"])
                self.assertEqual(rule_payload["state"]["revenue_rules"]["active_count"], 1)
                self.assertEqual(rule_payload["state"]["revenue_rules"]["triggered_count"], 1)
                self.assertEqual(rule_payload["state"]["revenue_rules"]["approval_required_count"], 1)

                pause_body = json.dumps({"status": "paused"}).encode("utf-8")
                pause_request = Request(
                    f"{base_url}/api/revenue-rules/{rule_payload['id']}/status",
                    data=pause_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(pause_request) as response:
                    pause_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(pause_payload["rule"]["status"], "paused")
                self.assertEqual(pause_payload["state"]["revenue_rules"]["triggered_count"], 0)

                draft_body = json.dumps(
                    {
                        "kind": "outreach",
                        "target": "Acme Lead",
                        "offer": "a fast revenue dashboard",
                        "context": "their manual reporting is slow",
                        "strategy": "freelance_services",
                    }
                ).encode("utf-8")
                draft_request = Request(
                    f"{base_url}/api/approval/draft",
                    data=draft_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(draft_request) as response:
                    draft_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(draft_payload["ok"])
                self.assertEqual(draft_payload["state"]["approvals"]["counts"]["pending"], 1)

                review_body = json.dumps({"id": draft_payload["id"], "decision": "approve"}).encode("utf-8")
                review_request = Request(
                    f"{base_url}/api/approval/review",
                    data=review_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(review_request) as response:
                    review_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(review_payload["approval"]["status"], "approved")
                self.assertEqual(review_payload["state"]["approvals"]["counts"]["approved"], 1)

                receivable_body = json.dumps(
                    {
                        "client": "Acme Ops",
                        "reference": "INV-ACME-001",
                        "amount": "700",
                        "issued_on": date.today().isoformat(),
                        "due_on": (date.today() + timedelta(days=7)).isoformat(),
                        "lead_id": lead_payload["id"],
                        "description": "Booked retainer collection",
                    }
                ).encode("utf-8")
                receivable_request = Request(
                    f"{base_url}/api/receivables",
                    data=receivable_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(receivable_request) as response:
                    receivable_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(receivable_payload["ok"])
                self.assertEqual(receivable_payload["state"]["receivables"]["outstanding_minor"], 70000)
                self.assertTrue(receivable_payload["state"]["receivables"]["rows"][0]["already_counted"])

                reminder_request = Request(
                    f"{base_url}/api/receivables/{receivable_payload['id']}/reminder",
                    data=b"{}",
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(reminder_request) as response:
                    reminder_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(reminder_payload["ok"])
                self.assertEqual(reminder_payload["state"]["approvals"]["counts"]["pending"], 1)

                payment_body = json.dumps(
                    {
                        "receivable_id": receivable_payload["id"],
                        "amount": "700",
                        "payment_reference": "PAY-ACME-001",
                    }
                ).encode("utf-8")
                payment_request = Request(
                    f"{base_url}/api/receivables/payment",
                    data=payment_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(payment_request) as response:
                    payment_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(payment_payload["receivable"]["state"], "paid")
                self.assertEqual(payment_payload["state"]["receivables"]["outstanding_minor"], 0)
                self.assertEqual(payment_payload["state"]["status"]["earned_minor"], 74500)

                with urlopen(Request(f"{base_url}/api/receivables", headers=auth_headers)) as response:
                    receivables_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(receivables_payload["receivables"]["paid_count"], 1)
                self.assertEqual(receivables_payload["receivables"]["collected_minor"], 70000)

                temple_body = json.dumps(
                    {
                        "name": "Product Temple",
                        "template": "products",
                        "description": "Digital products and affiliate revenue",
                    }
                ).encode("utf-8")
                temple_request = Request(
                    f"{base_url}/api/temple/create",
                    data=temple_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(temple_request) as response:
                    temple_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(temple_payload["temple"]["id"], "product_temple")
                self.assertEqual(temple_payload["state"]["temples"]["temple_count"], 2)

                switch_body = json.dumps({"temple_id": "product_temple"}).encode("utf-8")
                switch_request = Request(
                    f"{base_url}/api/temple/switch",
                    data=switch_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(switch_request) as response:
                    switch_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(switch_payload["state"]["status"]["temple"]["id"], "product_temple")

                side_income_body = json.dumps(
                    {"amount": "10", "source": "product sale", "strategy": "digital_product"}
                ).encode("utf-8")
                side_income_request = Request(
                    f"{base_url}/api/income",
                    data=side_income_body,
                    method="POST",
                    headers=json_headers,
                )
                with urlopen(side_income_request) as response:
                    side_income_payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(side_income_payload["state"]["status"]["earned_minor"], 1000)
                self.assertEqual(side_income_payload["state"]["temples"]["total_earned_minor"], 75500)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_reconciliation_web_api_imports_and_confirms_with_authentication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            create_account(data_dir, "creator", "strong-pass-123")
            session = create_session(data_dir, "creator", "strong-pass-123")
            receivable_id = create_receivable(
                data_dir,
                client="API Buyer",
                reference="INV-API-RECON-001",
                amount_minor=parse_money_to_minor("80"),
                due_on=date.today() + timedelta(days=7),
                issued_on=date.today(),
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_dir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            json_headers = {
                "Content-Type": "application/json",
                "Cookie": f"divine_session={session['token']}",
            }
            auth_headers = {"Cookie": f"divine_session={session['token']}"}
            try:
                import_body = json.dumps(
                    {
                        "csv_text": (
                            "Date,Amount,Currency,Reference,Payer,Description\n"
                            f"{date.today().isoformat()},80.00,GBP,API-PAY-001,API Buyer,INV-API-RECON-001\n"
                        ),
                        "provider": "bank",
                        "filename": "api-bank.csv",
                        "dry_run": False,
                    }
                ).encode("utf-8")
                with urlopen(
                    Request(
                        f"{base_url}/api/reconciliation/import",
                        data=import_body,
                        method="POST",
                        headers=json_headers,
                    )
                ) as response:
                    imported = json.loads(response.read().decode("utf-8"))

                self.assertTrue(imported["ok"])
                self.assertEqual(imported["reconciliation_import"]["imported_count"], 1)
                self.assertEqual(imported["state"]["reconciliation"]["suggested_count"], 1)
                transaction_id = imported["state"]["reconciliation"]["rows"][0]["id"]

                confirm_body = json.dumps(
                    {"receivable_id": receivable_id, "count_as_income": True, "note": "API human confirmation"}
                ).encode("utf-8")
                with urlopen(
                    Request(
                        f"{base_url}/api/reconciliation/{transaction_id}/confirm",
                        data=confirm_body,
                        method="POST",
                        headers=json_headers,
                    )
                ) as response:
                    confirmed = json.loads(response.read().decode("utf-8"))

                self.assertTrue(confirmed["ok"])
                self.assertEqual(confirmed["transaction"]["status"], "matched")
                self.assertEqual(confirmed["transaction"]["income_treatment"], "counted")
                self.assertEqual(confirmed["receivable"]["state"], "paid")
                self.assertTrue(confirmed["payment"]["counted_as_income"])

                with urlopen(Request(f"{base_url}/api/reconciliation", headers=auth_headers)) as response:
                    summary = json.loads(response.read().decode("utf-8"))["reconciliation"]
                self.assertEqual(summary["matched_count"], 1)
                self.assertEqual(summary["review_count"], 0)
                self.assertEqual(summary["recent_decisions"][0]["action"], "confirmed")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_follow_up_web_api_requires_auth_and_preserves_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            create_account(data_dir, "creator", "strong-pass-123")
            session = create_session(data_dir, "creator", "strong-pass-123")
            create_receivable(
                data_dir,
                client="API Cadence Client",
                reference="INV-API-CADENCE-001",
                amount_minor=parse_money_to_minor("90"),
                due_on=date.today(),
                issued_on=date.today() - timedelta(days=7),
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_dir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            headers = {
                "Content-Type": "application/json",
                "Cookie": f"divine_session={session['token']}",
            }

            def post(path: str, payload: dict[str, object]) -> dict[str, object]:
                request = Request(
                    f"{base_url}{path}",
                    data=json.dumps(payload).encode("utf-8"),
                    method="POST",
                    headers=headers,
                )
                with urlopen(request) as response:
                    return json.loads(response.read().decode("utf-8"))

            try:
                with self.assertRaises(HTTPError) as unauthenticated:
                    urlopen(f"{base_url}/api/follow-ups")
                self.assertEqual(unauthenticated.exception.code, 401)
                unauthenticated.exception.close()

                configured = post(
                    "/api/follow-ups/cadence",
                    {
                        "due_soon_days": "3,0",
                        "overdue_days": "3,7,14",
                        "minimum_gap_days": 2,
                        "max_reminders": 5,
                        "stop_after_overdue_days": 45,
                        "enabled": True,
                    },
                )
                self.assertTrue(configured["ok"])
                self.assertEqual(configured["cadence"]["max_reminders"], 5)

                post(
                    "/api/follow-ups/client",
                    {"client": "API Cadence Client", "status": "paused", "reason": "Awaiting account check"},
                )
                suppressed = post("/api/follow-ups/run", {})
                self.assertEqual(suppressed["run"]["drafted"], 0)
                self.assertEqual(suppressed["run"]["suppressed"], 1)

                post("/api/follow-ups/client", {"client": "API Cadence Client", "status": "active"})
                drafted = post("/api/follow-ups/run", {})
                self.assertEqual(drafted["run"]["drafted"], 1)
                event = drafted["state"]["follow_ups"]["recent"][0]
                approval_id = int(event["approval_id"])
                self.assertEqual(event["status"], "drafted")

                post("/api/approval/review", {"id": approval_id, "decision": "approve"})
                completed = post("/api/approval/review", {"id": approval_id, "decision": "complete"})
                self.assertEqual(completed["approval"]["status"], "completed")
                outcome = post(
                    f"/api/follow-ups/{event['id']}/outcome",
                    {"outcome": "no_response", "note": "No reply after manual dispatch"},
                )
                self.assertEqual(outcome["event"]["outcome"], "no_response")

                with urlopen(
                    Request(
                        f"{base_url}/api/follow-ups",
                        headers={"Cookie": f"divine_session={session['token']}"},
                    )
                ) as response:
                    summary = json.loads(response.read().decode("utf-8"))["follow_ups"]
                self.assertEqual(summary["metrics"]["no_response_count"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_api_request_body_limits_reject_oversized_json_and_csv_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ensure_state(data_dir)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_dir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for path, limit in (
                    ("/api/auth/login", MAX_JSON_BODY_BYTES),
                    ("/api/import/csv", MAX_CSV_IMPORT_BODY_BYTES),
                    ("/api/reconciliation/import", MAX_CSV_IMPORT_BODY_BYTES),
                ):
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                    try:
                        connection.putrequest("POST", path)
                        connection.putheader("Content-Type", "application/json")
                        connection.putheader("Content-Length", str(limit + 1))
                        connection.endheaders()
                        response = connection.getresponse()
                        payload = json.loads(response.read().decode("utf-8"))
                    finally:
                        connection.close()
                    self.assertEqual(response.status, 413)
                    self.assertIn("limit", payload["error"])

                wrong_type = Request(
                    f"http://127.0.0.1:{server.server_port}/api/auth/login",
                    data=b"username=creator",
                    method="POST",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with self.assertRaises(HTTPError) as unsupported:
                    urlopen(wrong_type)
                self.assertEqual(unsupported.exception.code, 415)
                unsupported.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_login_throttling_persists_failures_and_records_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            create_account(data_dir, "creator", "strong-pass-123")
            config = load_config(data_dir)
            config["auth"]["login_max_attempts"] = 3
            config["auth"]["login_attempt_window_seconds"] = 600
            config["auth"]["login_lockout_seconds"] = 600
            save_config(data_dir, config)

            for _ in range(2):
                with self.assertRaises(AuthenticationError):
                    create_session(
                        data_dir,
                        "creator",
                        "wrong-pass",
                        client_key="203.0.113.10",
                    )
            with self.assertRaises(LoginThrottledError) as throttled:
                create_session(
                    data_dir,
                    "creator",
                    "wrong-pass",
                    client_key="203.0.113.10",
                )
            self.assertGreater(throttled.exception.retry_after_seconds, 0)
            with self.assertRaises(LoginThrottledError):
                create_session(
                    data_dir,
                    "creator",
                    "strong-pass-123",
                    client_key="203.0.113.10",
                )

            with closing(connect(data_dir)) as conn:
                attempt_count = int(conn.execute("SELECT COUNT(*) FROM auth_login_attempts").fetchone()[0])
            self.assertEqual(attempt_count, 3)
            auth_events = [row for row in list_events(data_dir, limit=20) if row["category"] == "auth"]
            messages = [str(row["message"]) for row in auth_events]
            self.assertEqual(sum(message.startswith("Failed sign-in") for message in messages), 3)
            self.assertTrue(any(message.startswith("Throttled sign-in") for message in messages))
            self.assertFalse(any("wrong-pass" in message for message in messages))

            reset_account_password(data_dir, "creator", "better-pass-456")
            session = create_session(
                data_dir,
                "creator",
                "better-pass-456",
                client_key="203.0.113.10",
            )
            self.assertTrue(session["token"])

    def test_hosted_policy_enforces_https_origin_proxy_and_secure_cookie_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            create_account(data_dir, "creator", "strong-pass-123")
            config = load_config(data_dir)
            config["auth"]["login_max_attempts"] = 1
            save_config(data_dir, config)
            environ = {
                "DIVINE_DEPLOYMENT_MODE": "production",
                "DIVINE_PUBLIC_URL": "https://divine.example",
                "DIVINE_ALLOWED_ORIGINS": "https://divine.example",
                "DIVINE_COOKIE_SECURE": "true",
                "DIVINE_CSRF_REQUIRE_ORIGIN": "true",
                "DIVINE_TRUST_PROXY": "true",
                "DIVINE_FORCE_HTTPS": "true",
            }
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_dir, environ=environ))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            login_body = json.dumps({"username": "creator", "password": "strong-pass-123"}).encode("utf-8")
            try:
                with urlopen(f"{base_url}/api/health") as response:
                    health = json.loads(response.read().decode("utf-8"))
                self.assertTrue(health["deployment"]["force_https"])
                self.assertTrue(health["deployment"]["csrf_require_origin"])

                insecure = Request(
                    f"{base_url}/api/auth/login",
                    data=login_body,
                    method="POST",
                    headers={"Content-Type": "application/json", "Origin": "https://divine.example"},
                )
                with self.assertRaises(HTTPError) as insecure_error:
                    urlopen(insecure)
                self.assertEqual(insecure_error.exception.code, 426)
                insecure_error.exception.close()

                missing_origin = Request(
                    f"{base_url}/api/auth/login",
                    data=login_body,
                    method="POST",
                    headers={"Content-Type": "application/json", "X-Forwarded-Proto": "https"},
                )
                with self.assertRaises(HTTPError) as missing_origin_error:
                    urlopen(missing_origin)
                self.assertEqual(missing_origin_error.exception.code, 403)
                missing_origin_error.exception.close()

                wrong_origin = Request(
                    f"{base_url}/api/auth/login",
                    data=login_body,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Forwarded-Proto": "https",
                        "Origin": "https://attacker.example",
                    },
                )
                with self.assertRaises(HTTPError) as wrong_origin_error:
                    urlopen(wrong_origin)
                self.assertEqual(wrong_origin_error.exception.code, 403)
                wrong_origin_error.exception.close()

                valid_login = Request(
                    f"{base_url}/api/auth/login",
                    data=login_body,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Forwarded-Proto": "https",
                        "X-Forwarded-For": "203.0.113.20",
                        "Origin": "https://divine.example",
                    },
                )
                with urlopen(valid_login) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    cookie = response.headers["Set-Cookie"]
                    hsts = response.headers["Strict-Transport-Security"]
                self.assertTrue(payload["ok"])
                self.assertIn("HttpOnly", cookie)
                self.assertIn("SameSite=Strict", cookie)
                self.assertIn("Secure", cookie)
                self.assertIn("max-age=31536000", hsts)

                wrong_password = Request(
                    f"{base_url}/api/auth/login",
                    data=json.dumps({"username": "creator", "password": "wrong-pass"}).encode("utf-8"),
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Forwarded-Proto": "https",
                        "X-Forwarded-For": "203.0.113.21",
                        "Origin": "https://divine.example",
                    },
                )
                with self.assertRaises(HTTPError) as wrong_password_error:
                    urlopen(wrong_password)
                self.assertEqual(wrong_password_error.exception.code, 429)
                self.assertGreater(int(wrong_password_error.exception.headers["Retry-After"]), 0)
                wrong_password_error.exception.close()
                self.assertTrue(
                    any(
                        "203.0.113.21" in str(row["message"])
                        for row in list_events(data_dir, limit=20)
                        if row["category"] == "auth"
                    )
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_unexpected_api_errors_are_redacted_and_correlated_with_internal_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            create_account(data_dir, "creator", "strong-pass-123")
            session = create_session(data_dir, "creator", "strong-pass-123")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_dir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            request = Request(
                f"http://127.0.0.1:{server.server_port}/api/status",
                headers={"Cookie": f"divine_session={session['token']}"},
            )
            try:
                with (
                    patch("divine_tool.web.dashboard_payload", side_effect=RuntimeError("private-database-detail")),
                    self.assertLogs("divine_tool.web", level="ERROR") as captured,
                    self.assertRaises(HTTPError) as failed,
                ):
                    urlopen(request)
                payload = json.loads(failed.exception.read().decode("utf-8"))
                request_id = failed.exception.headers["X-Request-ID"]
                failed.exception.close()
                self.assertEqual(failed.exception.code, 500)
                self.assertEqual(payload["error"], "Unexpected server error.")
                self.assertEqual(payload["request_id"], request_id)
                self.assertNotIn("private-database-detail", json.dumps(payload))
                self.assertTrue(any("private-database-detail" in entry for entry in captured.output))
                self.assertTrue(any(request_id in entry for entry in captured.output))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_dashboard_snapshot_reuses_request_scoped_summaries_and_defers_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            with (
                patch("divine_tool.core.status_report", wraps=status_report) as status_spy,
                patch("divine_tool.core.generate_opportunities", wraps=generate_opportunities) as opportunities_spy,
                patch("divine_tool.web.generate_report", side_effect=AssertionError("dashboard generated a full report")),
            ):
                payload = dashboard_payload(data_dir)

            self.assertEqual(status_spy.call_count, 1)
            self.assertEqual(opportunities_spy.call_count, 1)
            self.assertFalse(payload["report"]["generated"])
            self.assertEqual(payload["report"]["markdown"], "")
            self.assertEqual(payload["leads"]["total_count"], payload["conversions"]["total_leads"])
            self.assertTrue(payload["snapshot"]["within_budget"])

    def test_representative_dashboard_snapshot_meets_response_time_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            seed_representative_dashboard(data_dir)
            elapsed_samples = []
            snapshots = []

            for _ in range(5):
                started = time.perf_counter()
                payload = dashboard_payload(data_dir)
                elapsed_samples.append((time.perf_counter() - started) * 1000)
                snapshots.append(payload["snapshot"])

            median_ms = sorted(elapsed_samples)[len(elapsed_samples) // 2]
            self.assertEqual(payload["leads"]["total_count"], 120)
            self.assertEqual(payload["revenue_rules"]["total_count"], 24)
            self.assertLessEqual(median_ms, DASHBOARD_SNAPSHOT_BUDGET_MS)
            self.assertTrue(all(snapshot["within_budget"] for snapshot in snapshots))

    def test_opportunity_scoring_uses_strategy_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("100"), "week")
            set_mood(data_dir, "watchful")
            add_income(
                data_dir,
                amount_minor=parse_money_to_minor("90"),
                currency="GBP",
                gbp_minor=None,
                source="mini product sale",
                note="evidence for product channel",
                strategy="digital_product",
                occurred_on=date(2026, 8, 19),
            )

            opportunities = generate_opportunities(data_dir, today=date(2026, 8, 20))

            self.assertEqual(opportunities[0]["id"], "digital_product")
            self.assertEqual(opportunities[0]["period_income_minor"], 9000)
            self.assertGreater(opportunities[0]["components"]["evidence"], 0)

    def test_lead_pipeline_scores_and_advances_leads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("1000"), "week")
            set_mood(data_dir, "watchful")

            lead_id = create_lead(
                data_dir,
                title="Retainer Prospect",
                contact="Prospect Ltd",
                source="Warm referral",
                offer="Revenue operations retainer",
                estimated_value_minor=parse_money_to_minor("900"),
                probability=0.8,
                strategy="freelance_services",
                next_action="Send scoped proposal",
                follow_up_on=date.today(),
            )

            summary = lead_pipeline_summary(data_dir)

            self.assertEqual(summary["open_count"], 1)
            self.assertEqual(summary["top"][0]["id"], lead_id)
            self.assertEqual(summary["due_count"], 1)
            self.assertGreater(summary["top"][0]["priority_score"], 50)

            contacted = advance_lead(data_dir, lead_id, "contacted", "First message sent")
            self.assertEqual(contacted["stage"], "contacted")
            self.assertEqual(list_leads(data_dir, stage="contacted")[0]["id"], lead_id)

            won = advance_lead(data_dir, lead_id, "won")
            self.assertEqual(won["stage"], "won")
            closed_summary = lead_pipeline_summary(data_dir)
            self.assertEqual(closed_summary["open_count"], 0)
            self.assertEqual(closed_summary["counts"]["won"], 1)

    def test_lead_aggregates_and_rules_are_not_capped_by_page_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("5000"), "week")
            set_mood(data_dir, "watchful")

            for index in range(205):
                create_lead(
                    data_dir,
                    title=f"Scale Prospect {index + 1}",
                    contact="Pipeline Buyer",
                    source="Regression fixture",
                    offer="Revenue operations package",
                    estimated_value_minor=parse_money_to_minor("10"),
                    probability=0.5,
                    stage="proposal",
                    strategy="freelance_services",
                    next_action="Review the proposal",
                    follow_up_on=date.today(),
                )

            summary = lead_pipeline_summary(data_dir)
            middle_page = list_leads_page(data_dir, limit=60, offset=60)
            final_page = list_leads_page(data_dir, limit=60, offset=200)

            self.assertEqual(summary["total_count"], 205)
            self.assertEqual(summary["open_count"], 205)
            self.assertEqual(summary["counts"]["proposal"], 205)
            self.assertEqual(summary["due_count"], 205)
            self.assertEqual(summary["weighted_value_minor"], 102500)
            self.assertEqual(len(summary["rows"]), 60)
            self.assertEqual(summary["pagination"]["total"], 205)
            self.assertTrue(summary["pagination"]["has_more"])
            self.assertEqual(summary["pagination"]["next_offset"], 60)
            self.assertEqual(summary["strategy_metrics"]["freelance_services"]["open_count"], 205)
            self.assertEqual(middle_page["pagination"]["offset"], 60)
            self.assertEqual(len(middle_page["items"]), 60)
            self.assertEqual(final_page["pagination"]["offset"], 200)
            self.assertEqual(len(final_page["items"]), 5)
            self.assertFalse(final_page["pagination"]["has_more"])

            rule_id = create_revenue_rule(
                data_dir,
                name="Recognise the full service pipeline",
                rule_type="promote",
                metric="open_leads",
                operator="gte",
                threshold_value="205",
                action="Prioritise the complete service pipeline",
                strategy="freelance_services",
                approval_required=False,
            )
            for index in range(64):
                create_revenue_rule(
                    data_dir,
                    name=f"Scale pipeline rule {index + 2}",
                    rule_type="promote",
                    metric="open_leads",
                    operator="gte",
                    threshold_value="205",
                    action="Prioritise the complete service pipeline",
                    strategy="freelance_services",
                    approval_required=False,
                )
            rule_summary = revenue_rules_summary(data_dir)
            evaluated_rule = next(rule for rule in rule_summary["rows"] if rule["id"] == rule_id)

            self.assertEqual(rule_summary["total_count"], 65)
            self.assertEqual(rule_summary["triggered_count"], 65)
            self.assertEqual(len(rule_summary["rows"]), 65)
            self.assertEqual(evaluated_rule["evaluation"]["metric_value"], 205.0)
            self.assertTrue(evaluated_rule["evaluation"]["triggered"])

    def test_lead_conversion_links_income_and_reports_rates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("1000"), "week")
            set_mood(data_dir, "watchful")

            lead_id = create_lead(
                data_dir,
                title="Conversion Prospect",
                contact="Buyer Ltd",
                source="Referral",
                offer="Automation project",
                estimated_value_minor=parse_money_to_minor("900"),
                probability=0.75,
                stage="proposal",
                strategy="freelance_services",
                next_action="Send invoice",
                follow_up_on=date.today(),
            )
            lost_id = create_lead(
                data_dir,
                title="Lost Prospect",
                contact="Old Buyer Ltd",
                source="Marketplace",
                offer="Audit sprint",
                estimated_value_minor=parse_money_to_minor("300"),
                probability=0.25,
                stage="lost",
                strategy="freelance_services",
                next_action="Review reason",
                notes="Price mismatch",
            )

            result = record_lead_conversion(
                data_dir,
                lead_id=lead_id,
                amount_minor=parse_money_to_minor("850"),
                currency="GBP",
                gbp_minor=None,
                source="Paid invoice",
                note="Converted through proposal follow-up",
                occurred_on=date(2026, 8, 20),
            )
            rows = list_income(data_dir)
            summary = lead_conversion_summary(data_dir)
            report = generate_report(data_dir, period_name="week", today=date(2026, 8, 20))

            self.assertEqual(result["lead"]["stage"], "won")
            self.assertEqual(rows[0]["lead_id"], lead_id)
            self.assertEqual(rows[0]["strategy"], "freelance_services")
            self.assertEqual(summary["converted_count"], 1)
            self.assertEqual(summary["lost_count"], 1)
            self.assertEqual(summary["linked_revenue_minor"], 85000)
            self.assertEqual(summary["lost_value_minor"], 30000)
            self.assertEqual(summary["by_strategy"][0]["conversion_rate_pct"], 50.0)
            self.assertEqual(summary["lost_notes"][0]["id"], lost_id)
            self.assertIn("## Lead Conversion Tracking", report["markdown"])
            self.assertIn("Booked conversions: 1 of 2 leads", report["markdown"])

            with self.assertRaises(DivineToolError):
                record_lead_conversion(
                    data_dir,
                    lead_id=lead_id,
                    amount_minor=parse_money_to_minor("25"),
                    currency="GBP",
                    gbp_minor=None,
                    source="duplicate invoice",
                )

    def test_receivables_collect_without_double_counting_booked_income(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            standalone_id = create_receivable(
                data_dir,
                client="Independent Buyer",
                reference="INV-STANDALONE-001",
                amount_minor=parse_money_to_minor("1000"),
                due_on=date(2026, 8, 15),
                issued_on=date(2026, 8, 1),
                description="Standalone consulting invoice",
            )

            initial = receivables_summary(data_dir, today=date(2026, 8, 20))
            self.assertEqual(initial["overdue_count"], 1)
            self.assertEqual(initial["outstanding_minor"], 100000)

            reminder = queue_receivable_reminder(data_dir, standalone_id)
            approval = next(item for item in approval_queue_summary(data_dir)["recent"] if item["id"] == reminder["approval_id"])
            self.assertEqual(approval["receivable_id"], standalone_id)
            with self.assertRaises(DivineToolError):
                queue_receivable_reminder(data_dir, standalone_id)

            partial = record_receivable_payment(
                data_dir,
                standalone_id,
                amount_minor=parse_money_to_minor("250"),
                payment_reference="PAY-STANDALONE-001",
                occurred_on=date(2026, 8, 20),
                count_as_income=True,
            )
            self.assertEqual(partial["receivable"]["state"], "overdue")
            self.assertEqual(partial["receivable"]["outstanding_gbp_minor"], 75000)
            self.assertTrue(partial["payment"]["counted_as_income"])
            self.assertEqual(list_income(data_dir)[0]["receivable_id"], standalone_id)
            with self.assertRaises(DivineToolError):
                record_receivable_payment(
                    data_dir,
                    standalone_id,
                    amount_minor=parse_money_to_minor("800"),
                )

            lead_id = create_lead(
                data_dir,
                title="Booked Buyer",
                contact="Buyer Ltd",
                source="Referral",
                offer="Automation project",
                estimated_value_minor=parse_money_to_minor("700"),
                probability=0.8,
                stage="proposal",
                strategy="freelance_services",
                next_action="Collect invoice",
            )
            conversion = record_lead_conversion(
                data_dir,
                lead_id=lead_id,
                amount_minor=parse_money_to_minor("700"),
                currency="GBP",
                gbp_minor=None,
                source="Booked contract",
                occurred_on=date(2026, 8, 20),
            )
            linked_id = create_receivable(
                data_dir,
                client="Buyer Ltd",
                reference="INV-BOOKED-001",
                amount_minor=parse_money_to_minor("700"),
                due_on=date(2026, 8, 27),
                issued_on=date(2026, 8, 20),
                lead_id=lead_id,
            )
            linked = next(item for item in receivables_summary(data_dir, today=date(2026, 8, 20))["rows"] if item["id"] == linked_id)
            self.assertEqual(linked["source_income_id"], conversion["income_id"])
            self.assertTrue(linked["already_counted"])
            with self.assertRaises(DivineToolError):
                record_receivable_payment(
                    data_dir,
                    linked_id,
                    amount_minor=parse_money_to_minor("700"),
                    count_as_income=True,
                )

            linked_payment = record_receivable_payment(
                data_dir,
                linked_id,
                amount_minor=parse_money_to_minor("700"),
                payment_reference="PAY-BOOKED-001",
            )
            self.assertEqual(linked_payment["receivable"]["state"], "paid")
            self.assertFalse(linked_payment["payment"]["counted_as_income"])
            self.assertEqual(len(list_income(data_dir)), 2)

            report = generate_report(data_dir, period_name="week", today=date(2026, 8, 20))
            self.assertIn("## Receivables", report["markdown"])
            self.assertEqual(report["receivables"]["total_count"], 2)

            with self.assertRaises(DivineToolError):
                update_receivable_status(data_dir, standalone_id, "void")

    def test_concurrent_receivable_payments_and_reminders_preserve_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            receivable_id = create_receivable(
                data_dir,
                client="Concurrent Buyer",
                reference="INV-CONCURRENT-001",
                amount_minor=parse_money_to_minor("100"),
                due_on=date.today() + timedelta(days=7),
            )
            barrier = threading.Barrier(2)
            payment_outcomes: list[str] = []

            def pay(reference: str) -> None:
                barrier.wait()
                try:
                    record_receivable_payment(
                        data_dir,
                        receivable_id,
                        amount_minor=parse_money_to_minor("75"),
                        payment_reference=reference,
                    )
                    payment_outcomes.append("recorded")
                except DivineToolError:
                    payment_outcomes.append("blocked")

            payment_threads = [
                threading.Thread(target=pay, args=("PAY-CONCURRENT-A",)),
                threading.Thread(target=pay, args=("PAY-CONCURRENT-B",)),
            ]
            for thread in payment_threads:
                thread.start()
            for thread in payment_threads:
                thread.join(timeout=5)

            summary = receivables_summary(data_dir)
            self.assertCountEqual(payment_outcomes, ["recorded", "blocked"])
            self.assertEqual(summary["collected_minor"], 7500)
            self.assertEqual(summary["outstanding_minor"], 2500)
            self.assertEqual(len(summary["recent_payments"]), 1)

            reminder_barrier = threading.Barrier(2)
            reminder_outcomes: list[str] = []

            def remind() -> None:
                reminder_barrier.wait()
                try:
                    queue_receivable_reminder(data_dir, receivable_id)
                    reminder_outcomes.append("queued")
                except DivineToolError:
                    reminder_outcomes.append("blocked")

            reminder_threads = [threading.Thread(target=remind), threading.Thread(target=remind)]
            for thread in reminder_threads:
                thread.start()
            for thread in reminder_threads:
                thread.join(timeout=5)

            approvals = approval_queue_summary(data_dir)
            self.assertCountEqual(reminder_outcomes, ["queued", "blocked"])
            self.assertEqual(approvals["counts"]["pending"], 1)

    def test_follow_up_cadence_is_idempotent_and_honors_client_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            today = date(2026, 9, 1)
            active_id = create_receivable(
                data_dir,
                client="Cadence Client",
                reference="INV-CADENCE-001",
                amount_minor=parse_money_to_minor("500"),
                due_on=today - timedelta(days=3),
                issued_on=today - timedelta(days=14),
            )
            suppressed_id = create_receivable(
                data_dir,
                client="Protected Client",
                reference="INV-CADENCE-002",
                amount_minor=parse_money_to_minor("300"),
                due_on=today - timedelta(days=3),
                issued_on=today - timedelta(days=14),
            )
            update_follow_up_cadence(
                data_dir,
                due_soon_days="3,0",
                overdue_days="3,7,14",
                minimum_gap_days=2,
                max_reminders=4,
                stop_after_overdue_days=45,
            )
            update_client_contact_state(
                data_dir,
                client="Protected Client",
                status="do_not_contact",
                reason="Client requested no reminders",
            )

            first = process_follow_up_cadences(data_dir, today=today)
            second = process_follow_up_cadences(data_dir, today=today)
            summary = follow_up_summary(data_dir, today=today)

            self.assertEqual(first["drafted"], 1)
            self.assertEqual(first["suppressed"], 1)
            self.assertEqual(second["drafted"], 0)
            self.assertEqual(second["existing"], 1)
            self.assertEqual(second["suppressed"], 1)
            self.assertEqual(summary["counts"]["drafted"], 1)
            self.assertEqual(summary["counts"]["suppressed"], 1)
            self.assertEqual(approval_queue_summary(data_dir)["counts"]["pending"], 1)

            active_event = next(item for item in summary["recent"] if item["receivable_id"] == active_id)
            protected_event = next(item for item in summary["recent"] if item["receivable_id"] == suppressed_id)
            self.assertIsNotNone(active_event["approval_id"])
            self.assertIsNone(protected_event["approval_id"])
            self.assertIn("do not contact", protected_event["suppression_reason"].lower())

            update_client_contact_state(data_dir, client="Protected Client", status="active")
            released = process_follow_up_cadences(data_dir, today=today)
            self.assertEqual(released["drafted"], 1)
            self.assertEqual(approval_queue_summary(data_dir)["counts"]["pending"], 2)

            review_approval_action(data_dir, int(active_event["approval_id"]), "approve")
            review_approval_action(data_dir, int(active_event["approval_id"]), "complete")
            with self.assertRaises(DivineToolError):
                queue_receivable_reminder(data_dir, active_id)

    def test_follow_up_outcomes_track_collection_and_cancel_stale_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            today = date.today()
            receivable_id = create_receivable(
                data_dir,
                client="Outcome Client",
                reference="INV-OUTCOME-001",
                amount_minor=parse_money_to_minor("200"),
                due_on=today,
                issued_on=today - timedelta(days=10),
            )
            reminder = queue_receivable_reminder(data_dir, receivable_id)
            event_id = int(reminder["event_id"])
            with self.assertRaises(DivineToolError):
                record_follow_up_outcome(data_dir, event_id, "payment_promised")
            review_approval_action(data_dir, reminder["approval_id"], "approve")
            review_approval_action(data_dir, reminder["approval_id"], "complete")
            promised = record_follow_up_outcome(
                data_dir,
                event_id,
                "payment_promised",
                "Client promised payment this week",
            )
            self.assertEqual(promised["event"]["outcome"], "payment_promised")

            partial = record_receivable_payment(
                data_dir,
                receivable_id,
                amount_minor=parse_money_to_minor("50"),
                payment_reference="PAY-OUTCOME-001",
                occurred_on=today,
            )
            self.assertEqual(partial["receivable"]["outstanding_gbp_minor"], 15000)
            self.assertEqual(follow_up_summary(data_dir)["recent"][0]["outcome"], "partial_payment")

            update_follow_up_cadence(
                data_dir,
                due_soon_days="3,0",
                overdue_days="3,7,14,30",
                minimum_gap_days=0,
                max_reminders=6,
                stop_after_overdue_days=60,
            )
            stale = queue_receivable_reminder(data_dir, receivable_id)
            record_receivable_payment(
                data_dir,
                receivable_id,
                amount_minor=parse_money_to_minor("150"),
                payment_reference="PAY-OUTCOME-002",
                occurred_on=today,
            )
            final = follow_up_summary(data_dir)
            events = {item["id"]: item for item in final["recent"]}
            self.assertEqual(events[event_id]["outcome"], "paid")
            self.assertEqual(events[int(stale["event_id"])]["status"], "cancelled")
            self.assertEqual(final["metrics"]["paid_count"], 1)
            self.assertEqual(final["metrics"]["collected_after_reminder_minor"], 20000)
            self.assertEqual(final["metrics"]["assisted_paid_receivables"], 1)
            report = generate_report(data_dir, period_name="week", today=today)
            self.assertIn("## Follow-Up Cadences", report["markdown"])
            self.assertEqual(report["follow_ups"]["metrics"]["completed_reminders"], 1)

    def test_reconciliation_import_scores_confirms_and_preserves_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            receivable_id = create_receivable(
                data_dir,
                client="Acme Limited",
                reference="INV-RECON-001",
                amount_minor=parse_money_to_minor("125"),
                due_on=date(2026, 9, 7),
                issued_on=date(2026, 8, 31),
            )
            csv_text = (
                "Date,Amount,Currency,Reference,Payer,Description,Direction\n"
                "2026-09-01,125.00,GBP,BANK-RECON-001,Acme Limited,Payment INV-RECON-001,Credit\n"
                "2026-09-01,40.00,GBP,BANK-DEBIT-001,Supplier,Subscription,Debit\n"
            )

            dry_run = import_reconciliation_csv(
                data_dir,
                csv_text,
                provider="bank",
                dry_run=True,
                filename="bank-export.csv",
            )
            self.assertEqual(dry_run["ready_count"], 1)
            self.assertEqual(dry_run["skipped_count"], 1)
            self.assertEqual(reconciliation_summary(data_dir)["total_count"], 0)

            imported = import_reconciliation_csv(
                data_dir,
                csv_text,
                provider="bank",
                filename="bank-export.csv",
            )
            transaction = reconciliation_summary(data_dir)["rows"][0]
            self.assertEqual(imported["imported_count"], 1)
            self.assertEqual(transaction["status"], "suggested")
            self.assertEqual(transaction["suggested_receivable_id"], receivable_id)
            self.assertEqual(transaction["match_confidence"], 100)
            self.assertIn("invoice reference appears", " ".join(transaction["match_reasons"]))

            repeated = import_reconciliation_csv(
                data_dir,
                csv_text,
                provider="bank",
                filename="bank-export.csv",
            )
            before_confirm = reconciliation_summary(data_dir)
            self.assertEqual(repeated["duplicate_count"], 1)
            self.assertEqual(before_confirm["total_count"], 1)
            self.assertEqual(before_confirm["recent_batches"][0]["repeated_of_batch_id"], imported["batch_id"])

            result = confirm_reconciliation_match(
                data_dir,
                transaction_id=transaction["id"],
                receivable_id=receivable_id,
                note="Reference, client, amount, and date all agree",
            )
            summary = reconciliation_summary(data_dir)
            self.assertEqual(result["receivable"]["state"], "paid")
            self.assertEqual(result["transaction"]["income_treatment"], "not_counted")
            self.assertEqual(summary["matched_count"], 1)
            self.assertEqual(summary["review_count"], 0)
            self.assertEqual(len(list_income(data_dir)), 0)
            self.assertEqual(summary["recent_decisions"][0]["action"], "confirmed")
            with closing(connect(data_dir)) as conn:
                payment = conn.execute(
                    "SELECT reconciliation_transaction_id FROM receivable_payments WHERE id = ?",
                    (result["payment"]["id"],),
                ).fetchone()
            self.assertEqual(payment["reconciliation_transaction_id"], transaction["id"])
            with self.assertRaises(DivineToolError):
                confirm_reconciliation_match(data_dir, transaction["id"], receivable_id)

            report = generate_report(data_dir, period_name="week", today=date(2026, 9, 1))
            self.assertIn("## Payment Reconciliation", report["markdown"])
            self.assertEqual(report["reconciliation"]["matched_count"], 1)

    def test_reconciliation_ambiguous_income_choice_ignore_and_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            first_id = create_receivable(
                data_dir,
                client="North Studio",
                reference="INV-NORTH-001",
                amount_minor=parse_money_to_minor("50"),
                due_on=date(2026, 9, 5),
                issued_on=date(2026, 8, 25),
            )
            second_id = create_receivable(
                data_dir,
                client="South Studio",
                reference="INV-SOUTH-001",
                amount_minor=parse_money_to_minor("50"),
                due_on=date(2026, 9, 5),
                issued_on=date(2026, 8, 25),
            )
            import_reconciliation_csv(
                data_dir,
                "Date,Amount,Currency\n2026-09-05,50.00,GBP\n",
                provider="generic",
                filename="ambiguous.csv",
            )
            ambiguous = reconciliation_summary(data_dir)["rows"][0]
            self.assertTrue(ambiguous["ambiguous"])
            self.assertEqual(ambiguous["match_label"], "ambiguous")
            self.assertEqual(len(ambiguous["candidates"]), 2)

            counted = confirm_reconciliation_match(
                data_dir,
                transaction_id=ambiguous["id"],
                receivable_id=second_id,
                count_as_income=True,
                note="Human selected South Studio",
            )
            self.assertEqual(counted["transaction"]["income_treatment"], "counted")
            self.assertEqual(counted["payment"]["counted_income_id"], list_income(data_dir)[0]["id"])
            self.assertEqual(counted["receivable"]["id"], second_id)

            import_reconciliation_csv(
                data_dir,
                "Date,Amount,Currency,Reference,Description\n2026-09-06,10.00,GBP,TRANSFER-001,Internal transfer\n",
                provider="bank",
                filename="transfer.csv",
            )
            transfer = next(item for item in reconciliation_summary(data_dir)["rows"] if item["status"] != "matched")
            ignored = ignore_reconciliation_transaction(
                data_dir,
                transfer["id"],
                "Internal transfer, not customer revenue",
            )
            self.assertEqual(ignored["transaction"]["status"], "ignored")
            self.assertEqual(reconciliation_summary(data_dir)["ignored_count"], 1)
            with self.assertRaises(DivineToolError):
                ignore_reconciliation_transaction(data_dir, transfer["id"], "again")

            import_reconciliation_csv(
                data_dir,
                "Date,Amount,Currency,Reference,Payer\n2026-09-05,50.00,GBP,CONCURRENT-REC-001,North Studio\n",
                provider="bank",
                filename="concurrent.csv",
            )
            concurrent = next(
                item
                for item in reconciliation_summary(data_dir)["rows"]
                if item["external_reference"] == "CONCURRENT-REC-001"
            )
            barrier = threading.Barrier(2)
            outcomes: list[str] = []

            def confirm() -> None:
                barrier.wait()
                try:
                    confirm_reconciliation_match(data_dir, concurrent["id"], first_id)
                    outcomes.append("matched")
                except DivineToolError:
                    outcomes.append("blocked")

            threads = [threading.Thread(target=confirm), threading.Thread(target=confirm)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            final = reconciliation_summary(data_dir)
            self.assertCountEqual(outcomes, ["matched", "blocked"])
            self.assertEqual(final["matched_count"], 2)
            with closing(connect(data_dir)) as conn:
                linked_count = conn.execute(
                    "SELECT COUNT(*) FROM receivable_payments WHERE reconciliation_transaction_id = ?",
                    (concurrent["id"],),
                ).fetchone()[0]
            self.assertEqual(linked_count, 1)

    def test_revenue_rules_evaluate_log_and_report_without_executing_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("1000"), "week")
            set_mood(data_dir, "watchful")
            create_lead(
                data_dir,
                title="Rule Candidate",
                contact="Buyer Ltd",
                source="Referral",
                offer="Automation engagement",
                estimated_value_minor=parse_money_to_minor("900"),
                probability=0.8,
                stage="proposal",
                strategy="freelance_services",
                next_action="Review proposal evidence",
                follow_up_on=date.today(),
            )
            promote_id = create_revenue_rule(
                data_dir,
                name="Promote strong service pipeline",
                rule_type="promote",
                metric="open_weighted_value",
                operator="gte",
                threshold_value="400",
                action="Prioritise the highest-value service proposal",
                strategy="freelance_services",
                approval_required=False,
            )
            approval_id = create_revenue_rule(
                data_dir,
                name="Gate weak conversion evidence",
                rule_type="require_approval",
                metric="conversion_rate_pct",
                operator="lte",
                threshold_value="20",
                action="Require a human review before increasing outreach",
                approval_required=True,
            )

            summary = revenue_rules_summary(data_dir)
            rules = {rule["id"]: rule for rule in summary["rows"]}

            self.assertEqual(summary["active_count"], 2)
            self.assertEqual(summary["triggered_count"], 2)
            self.assertEqual(summary["approval_required_count"], 1)
            self.assertEqual(rules[promote_id]["evaluation"]["decision"], "apply")
            self.assertEqual(rules[approval_id]["evaluation"]["decision"], "approval")
            self.assertEqual(rules[promote_id]["evaluation"]["metric_value"], 72000.0)

            self.assertEqual(record_revenue_rule_runs(data_dir, summary), 2)
            logged = revenue_rules_summary(data_dir)
            self.assertEqual(len(logged["recent_runs"]), 2)
            self.assertTrue(all(run["triggered"] for run in logged["recent_runs"]))

            report = generate_report(data_dir, period_name="week", today=date.today())
            self.assertIn("## Revenue Rules", report["markdown"])
            self.assertIn("Prioritise the highest-value service proposal", report["markdown"])

            paused = update_revenue_rule(data_dir, promote_id, {"status": "paused"})
            self.assertEqual(paused["status"], "paused")
            after_pause = revenue_rules_summary(data_dir)
            self.assertEqual(after_pause["triggered_count"], 1)
            self.assertEqual(
                next(rule for rule in after_pause["rows"] if rule["id"] == promote_id)["evaluation"]["decision"],
                "inactive",
            )

    def test_config_migration_adds_strategy_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "config.json").write_text(
                json.dumps(
                    {
                        "god_name": "Creator",
                        "active_mood": "watchful",
                        "base_currency": "GBP",
                        "moods": {
                            "watchful": {
                                "period": "week",
                                "quota_minor": 10000,
                                "punishment": "review",
                            }
                        },
                        "channels": [
                            {
                                "name": "Freelance services",
                                "expected_gbp_minor": 25000,
                                "effort": "medium",
                                "risk": "low",
                                "next_action": "Send proposals.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(data_dir)

            self.assertEqual(config["channels"][0]["id"], "freelance_services")
            self.assertEqual(config["channels"][0]["deadline_fit"], "high")
            self.assertEqual(config["channels"][0]["repeatability"], "medium")
            self.assertTrue(config["auth"]["enabled"])
            self.assertTrue(config["deployment"]["backup"]["enabled"])

    def test_sqlite_runtime_settings_and_versioned_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            status = database_status(data_dir)

            self.assertTrue(status["ready"])
            self.assertEqual(status["journal_mode"], "wal")
            self.assertTrue(status["foreign_keys"])
            self.assertGreaterEqual(status["busy_timeout_ms"], 10_000)
            self.assertEqual(status["schema_version"], LATEST_SCHEMA_VERSION)
            self.assertEqual([row["version"] for row in status["migrations"]], list(range(1, LATEST_SCHEMA_VERSION + 1)))

            with closing(connect(data_dir)) as conn:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO auth_sessions
                            (token_hash, account_id, created_at, expires_at, last_seen_at, user_agent)
                        VALUES ('missing-account', 999, 'now', 'later', 'now', 'test')
                        """
                    )

    def test_legacy_sqlite_state_is_preserved_and_migrations_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            legacy = sqlite3.connect(data_dir / "divine_tool.sqlite3")
            try:
                legacy.execute(
                    """
                    CREATE TABLE income (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        amount_minor INTEGER NOT NULL,
                        currency TEXT NOT NULL,
                        gbp_minor INTEGER NOT NULL,
                        source TEXT NOT NULL,
                        note TEXT NOT NULL DEFAULT '',
                        occurred_at TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                legacy.execute(
                    """
                    INSERT INTO income
                        (amount_minor, currency, gbp_minor, source, note, occurred_at, created_at)
                    VALUES (4200, 'GBP', 4200, 'legacy invoice', 'preserve me', '2026-08-20', '2026-08-20T09:00:00')
                    """
                )
                legacy.commit()
            finally:
                legacy.close()

            pre_migration_backup = create_backup(data_dir, data_dir / "backups")
            backup_check = data_dir / "backup-check"
            with zipfile.ZipFile(pre_migration_backup["archive"]) as archive:
                archive.extract("divine_tool.sqlite3", backup_check)
            backup_conn = sqlite3.connect(backup_check / "divine_tool.sqlite3")
            try:
                self.assertEqual(int(backup_conn.execute("PRAGMA user_version").fetchone()[0]), 0)
                self.assertIsNone(
                    backup_conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
                    ).fetchone()
                )
            finally:
                backup_conn.close()

            restored_legacy = restore_backup(pre_migration_backup["archive"], data_dir / "restored-legacy")
            restored_rows = list_income(data_dir / "restored-legacy")
            self.assertEqual(restored_legacy["source_schema_version"], 0)
            self.assertEqual(restored_legacy["schema_version"], LATEST_SCHEMA_VERSION)
            self.assertEqual(restored_rows[0]["source"], "legacy invoice")
            self.assertEqual(restored_rows[0]["gbp_minor"], 4200)

            ensure_state(data_dir)
            first_status = database_status(data_dir)
            ensure_state(data_dir)
            second_status = database_status(data_dir)

            self.assertEqual(first_status["schema_version"], LATEST_SCHEMA_VERSION)
            self.assertEqual(first_status["migrations"], second_status["migrations"])
            with closing(connect(data_dir)) as conn:
                row = conn.execute("SELECT * FROM income WHERE source = 'legacy invoice'").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["gbp_minor"], 4200)
                self.assertEqual(row["temple_id"], "main")
                self.assertEqual(row["strategy"], "")

    def test_failed_schema_migration_rolls_back_without_advancing_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ensure_state(data_dir)

            def fail_after_schema_change(conn: sqlite3.Connection) -> None:
                conn.execute("CREATE TABLE migration_must_rollback (id INTEGER PRIMARY KEY)")
                conn.execute("INSERT INTO migration_must_rollback (id) VALUES (1)")
                raise RuntimeError("deliberate migration failure")

            with closing(connect(data_dir)) as conn:
                with self.assertRaisesRegex(RuntimeError, "deliberate migration failure"):
                    run_migrations(
                        conn,
                        SCHEMA_MIGRATIONS
                        + (SchemaMigration(LATEST_SCHEMA_VERSION + 1, "deliberate_failure", fail_after_schema_change),),
                    )
                self.assertEqual(int(conn.execute("PRAGMA user_version").fetchone()[0]), LATEST_SCHEMA_VERSION)
                self.assertIsNone(
                    conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'migration_must_rollback'"
                    ).fetchone()
                )
                self.assertIsNone(
                    conn.execute(
                        "SELECT 1 FROM schema_migrations WHERE version = ?",
                        (LATEST_SCHEMA_VERSION + 1,),
                    ).fetchone()
                )

    def test_concurrent_web_and_daemon_activity_and_lock_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            ensure_state(data_dir)
            start = threading.Barrier(3)
            failures: list[BaseException] = []

            def web_writer() -> None:
                try:
                    start.wait()
                    for index in range(12):
                        add_income(data_dir, 100 + index, "GBP", None, f"concurrent web {index}")
                except BaseException as exc:
                    failures.append(exc)

            def daemon_writer() -> None:
                try:
                    start.wait()
                    for index in range(24):
                        record_heartbeat(data_dir, detail=f"concurrent daemon {index}")
                except BaseException as exc:
                    failures.append(exc)

            def dashboard_reader() -> None:
                try:
                    start.wait()
                    for _ in range(12):
                        status_report(data_dir)
                except BaseException as exc:
                    failures.append(exc)

            threads = [
                threading.Thread(target=web_writer),
                threading.Thread(target=daemon_writer),
                threading.Thread(target=dashboard_reader),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(failures, [])
            self.assertEqual(len(list_income(data_dir, limit=20)), 12)

            holder = connect(data_dir)
            holder.execute("BEGIN IMMEDIATE")
            holder.execute(
                "INSERT INTO events (temple_id, level, category, message, created_at) VALUES ('main', 'info', 'test', 'held lock', 'now')"
            )
            lock_failure: list[BaseException] = []
            elapsed: list[float] = []

            def waiting_writer() -> None:
                started = time.monotonic()
                try:
                    record_heartbeat(data_dir, worker_name="lock-recovery", detail="recovered")
                except BaseException as exc:
                    lock_failure.append(exc)
                finally:
                    elapsed.append(time.monotonic() - started)

            waiter = threading.Thread(target=waiting_writer)
            waiter.start()
            time.sleep(0.2)
            holder.commit()
            holder.close()
            waiter.join(timeout=5)

            self.assertFalse(waiter.is_alive())
            self.assertEqual(lock_failure, [])
            self.assertGreaterEqual(elapsed[0], 0.15)
            with closing(connect(data_dir)) as conn:
                recovered = conn.execute(
                    "SELECT detail FROM worker_heartbeat WHERE worker_name = 'lock-recovery'"
                ).fetchone()
            self.assertEqual(recovered["detail"], "recovered")

    def test_owner_account_and_session_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            self.assertTrue(auth_status(data_dir)["setup_required"])

            account = create_account(
                data_dir,
                "Creator.One",
                "strong-pass-123",
                display_name="Creator",
                recovery_email="Creator@Example.COM",
            )

            self.assertEqual(account["username"], "creator.one")
            self.assertEqual(account["role"], "owner")
            self.assertEqual(account["recovery_email"], "creator@example.com")
            self.assertEqual(len(list_accounts(data_dir)), 1)
            self.assertFalse(auth_status(data_dir)["setup_required"])

            updated = update_account_profile(
                data_dir,
                int(account["id"]),
                display_name="Prime Creator",
                recovery_email="prime@example.com",
            )
            self.assertEqual(updated["display_name"], "Prime Creator")
            self.assertEqual(updated["recovery_email"], "prime@example.com")

            with self.assertRaises(DivineToolError):
                create_account(data_dir, "second", "strong-pass-123")
            with self.assertRaises(DivineToolError):
                update_account_profile(data_dir, int(account["id"]), recovery_email="not-an-email")
            with self.assertRaises(DivineToolError):
                create_session(data_dir, "creator.one", "wrong-pass")

            session = create_session(data_dir, "creator.one", "strong-pass-123", user_agent="test")

            self.assertTrue(session["token"])
            self.assertEqual(auth_status(data_dir, session["token"])["account"]["username"], "creator.one")
            reset = reset_account_password(data_dir, "creator.one", "better-pass-456")
            self.assertEqual(reset["username"], "creator.one")
            self.assertEqual(reset["recovery_email"], "prime@example.com")
            self.assertFalse(auth_status(data_dir, session["token"])["authenticated"])
            with self.assertRaises(DivineToolError):
                create_session(data_dir, "creator.one", "strong-pass-123")
            new_session = create_session(data_dir, "creator.one", "better-pass-456", user_agent="test")
            self.assertEqual(auth_status(data_dir, new_session["token"])["account"]["username"], "creator.one")
            destroy_session(data_dir, session["token"])
            destroy_session(data_dir, new_session["token"])
            self.assertFalse(auth_status(data_dir, new_session["token"])["authenticated"])

    def test_multi_temple_profiles_scope_income(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("100"), "week")
            add_income(data_dir, parse_money_to_minor("40"), "GBP", None, "main invoice", occurred_on=date(2026, 8, 19))

            created = create_temple(data_dir, "Product Temple", template="products")
            temples = list_temples(data_dir)

            self.assertEqual(created["id"], "product_temple")
            self.assertEqual(len(temples), 2)
            self.assertTrue(any(temple["active"] and temple["id"] == "main" for temple in temples))

            switch_temple(data_dir, "product_temple")
            set_quota(data_dir, "watchful", parse_money_to_minor("200"), "week")
            add_income(
                data_dir,
                parse_money_to_minor("150"),
                "GBP",
                None,
                "product sale",
                strategy="digital_product",
                occurred_on=date(2026, 8, 20),
            )

            product_status = status_report(data_dir, today=date(2026, 8, 20))
            product_rows = list_income(data_dir)

            self.assertEqual(product_status["temple"]["id"], "product_temple")
            self.assertEqual(product_status["earned_minor"], 15000)
            self.assertEqual(product_status["quota_minor"], 20000)
            self.assertEqual(len(product_rows), 1)
            self.assertEqual(product_rows[0]["source"], "product sale")

            switch_temple(data_dir, "main")
            main_status = status_report(data_dir, today=date(2026, 8, 20))
            summary = temple_summary(data_dir, today=date(2026, 8, 20))
            rows = {row["id"]: row for row in summary["rows"]}

            self.assertEqual(main_status["earned_minor"], 4000)
            self.assertEqual(rows["main"]["earned_minor"], 4000)
            self.assertEqual(rows["product_temple"]["earned_minor"], 15000)
            self.assertEqual(summary["total_earned_minor"], 19000)

    def test_deployment_preflight_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "state"
            backup_dir = Path(tmp) / "backups"
            production_defaults = deployment_environment({"DIVINE_DEPLOYMENT_MODE": "production"})
            self.assertTrue(production_defaults["cookie_secure"])
            self.assertTrue(production_defaults["csrf_require_origin"])
            self.assertTrue(production_defaults["force_https"])
            self.assertFalse(production_defaults["trust_proxy"])
            environ = {
                "DIVINE_DATA_DIR": str(data_dir),
                "DIVINE_BACKUP_DIR": str(backup_dir),
                "DIVINE_HOST": "0.0.0.0",
                "DIVINE_PORT": "8765",
                "DIVINE_DAEMON_INTERVAL": "60",
                "DIVINE_DEPLOYMENT_MODE": "production",
                "DIVINE_PUBLIC_URL": "https://divine.example",
                "DIVINE_ALLOWED_ORIGINS": "https://divine.example",
                "DIVINE_COOKIE_SECURE": "true",
                "DIVINE_CSRF_REQUIRE_ORIGIN": "true",
                "DIVINE_TRUST_PROXY": "true",
                "DIVINE_FORCE_HTTPS": "true",
            }

            env = deployment_environment(environ)

            self.assertEqual(env["data_dir"], data_dir.resolve())
            self.assertEqual(env["backup_dir"], backup_dir.resolve())
            self.assertEqual(env["daemon_interval"], 60)
            self.assertTrue(env["cookie_secure"])
            self.assertEqual(env["allowed_origins"], ["https://divine.example"])
            self.assertTrue(env["csrf_require_origin"])
            self.assertTrue(env["trust_proxy"])
            self.assertTrue(env["force_https"])

            blocked = deployment_preflight(data_dir, host="0.0.0.0", port=8765, environ=environ)

            self.assertEqual(blocked["status"], "blocked")
            self.assertTrue(any(item["name"] == "owner_account" and item["severity"] == "fail" for item in blocked["checks"]))

            create_account(data_dir, "creator", "strong-pass-123")
            run_worker_cycle(data_dir, trigger="daemon", worker_name="daemon")
            add_income(data_dir, parse_money_to_minor("25"), "GBP", None, "deployment smoke")

            incomplete = deployment_preflight(
                data_dir,
                host="0.0.0.0",
                port=8765,
                environ={"DIVINE_DEPLOYMENT_MODE": "production"},
            )
            self.assertEqual(incomplete["status"], "blocked")
            self.assertTrue(
                any(item["name"] == "hosted_origin" and item["severity"] == "fail" for item in incomplete["checks"])
            )
            self.assertTrue(
                any(item["name"] == "proxy_headers" and item["severity"] == "fail" for item in incomplete["checks"])
            )

            ready = deployment_preflight(data_dir, host="0.0.0.0", port=8765, environ=environ)

            self.assertEqual(ready["status"], "ready")

            backup = create_backup(data_dir, backup_dir)

            self.assertTrue(backup["archive"].exists())
            with zipfile.ZipFile(backup["archive"]) as archive:
                names = set(archive.namelist())
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertIn("config.json", names)
            self.assertIn("divine_tool.sqlite3", names)
            self.assertIn("manifest.json", names)
            self.assertEqual(manifest["format_version"], BACKUP_FORMAT_VERSION)
            self.assertTrue(all("sha256" in record for record in manifest["files"]))
            self.assertEqual(backup["verification"]["status"], "verified")

    def test_verified_restore_requires_confirmation_and_preserves_a_safety_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "state"
            backup_dir = root / "backups"
            add_income(data_dir, 1250, "GBP", None, "before backup")
            backup = create_backup(data_dir, backup_dir)
            add_income(data_dir, 875, "GBP", None, "after backup")

            verification = verify_backup(backup["archive"])
            self.assertEqual(verification["format_version"], BACKUP_FORMAT_VERSION)
            self.assertEqual(verification["status"], "verified")
            with self.assertRaisesRegex(DivineToolError, "--confirm"):
                restore_backup(backup["archive"], data_dir)

            restored = restore_backup(
                backup["archive"],
                data_dir,
                replace=True,
                safety_output_dir=backup_dir,
            )

            self.assertEqual(restored["status"], "restored")
            self.assertEqual(restored["schema_version"], LATEST_SCHEMA_VERSION)
            self.assertTrue(restored["safety_backup"].exists())
            self.assertEqual([row["source"] for row in list_income(data_dir)], ["before backup"])
            self.assertTrue(state_integrity(data_dir)["ok"])
            self.assertEqual(verify_backup(restored["safety_backup"])["status"], "verified")

            restore_backup(restored["safety_backup"], data_dir, replace=True, safety_output_dir=backup_dir)
            self.assertEqual(
                {row["source"] for row in list_income(data_dir)},
                {"before backup", "after backup"},
            )

    def test_backup_verification_rejects_tampering_and_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "state"
            add_income(data_dir, 500, "GBP", None, "tamper test")
            backup = create_backup(data_dir, root / "backups")
            tampered = root / "tampered.zip"
            with zipfile.ZipFile(backup["archive"]) as source, zipfile.ZipFile(
                tampered, "w", compression=zipfile.ZIP_DEFLATED
            ) as target:
                for info in source.infolist():
                    payload = source.read(info.filename)
                    if info.filename == "config.json":
                        payload = bytes([payload[0] ^ 1]) + payload[1:]
                    target.writestr(info, payload)

            with self.assertRaisesRegex(DivineToolError, "checksum"):
                verify_backup(tampered)

            unsafe = root / "unsafe.zip"
            with zipfile.ZipFile(unsafe, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps({"files": ["config.json"]}))
                archive.writestr("../config.json", "{}")
            with self.assertRaisesRegex(DivineToolError, "unsafe path"):
                verify_backup(unsafe)

    def test_restore_staging_failure_leaves_live_state_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "state"
            backup_dir = root / "backups"
            add_income(data_dir, 1000, "GBP", None, "backup state")
            backup = create_backup(data_dir, backup_dir)
            add_income(data_dir, 2000, "GBP", None, "newer live state")
            before = state_integrity(data_dir)

            with patch("divine_tool.deployment.ensure_state", side_effect=RuntimeError("migration drill failure")):
                with self.assertRaisesRegex(DivineToolError, "before live state was changed"):
                    restore_backup(backup["archive"], data_dir, replace=True, safety_output_dir=backup_dir)

            after = state_integrity(data_dir)
            self.assertEqual(before["config_sha256"], after["config_sha256"])
            self.assertEqual(before["database"]["table_counts"], after["database"]["table_counts"])
            self.assertEqual(
                {row["source"] for row in list_income(data_dir)},
                {"backup state", "newer live state"},
            )

    def test_recovery_drills_cover_persistence_and_failure_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "state"
            add_income(data_dir, 3300, "GBP", None, "drill baseline")
            before = state_integrity(data_dir)

            result = run_recovery_drills(data_dir, root / "backups")
            after = state_integrity(data_dir)

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "passed")
            self.assertEqual(
                {item["name"] for item in result["checks"]},
                {
                    "backup_restore_round_trip",
                    "persistent_volume_restart",
                    "interrupted_command_write",
                    "migration_failure_rollback",
                    "stale_worker_recovery",
                },
            )
            self.assertTrue(all(item["severity"] == "pass" for item in result["checks"]))
            self.assertEqual(before["database"]["table_counts"], after["database"]["table_counts"])

            compose_text = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
            self.assertEqual(compose_text.count("divine_data:/data"), 2)
            self.assertEqual(compose_text.count("restart: unless-stopped"), 2)

    def test_strategy_roi_compares_periods_and_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("1000"), "week")
            set_mood(data_dir, "watchful")
            add_income(
                data_dir,
                amount_minor=parse_money_to_minor("40"),
                currency="GBP",
                gbp_minor=None,
                source="previous invoice",
                strategy="freelance_services",
                occurred_on=date(2026, 8, 12),
            )
            add_income(
                data_dir,
                amount_minor=parse_money_to_minor("85"),
                currency="GBP",
                gbp_minor=None,
                source="current invoice",
                note="client renewed",
                strategy="freelance_services",
                occurred_on=date(2026, 8, 19),
            )

            summary = strategy_roi_summary(data_dir, today=date(2026, 8, 20))
            rows = {row["id"]: row for row in summary["rows"]}

            self.assertEqual(rows["freelance_services"]["current_period_minor"], 8500)
            self.assertEqual(rows["freelance_services"]["previous_period_minor"], 4000)
            self.assertEqual(rows["freelance_services"]["trend"], "growing")
            self.assertEqual(rows["freelance_services"]["recommendation"], "push")
            self.assertEqual(rows["freelance_services"]["notes"][0]["note"], "client renewed")
            self.assertTrue(any(row["recommendation"] == "pause" for row in summary["pause_recommendations"]))

    def test_generate_report_includes_roi_and_upgrades(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            set_quota(data_dir, "watchful", parse_money_to_minor("100"), "week")
            set_mood(data_dir, "watchful")
            add_income(
                data_dir,
                amount_minor=parse_money_to_minor("25"),
                currency="GBP",
                gbp_minor=None,
                source="report invoice",
                note="report note",
                strategy="freelance_services",
                occurred_on=date(2026, 8, 19),
            )

            report = generate_report(data_dir, period_name="week", today=date(2026, 8, 20))

            self.assertEqual(report["title"], "Divine Profit Weekly Report")
            self.assertEqual(report["earned_minor"], 2500)
            self.assertIn("## Strategy ROI", report["markdown"])
            self.assertIn("## Upgrade Recommendations", report["markdown"])
            self.assertEqual(report["income"][0]["note"], "report note")

    def test_import_income_csv_dry_run_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            csv_text = (
                "Date,Amount,Source,Strategy,Reference,Note\n"
                "21/08/2026,£42.50,client invoice,freelance_services,INV-1,paid\n"
                "21/08/2026,GBP 42.50,client invoice,freelance_services,INV-1,paid\n"
                "2026-08-21,-3.00,refund,freelance_services,REF-1,refund\n"
            )

            dry_run = import_income_csv(data_dir, csv_text, source_type="payment", dry_run=True, filename="payments.csv")

            self.assertEqual(dry_run["ready_count"], 1)
            self.assertEqual(dry_run["duplicate_count"], 1)
            self.assertEqual(dry_run["skipped_count"], 1)
            self.assertEqual(dry_run["rows"][0]["status"], "ready")
            self.assertEqual(dry_run["rows"][1]["status"], "duplicate")
            self.assertIn("Matches row 2", dry_run["rows"][1]["reason"])

            imported = import_income_csv(data_dir, csv_text, source_type="payment", dry_run=False, filename="payments.csv")
            rows = list_income(data_dir)

            self.assertEqual(imported["imported_count"], 1)
            self.assertEqual(imported["duplicate_count"], 1)
            self.assertEqual(imported["skipped_count"], 1)
            self.assertEqual(rows[0]["gbp_minor"], 4250)
            self.assertEqual(rows[0]["strategy"], "freelance_services")

            duplicate_run = import_income_csv(data_dir, csv_text, source_type="payment", dry_run=False, filename="payments.csv")

            self.assertEqual(duplicate_run["imported_count"], 0)
            self.assertEqual(duplicate_run["duplicate_count"], 2)
            self.assertEqual(duplicate_run["skipped_count"], 1)
            self.assertEqual(status_report(data_dir, today=date(2026, 8, 21))["earned_minor"], 4250)

    def test_import_income_csv_affiliate_and_non_gbp_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            csv_text = (
                "paid_at,commission,currency,gbp_equivalent,program,sale_id\n"
                "21 Aug 2026,12.34,USD,9.75,Partner Network,A-1\n"
                "21 Aug 2026,0.01,BTC,,Crypto Network,A-2\n"
            )

            result = import_income_csv(data_dir, csv_text, source_type="affiliate", dry_run=False)
            rows = list_income(data_dir)

            self.assertEqual(result["imported_count"], 1)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(rows[0]["gbp_minor"], 975)
            self.assertEqual(rows[0]["currency"], "USD")
            self.assertEqual(rows[0]["strategy"], "affiliate_referral")
            self.assertEqual(result["rows"][1]["reason"], "Non-GBP row needs a GBP equivalent column.")

    def test_approval_queue_requires_human_review_before_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            action_id = create_approval_draft(
                data_dir,
                kind="invoice_reminder",
                target="Client One",
                amount_minor=parse_money_to_minor("250"),
                due_on=date(2026, 8, 30),
                invoice="INV-100",
                strategy="freelance_services",
            )

            pending = list_approval_actions(data_dir, status="pending")

            self.assertEqual(len(pending), 1)
            self.assertIn("INV-100", pending[0]["body"])
            self.assertIn("£250.00", pending[0]["body"])
            self.assertEqual(approval_queue_summary(data_dir)["counts"]["pending"], 1)

            with self.assertRaises(DivineToolError):
                review_approval_action(data_dir, action_id, "complete")

            approved = review_approval_action(data_dir, action_id, "approve", "Looks good")
            completed = review_approval_action(data_dir, action_id, "complete", "Sent manually")

            self.assertEqual(approved["status"], "approved")
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(approval_queue_summary(data_dir)["counts"]["completed"], 1)

    def test_external_connections_snapshot_uses_read_only_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            def fake_fetch(url: str, _headers: dict[str, str] | None = None):
                if "frankfurter" in url:
                    return [
                        {"date": "2026-08-21", "base": "GBP", "quote": "USD", "rate": 1.25},
                        {"date": "2026-08-21", "base": "GBP", "quote": "EUR", "rate": 1.10},
                    ]
                if url.endswith("/repos/liamryan391/Divine-Profit-Bot"):
                    return {"stargazers_count": 7, "updated_at": "2026-08-22T12:00:00Z"}
                if "/commits?" in url:
                    return [{"sha": "a"}, {"sha": "b"}]
                if "/issues?" in url:
                    return [{"number": 1}, {"number": 2, "pull_request": {}}]
                if "/pulls?" in url:
                    return [{"number": 2}]
                raise AssertionError(f"Unexpected URL: {url}")

            snapshot = external_connections_snapshot(data_dir, today=date(2026, 8, 23), fetch_json=fake_fetch)
            connections = {item["id"]: item for item in snapshot["connections"]}

            self.assertEqual(snapshot["connected_count"], 2)
            self.assertEqual(connections["currency_rates"]["state"], "connected")
            self.assertEqual(connections["currency_rates"]["items"][0]["currency"], "USD")
            self.assertEqual(connections["currency_rates"]["items"][0]["one_unit"], "£0.80")
            self.assertEqual(connections["github"]["items"][0]["value"], "2")
            self.assertEqual(connections["github"]["items"][1]["value"], "1")
            self.assertEqual(connections["github"]["items"][2]["value"], "1")
            self.assertEqual(connections["payments"]["state"], "ready")
            self.assertEqual(connections["product_analytics"]["state"], "disabled")

    def test_external_payment_snapshot_uses_env_key_without_storing_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            config = load_config(data_dir)
            config["integrations"]["currency_rates"]["enabled"] = False
            config["integrations"]["github"]["enabled"] = False
            config["integrations"]["payments"]["enabled"] = True
            save_config(data_dir, config)

            def fake_fetch(url: str, headers: dict[str, str] | None = None):
                self.assertIn("stripe.com/v1/balance_transactions", url)
                self.assertIn("Authorization", headers or {})
                self.assertNotIn("sk_test", url)
                return {
                    "data": [
                        {"currency": "gbp", "net": 1500},
                        {"currency": "gbp", "net": -125},
                    ]
                }

            snapshot = external_connections_snapshot(
                data_dir,
                fetch_json=fake_fetch,
                environ={"DIVINE_STRIPE_SECRET_KEY": "sk_test_readonly"},
            )
            payments = {item["id"]: item for item in snapshot["connections"]}["payments"]

            self.assertEqual(payments["state"], "connected")
            self.assertEqual(payments["items"][0]["net"], "£13.75")
            self.assertEqual(payments["items"][0]["transaction_count"], "2")


if __name__ == "__main__":
    unittest.main()
