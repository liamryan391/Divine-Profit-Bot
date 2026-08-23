from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "god_name": "Creator",
    "active_mood": "watchful",
    "base_currency": "GBP",
    "moods": {
        "merciful": {
            "period": "week",
            "quota_minor": 10000,
            "punishment": "review the lowest-return channel and cut wasted effort",
        },
        "watchful": {
            "period": "week",
            "quota_minor": 25000,
            "punishment": "trigger a daily revenue review until the quota recovers",
        },
        "hungry": {
            "period": "month",
            "quota_minor": 150000,
            "punishment": "freeze new features and focus only on revenue actions",
        },
    },
    "channels": [
        {
            "name": "Freelance services",
            "expected_gbp_minor": 25000,
            "effort": "medium",
            "risk": "low",
            "next_action": "Send three tailored proposals or follow-ups.",
        },
        {
            "name": "Digital product",
            "expected_gbp_minor": 10000,
            "effort": "medium",
            "risk": "low",
            "next_action": "Ship one paid mini-offer and test a simple landing page.",
        },
        {
            "name": "Affiliate or referral income",
            "expected_gbp_minor": 5000,
            "effort": "low",
            "risk": "low",
            "next_action": "Publish one honest comparison or recommendation.",
        },
    ],
    "automation": {
        "check_interval_seconds": 300,
        "command_file": "commands.jsonl",
    },
    "ethical_rules": [
        "No theft, fraud, scams, spam, market manipulation, unauthorized access, coercion, or evasion.",
        "No autonomous real-money trading or payments without explicit human approval.",
        "Every income entry should be traceable to a lawful source.",
    ],
}


@dataclass(frozen=True)
class Period:
    name: str
    start: date
    end: date


class DivineToolError(Exception):
    """Raised for user-correctable Divine Tool errors."""


def default_data_dir() -> Path:
    return Path.cwd() / ".divine_tool"


def ensure_state(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = data_dir / "config.json"
    if not config_path.exists():
        save_config(data_dir, DEFAULT_CONFIG)

    with db(data_dir) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS income (
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT NOT NULL,
                starts_on TEXT NOT NULL,
                ends_on TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def connect(data_dir: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(data_dir / "divine_tool.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db(data_dir: Path):
    conn = connect(data_dir)
    try:
        yield conn
    finally:
        conn.close()


def load_config(data_dir: Path) -> dict[str, Any]:
    ensure_config_only(data_dir)
    with (data_dir / "config.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data_dir: Path, config: dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "config.json"
    temp = data_dir / "config.json.tmp"
    with temp.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")
    shutil.move(str(temp), str(target))


def ensure_config_only(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    if not (data_dir / "config.json").exists():
        save_config(data_dir, DEFAULT_CONFIG)


def parse_money_to_minor(value: str | int | float | Decimal) -> int:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise DivineToolError(f"Invalid money amount: {value}") from exc
    return int(amount * 100)


def format_money(minor: int, currency: str = "GBP") -> str:
    symbol = "£" if currency.upper() == "GBP" else f"{currency.upper()} "
    sign = "-" if minor < 0 else ""
    whole = abs(minor) // 100
    pennies = abs(minor) % 100
    return f"{sign}{symbol}{whole:,}.{pennies:02d}"


def period_for(period_name: str, today: date | None = None) -> Period:
    today = today or date.today()
    if period_name == "week":
        start = today - timedelta(days=today.weekday())
        return Period("week", start, start + timedelta(days=7))
    if period_name == "month":
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return Period("month", start, end)
    raise DivineToolError("Period must be 'week' or 'month'.")


def active_mood(config: dict[str, Any]) -> dict[str, Any]:
    mood_name = config.get("active_mood", "watchful")
    moods = config.get("moods", {})
    if mood_name not in moods:
        raise DivineToolError(f"Active mood '{mood_name}' is not configured.")
    mood = dict(moods[mood_name])
    mood["name"] = mood_name
    return mood


def add_income(
    data_dir: Path,
    amount_minor: int,
    currency: str,
    gbp_minor: int | None,
    source: str,
    note: str = "",
    occurred_on: date | None = None,
) -> int:
    ensure_state(data_dir)
    currency = currency.upper()
    if currency != "GBP" and gbp_minor is None:
        raise DivineToolError("Non-GBP income needs a GBP equivalent, for example --gbp-equivalent 42.50.")
    if gbp_minor is None:
        gbp_minor = amount_minor
    occurred = (occurred_on or date.today()).isoformat()
    created = datetime.now().isoformat(timespec="seconds")
    with db(data_dir) as conn:
        cur = conn.execute(
            """
            INSERT INTO income (amount_minor, currency, gbp_minor, source, note, occurred_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (amount_minor, currency, gbp_minor, source, note, occurred, created),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_income(data_dir: Path, limit: int = 20) -> list[sqlite3.Row]:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        return list(
            conn.execute(
                """
                SELECT * FROM income
                ORDER BY occurred_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
        )


def income_total_for_period(data_dir: Path, period: Period) -> int:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(gbp_minor), 0) AS total
            FROM income
            WHERE date(occurred_at) >= date(?) AND date(occurred_at) < date(?)
            """,
            (period.start.isoformat(), period.end.isoformat()),
        ).fetchone()
    return int(row["total"])


def set_mood(data_dir: Path, mood_name: str) -> None:
    config = load_config(data_dir)
    if mood_name not in config.get("moods", {}):
        known = ", ".join(sorted(config.get("moods", {}).keys()))
        raise DivineToolError(f"Unknown mood '{mood_name}'. Known moods: {known}")
    config["active_mood"] = mood_name
    save_config(data_dir, config)


def set_quota(data_dir: Path, mood_name: str, amount_minor: int, period: str) -> None:
    config = load_config(data_dir)
    config.setdefault("moods", {})
    existing = config["moods"].get(mood_name, {})
    existing["period"] = period_for(period).name
    existing["quota_minor"] = amount_minor
    existing.setdefault("punishment", "review revenue actions until the quota recovers")
    config["moods"][mood_name] = existing
    config.setdefault("active_mood", mood_name)
    save_config(data_dir, config)


def add_exception(
    data_dir: Path,
    reason: str,
    starts_on: date | None,
    ends_on: date,
) -> int:
    ensure_state(data_dir)
    start = starts_on or date.today()
    if ends_on < start:
        raise DivineToolError("Exception end date must be on or after the start date.")
    with db(data_dir) as conn:
        cur = conn.execute(
            """
            INSERT INTO exceptions (reason, starts_on, ends_on, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (reason, start.isoformat(), ends_on.isoformat(), datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_exceptions(data_dir: Path, limit: int = 20) -> list[sqlite3.Row]:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        return list(
            conn.execute(
                """
                SELECT * FROM exceptions
                ORDER BY ends_on DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
        )


def active_exception(data_dir: Path, today: date | None = None) -> sqlite3.Row | None:
    ensure_state(data_dir)
    today = (today or date.today()).isoformat()
    with db(data_dir) as conn:
        return conn.execute(
            """
            SELECT * FROM exceptions
            WHERE date(starts_on) <= date(?) AND date(ends_on) >= date(?)
            ORDER BY ends_on DESC
            LIMIT 1
            """,
            (today, today),
        ).fetchone()


def status_report(data_dir: Path, today: date | None = None) -> dict[str, Any]:
    ensure_state(data_dir)
    config = load_config(data_dir)
    mood = active_mood(config)
    period = period_for(mood["period"], today)
    earned = income_total_for_period(data_dir, period)
    quota = int(mood["quota_minor"])
    remaining = max(quota - earned, 0)
    progress = 1.0 if quota <= 0 else min(earned / quota, 1.0)
    days_left = max((period.end - (today or date.today())).days, 0)
    exception = active_exception(data_dir, today)
    if earned >= quota:
        judgement = "quota satisfied"
    elif exception:
        judgement = "exception active"
    elif days_left <= 1 and progress < 0.85:
        judgement = "wrath risk"
    elif progress >= 0.5 or days_left > 2:
        judgement = "on track"
    else:
        judgement = "needs offerings"

    return {
        "god_name": config.get("god_name", "Creator"),
        "mood": mood["name"],
        "period": period,
        "quota_minor": quota,
        "earned_minor": earned,
        "remaining_minor": remaining,
        "progress": progress,
        "days_left": days_left,
        "judgement": judgement,
        "punishment": mood.get("punishment", "review revenue actions"),
        "exception": dict(exception) if exception else None,
        "ethical_rules": config.get("ethical_rules", []),
    }


def generate_opportunities(data_dir: Path, today: date | None = None) -> list[dict[str, str]]:
    report = status_report(data_dir, today)
    config = load_config(data_dir)
    gap = report["remaining_minor"]
    days_left = report["days_left"]
    opportunities: list[dict[str, str]] = []

    for channel in config.get("channels", []):
        expected = int(channel.get("expected_gbp_minor", 0))
        if expected <= 0:
            continue
        fit = "strong" if expected >= gap else "partial"
        opportunities.append(
            {
                "name": channel.get("name", "Revenue channel"),
                "expected": format_money(expected),
                "fit": fit,
                "risk": channel.get("risk", "unknown"),
                "effort": channel.get("effort", "unknown"),
                "next_action": channel.get("next_action", "Define the next concrete revenue action."),
            }
        )

    if gap == 0:
        opportunities.insert(
            0,
            {
                "name": "Quota reached",
                "expected": format_money(0),
                "fit": "upgrade",
                "risk": "low",
                "effort": "low",
                "next_action": "Bank the win, review what worked, then upgrade the highest-return workflow.",
            },
        )
    elif days_left <= 2:
        opportunities.insert(
            0,
            {
                "name": "Urgent cash sprint",
                "expected": format_money(gap),
                "fit": "deadline",
                "risk": "low",
                "effort": "high",
                "next_action": "Prioritize invoices, overdue follow-ups, paid consultations, and fast lawful services.",
            },
        )
    else:
        opportunities.insert(
            0,
            {
                "name": "Revenue compounding",
                "expected": format_money(max(gap // max(days_left, 1), 0)),
                "fit": "daily target",
                "risk": "low",
                "effort": "medium",
                "next_action": "Work the best channel daily and record every conversion in the ledger.",
            },
        )

    return opportunities


def generate_upgrades(data_dir: Path, today: date | None = None) -> list[str]:
    report = status_report(data_dir, today)
    if report["remaining_minor"] == 0:
        return [
            "Unlock payment reminders for invoices and retainers.",
            "Add lead scoring so the highest-value opportunities are contacted first.",
            "Add real currency-rate ingestion with human approval before counting non-GBP income.",
            "Add a local web dashboard for quota progress, command history, and channel ROI.",
            "Add exportable weekly reports for the Creator.",
        ]
    return [
        "Quota is not satisfied yet, so upgrades stay focused on revenue recovery.",
        "Tighten the offer list to one fast paid service and one reusable product.",
        "Add better source notes to each income entry so profitable channels are obvious.",
        "Reduce low-return channels until the current quota is safe.",
    ]


def command_file(data_dir: Path) -> Path:
    config = load_config(data_dir)
    return data_dir / config.get("automation", {}).get("command_file", "commands.jsonl")


def enqueue_command(data_dir: Path, command: dict[str, Any]) -> None:
    ensure_state(data_dir)
    path = command_file(data_dir)
    payload = dict(command)
    payload["queued_at"] = datetime.now().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def process_command(data_dir: Path, command: dict[str, Any]) -> str:
    action = command.get("action")
    if action == "add_income":
        amount_minor = parse_money_to_minor(command["amount"])
        gbp_equivalent = command.get("gbp_equivalent")
        gbp_minor = parse_money_to_minor(gbp_equivalent) if gbp_equivalent is not None else None
        income_id = add_income(
            data_dir,
            amount_minor=amount_minor,
            currency=command.get("currency", "GBP"),
            gbp_minor=gbp_minor,
            source=command.get("source", "command inbox"),
            note=command.get("note", ""),
            occurred_on=parse_date(command.get("date")) if command.get("date") else None,
        )
        return f"added income #{income_id}"
    if action == "set_mood":
        set_mood(data_dir, command["mood"])
        return f"set mood to {command['mood']}"
    if action == "set_quota":
        set_quota(
            data_dir,
            mood_name=command["mood"],
            amount_minor=parse_money_to_minor(command["amount"]),
            period=command.get("period", "week"),
        )
        return f"set {command['mood']} quota"
    if action == "add_exception":
        add_exception(
            data_dir,
            reason=command["reason"],
            starts_on=parse_date(command["from"]) if command.get("from") else None,
            ends_on=parse_date(command["until"]),
        )
        return "added exception"
    raise DivineToolError(f"Unknown command action: {action}")


def process_command_inbox(data_dir: Path) -> list[str]:
    ensure_state(data_dir)
    inbox = command_file(data_dir)
    if not inbox.exists():
        return []

    processed_path = data_dir / "commands.processed.jsonl"
    failed_path = data_dir / "commands.failed.jsonl"
    processing_path = data_dir / f"commands.processing.{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jsonl"
    inbox.replace(processing_path)
    lines = processing_path.read_text(encoding="utf-8").splitlines()
    processing_path.unlink()
    outcomes: list[str] = []

    for raw in lines:
        if not raw.strip():
            continue
        try:
            command = json.loads(raw)
            result = process_command(data_dir, command)
            command["processed_at"] = datetime.now().isoformat(timespec="seconds")
            command["result"] = result
            append_jsonl(processed_path, command)
            outcomes.append(result)
        except Exception as exc:  # keep daemon alive and preserve bad commands
            failed = {"raw": raw, "failed_at": datetime.now().isoformat(timespec="seconds"), "error": str(exc)}
            append_jsonl(failed_path, failed)
            outcomes.append(f"failed command: {exc}")
    return outcomes


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DivineToolError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc
