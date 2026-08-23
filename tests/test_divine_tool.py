from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from divine_tool.core import (
    DivineToolError,
    add_income,
    enqueue_command,
    generate_opportunities,
    generate_report,
    import_income_csv,
    list_income,
    load_config,
    parse_money_to_minor,
    process_command_inbox,
    set_mood,
    set_quota,
    status_report,
    strategy_roi_summary,
)
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
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_dir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(f"{base_url}/") as response:
                    self.assertIn(b"Divine Income Engine", response.read())

                body = json.dumps({"amount": "30", "source": "web invoice"}).encode("utf-8")
                request = Request(
                    f"{base_url}/api/income",
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(payload["ok"])
                self.assertEqual(payload["state"]["status"]["earned_minor"], 3000)
                self.assertIn("strategy_roi", payload["state"])

                with urlopen(f"{base_url}/api/report?period=week") as response:
                    report_payload = json.loads(response.read().decode("utf-8"))

                self.assertIn("report", report_payload)
                self.assertIn("markdown", report_payload["report"])
                self.assertIn("Missed-Quota Review", report_payload["report"]["markdown"])

                import_body = json.dumps(
                    {
                        "csv_text": "Date,Amount,Source,Strategy\n2026-08-21,15.00,web import,freelance_services\n",
                        "source_type": "payment",
                        "dry_run": False,
                        "filename": "web-import.csv",
                    }
                ).encode("utf-8")
                import_request = Request(
                    f"{base_url}/api/import/csv",
                    data=import_body,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(import_request) as response:
                    import_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(import_payload["ok"])
                self.assertEqual(import_payload["import_result"]["imported_count"], 1)
                self.assertEqual(import_payload["state"]["status"]["earned_minor"], 4500)
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


if __name__ == "__main__":
    unittest.main()
