from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from divine_tool.core import (
    DivineToolError,
    add_income,
    enqueue_command,
    parse_money_to_minor,
    process_command_inbox,
    set_mood,
    set_quota,
    status_report,
)


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


if __name__ == "__main__":
    unittest.main()
