from __future__ import annotations

import json
import tempfile
import threading
import unittest
import zipfile
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from divine_tool.core import (
    DivineToolError,
    add_income,
    approval_queue_summary,
    auth_status,
    create_account,
    create_approval_draft,
    create_session,
    create_temple,
    destroy_session,
    enqueue_command,
    external_connections_snapshot,
    generate_opportunities,
    generate_report,
    import_income_csv,
    list_approval_actions,
    list_accounts,
    list_income,
    list_temples,
    load_config,
    parse_money_to_minor,
    process_command_inbox,
    record_heartbeat,
    save_config,
    review_approval_action,
    set_mood,
    set_quota,
    status_report,
    strategy_roi_summary,
    switch_temple,
    temple_summary,
)
from divine_tool.deployment import create_backup, deployment_environment, deployment_preflight
from divine_tool.web import make_handler


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
                    self.assertIn(b"Divine Income Engine", html)
                    self.assertIn(b'href="/styles.css"', html)
                    self.assertIn(b'src="/app.js"', html)

                with urlopen(f"{base_url}/styles.css") as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(b".auth-gate", response.read())

                with urlopen(f"{base_url}/app.js") as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(b"function boot()", response.read())

                try:
                    urlopen(f"{base_url}/api/status")
                    self.fail("Protected status endpoint should require authentication.")
                except HTTPError as blocked:
                    self.assertEqual(blocked.code, 401)
                    blocked.close()

                setup_body = json.dumps(
                    {"username": "creator", "display_name": "Creator", "password": "strong-pass-123"}
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

                json_headers = {"Content-Type": "application/json", "Cookie": cookie}
                auth_headers = {"Cookie": cookie}

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
                self.assertEqual(side_income_payload["state"]["temples"]["total_earned_minor"], 5500)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

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

    def test_owner_account_and_session_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            self.assertTrue(auth_status(data_dir)["setup_required"])

            account = create_account(data_dir, "Creator.One", "strong-pass-123", display_name="Creator")

            self.assertEqual(account["username"], "creator.one")
            self.assertEqual(account["role"], "owner")
            self.assertEqual(len(list_accounts(data_dir)), 1)
            self.assertFalse(auth_status(data_dir)["setup_required"])

            with self.assertRaises(DivineToolError):
                create_account(data_dir, "second", "strong-pass-123")
            with self.assertRaises(DivineToolError):
                create_session(data_dir, "creator.one", "wrong-pass")

            session = create_session(data_dir, "creator.one", "strong-pass-123", user_agent="test")

            self.assertTrue(session["token"])
            self.assertEqual(auth_status(data_dir, session["token"])["account"]["username"], "creator.one")
            destroy_session(data_dir, session["token"])
            self.assertFalse(auth_status(data_dir, session["token"])["authenticated"])

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
            environ = {
                "DIVINE_DATA_DIR": str(data_dir),
                "DIVINE_BACKUP_DIR": str(backup_dir),
                "DIVINE_HOST": "0.0.0.0",
                "DIVINE_PORT": "8765",
                "DIVINE_DAEMON_INTERVAL": "60",
                "DIVINE_PUBLIC_URL": "https://divine.example",
                "DIVINE_COOKIE_SECURE": "true",
            }

            env = deployment_environment(environ)

            self.assertEqual(env["data_dir"], data_dir.resolve())
            self.assertEqual(env["backup_dir"], backup_dir.resolve())
            self.assertEqual(env["daemon_interval"], 60)
            self.assertTrue(env["cookie_secure"])

            blocked = deployment_preflight(data_dir, host="0.0.0.0", port=8765, environ=environ)

            self.assertEqual(blocked["status"], "blocked")
            self.assertTrue(any(item["name"] == "owner_account" and item["severity"] == "fail" for item in blocked["checks"]))

            create_account(data_dir, "creator", "strong-pass-123")
            record_heartbeat(data_dir)
            add_income(data_dir, parse_money_to_minor("25"), "GBP", None, "deployment smoke")

            ready = deployment_preflight(data_dir, host="0.0.0.0", port=8765, environ=environ)

            self.assertEqual(ready["status"], "ready")

            backup = create_backup(data_dir, backup_dir)

            self.assertTrue(backup["archive"].exists())
            with zipfile.ZipFile(backup["archive"]) as archive:
                names = set(archive.namelist())
            self.assertIn("config.json", names)
            self.assertIn("divine_tool.sqlite3", names)
            self.assertIn("manifest.json", names)

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
