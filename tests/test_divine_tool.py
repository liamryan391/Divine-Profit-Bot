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
    load_config,
    parse_money_to_minor,
    process_command_inbox,
    set_mood,
    set_quota,
    status_report,
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
            set_quota(data_dir, "watchful", parse_money_to_minor("100"), "week")
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


if __name__ == "__main__":
    unittest.main()
