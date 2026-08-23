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
            "id": "freelance_services",
            "name": "Freelance services",
            "expected_gbp_minor": 25000,
            "effort": "medium",
            "risk": "low",
            "deadline_fit": "high",
            "repeatability": "medium",
            "success_probability": 0.65,
            "next_action": "Send three tailored proposals or follow-ups.",
        },
        {
            "id": "digital_product",
            "name": "Digital product",
            "expected_gbp_minor": 10000,
            "effort": "medium",
            "risk": "low",
            "deadline_fit": "medium",
            "repeatability": "high",
            "success_probability": 0.35,
            "next_action": "Ship one paid mini-offer and test a simple landing page.",
        },
        {
            "id": "affiliate_referral",
            "name": "Affiliate or referral income",
            "expected_gbp_minor": 5000,
            "effort": "low",
            "risk": "low",
            "deadline_fit": "low",
            "repeatability": "medium",
            "success_probability": 0.25,
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
                strategy TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        ensure_column(conn, "income", "strategy", "TEXT NOT NULL DEFAULT ''")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_heartbeat (
                worker_name TEXT PRIMARY KEY,
                last_seen_at TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()


def connect(data_dir: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(data_dir / "divine_tool.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def db(data_dir: Path):
    conn = connect(data_dir)
    try:
        yield conn
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_config(data_dir: Path) -> dict[str, Any]:
    ensure_config_only(data_dir)
    with (data_dir / "config.json").open("r", encoding="utf-8") as f:
        config = json.load(f)
    migrated, changed = migrate_config(config)
    if changed:
        save_config(data_dir, migrated)
    return migrated


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


def migrate_config(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    migrated = dict(config)
    for key, value in DEFAULT_CONFIG.items():
        if key not in migrated:
            migrated[key] = value
            changed = True

    default_channels_by_name = {
        str(channel.get("name", "")).lower(): channel for channel in DEFAULT_CONFIG.get("channels", [])
    }
    channels = []
    for channel in migrated.get("channels", []):
        current = dict(channel)
        default = default_channels_by_name.get(str(current.get("name", "")).lower(), {})
        for key, value in default.items():
            if key not in current:
                current[key] = value
                changed = True
        if "id" not in current:
            current["id"] = slugify(str(current.get("name", "strategy")))
            changed = True
        for key, value in {
            "deadline_fit": "medium",
            "repeatability": "medium",
            "success_probability": 0.5,
        }.items():
            if key not in current:
                current[key] = value
                changed = True
        channels.append(current)
    migrated["channels"] = channels

    return migrated, changed


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def log_event(data_dir: Path, message: str, category: str = "system", level: str = "info") -> int:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        cur = conn.execute(
            """
            INSERT INTO events (level, category, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (level, category, message, now_iso()),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_events(data_dir: Path, limit: int = 50) -> list[sqlite3.Row]:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        return list(
            conn.execute(
                """
                SELECT * FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        )


def record_heartbeat(data_dir: Path, worker_name: str = "daemon", detail: str = "quota check complete") -> None:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        conn.execute(
            """
            INSERT INTO worker_heartbeat (worker_name, last_seen_at, detail)
            VALUES (?, ?, ?)
            ON CONFLICT(worker_name) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                detail = excluded.detail
            """,
            (worker_name, now_iso(), detail),
        )
        conn.commit()


def worker_status(data_dir: Path, worker_name: str = "daemon") -> dict[str, Any]:
    ensure_state(data_dir)
    config = load_config(data_dir)
    interval = int(config.get("automation", {}).get("check_interval_seconds", 300))
    stale_after = max(interval * 2, 60)
    with db(data_dir) as conn:
        row = conn.execute(
            """
            SELECT * FROM worker_heartbeat
            WHERE worker_name = ?
            """,
            (worker_name,),
        ).fetchone()

    if row is None:
        return {
            "worker_name": worker_name,
            "state": "not started",
            "last_seen_at": None,
            "age_seconds": None,
            "detail": "",
            "stale_after_seconds": stale_after,
        }

    last_seen = datetime.fromisoformat(row["last_seen_at"])
    age = max(int((datetime.now() - last_seen).total_seconds()), 0)
    return {
        "worker_name": worker_name,
        "state": "running" if age <= stale_after else "stale",
        "last_seen_at": row["last_seen_at"],
        "age_seconds": age,
        "detail": row["detail"],
        "stale_after_seconds": stale_after,
    }


def parse_money_to_minor(value: str | int | float | Decimal) -> int:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise DivineToolError(f"Invalid money amount: {value}") from exc
    return int(amount * 100)


def slugify(value: str) -> str:
    output = []
    previous_was_sep = False
    for char in value.lower():
        if char.isalnum():
            output.append(char)
            previous_was_sep = False
        elif not previous_was_sep:
            output.append("_")
            previous_was_sep = True
    return "".join(output).strip("_") or "strategy"


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


def previous_period(period: Period) -> Period:
    if period.name == "week":
        start = period.start - timedelta(days=7)
        return Period("week", start, period.start)
    if period.name == "month":
        end = period.start
        if end.month == 1:
            start = end.replace(year=end.year - 1, month=12)
        else:
            start = end.replace(month=end.month - 1)
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
    strategy: str = "",
    occurred_on: date | None = None,
) -> int:
    ensure_state(data_dir)
    currency = currency.upper()
    if currency != "GBP" and gbp_minor is None:
        raise DivineToolError("Non-GBP income needs a GBP equivalent, for example --gbp-equivalent 42.50.")
    if gbp_minor is None:
        gbp_minor = amount_minor
    occurred = (occurred_on or date.today()).isoformat()
    created = now_iso()
    with db(data_dir) as conn:
        cur = conn.execute(
            """
            INSERT INTO income (amount_minor, currency, gbp_minor, strategy, source, note, occurred_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (amount_minor, currency, gbp_minor, strategy, source, note, occurred, created),
        )
        conn.commit()
        income_id = int(cur.lastrowid)
    strategy_suffix = f" [{strategy}]" if strategy else ""
    log_event(data_dir, f"Income recorded: {format_money(gbp_minor)} from {source}{strategy_suffix}", "income")
    return income_id


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


def strategy_income_totals(data_dir: Path, period: Period) -> dict[str, dict[str, int]]:
    ensure_state(data_dir)
    totals: dict[str, dict[str, int]] = {}
    with db(data_dir) as conn:
        period_rows = conn.execute(
            """
            SELECT strategy, COALESCE(SUM(gbp_minor), 0) AS total, COUNT(*) AS count
            FROM income
            WHERE strategy <> '' AND date(occurred_at) >= date(?) AND date(occurred_at) < date(?)
            GROUP BY strategy
            """,
            (period.start.isoformat(), period.end.isoformat()),
        ).fetchall()
        all_rows = conn.execute(
            """
            SELECT strategy, COALESCE(SUM(gbp_minor), 0) AS total, COUNT(*) AS count
            FROM income
            WHERE strategy <> ''
            GROUP BY strategy
            """
        ).fetchall()

    for row in period_rows:
        totals.setdefault(row["strategy"], {"period_minor": 0, "period_count": 0, "total_minor": 0, "total_count": 0})
        totals[row["strategy"]]["period_minor"] = int(row["total"])
        totals[row["strategy"]]["period_count"] = int(row["count"])

    for row in all_rows:
        totals.setdefault(row["strategy"], {"period_minor": 0, "period_count": 0, "total_minor": 0, "total_count": 0})
        totals[row["strategy"]]["total_minor"] = int(row["total"])
        totals[row["strategy"]]["total_count"] = int(row["count"])

    return totals


def strategy_period_totals(data_dir: Path, period: Period) -> dict[str, dict[str, int]]:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        rows = conn.execute(
            """
            SELECT strategy, COALESCE(SUM(gbp_minor), 0) AS total, COUNT(*) AS count
            FROM income
            WHERE strategy <> '' AND date(occurred_at) >= date(?) AND date(occurred_at) < date(?)
            GROUP BY strategy
            """,
            (period.start.isoformat(), period.end.isoformat()),
        ).fetchall()
    return {row["strategy"]: {"minor": int(row["total"]), "count": int(row["count"])} for row in rows}


def strategy_recent_notes(data_dir: Path, limit_per_strategy: int = 3) -> dict[str, list[dict[str, Any]]]:
    ensure_state(data_dir)
    notes: dict[str, list[dict[str, Any]]] = {}
    with db(data_dir) as conn:
        rows = conn.execute(
            """
            SELECT strategy, source, note, gbp_minor, occurred_at
            FROM income
            WHERE strategy <> ''
            ORDER BY date(occurred_at) DESC, id DESC
            """
        ).fetchall()
    for row in rows:
        strategy = row["strategy"]
        bucket = notes.setdefault(strategy, [])
        if len(bucket) >= limit_per_strategy:
            continue
        note = row["note"] or row["source"]
        bucket.append(
            {
                "source": row["source"],
                "note": note,
                "amount": format_money(int(row["gbp_minor"])),
                "amount_minor": int(row["gbp_minor"]),
                "occurred_at": row["occurred_at"],
            }
        )
    return notes


def strategy_roi_summary(data_dir: Path, today: date | None = None) -> dict[str, Any]:
    report = status_report(data_dir, today)
    config = load_config(data_dir)
    period = report["period"]
    previous = previous_period(period)
    current_totals = strategy_period_totals(data_dir, period)
    previous_totals = strategy_period_totals(data_dir, previous)
    all_totals = strategy_income_totals(data_dir, period)
    notes = strategy_recent_notes(data_dir)
    opportunities_by_id = {item["id"]: item for item in generate_opportunities(data_dir, today)}
    rows: list[dict[str, Any]] = []

    for channel in config.get("channels", []):
        strategy_id = str(channel.get("id") or slugify(channel.get("name", "Revenue channel")))
        expected = int(channel.get("expected_gbp_minor", 0))
        effort = str(channel.get("effort", "medium"))
        effort_units = {"low": 1, "medium": 2, "high": 3}.get(effort, 2)
        current = current_totals.get(strategy_id, {"minor": 0, "count": 0})
        previous_total = previous_totals.get(strategy_id, {"minor": 0, "count": 0})
        lifetime = all_totals.get(strategy_id, {"period_minor": 0, "period_count": 0, "total_minor": 0, "total_count": 0})
        current_minor = current["minor"]
        previous_minor = previous_total["minor"]
        delta_minor = current_minor - previous_minor
        avg_entry_minor = round(current_minor / current["count"]) if current["count"] else 0
        roi_per_effort_minor = round(current_minor / effort_units)
        target_capture = 0 if expected <= 0 else min(current_minor / expected, 1)
        opportunity = opportunities_by_id.get(strategy_id, {})
        trend = roi_trend(current_minor, previous_minor)
        action, reason = roi_recommendation(
            expected_minor=expected,
            current_minor=current_minor,
            previous_minor=previous_minor,
            current_count=current["count"],
            total_count=lifetime["total_count"],
            score=int(opportunity.get("score", 0)),
            effort=effort,
            risk=str(channel.get("risk", "moderate")),
        )

        rows.append(
            {
                "id": strategy_id,
                "name": channel.get("name", "Revenue channel"),
                "effort": effort,
                "risk": channel.get("risk", "unknown"),
                "expected": format_money(expected),
                "expected_minor": expected,
                "current_period": format_money(current_minor),
                "current_period_minor": current_minor,
                "current_count": current["count"],
                "previous_period": format_money(previous_minor),
                "previous_period_minor": previous_minor,
                "previous_count": previous_total["count"],
                "delta": format_money(delta_minor),
                "delta_minor": delta_minor,
                "total_income": format_money(lifetime["total_minor"]),
                "total_income_minor": lifetime["total_minor"],
                "total_count": lifetime["total_count"],
                "average_entry": format_money(avg_entry_minor),
                "average_entry_minor": avg_entry_minor,
                "roi_per_effort": format_money(roi_per_effort_minor),
                "roi_per_effort_minor": roi_per_effort_minor,
                "target_capture_pct": round(target_capture * 100, 1),
                "trend": trend,
                "score": int(opportunity.get("score", 0)),
                "recommendation": action,
                "recommendation_reason": reason,
                "notes": notes.get(strategy_id, []),
            }
        )

    rows.sort(key=lambda row: (row["roi_per_effort_minor"], row["current_period_minor"], row["score"]), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["roi_rank"] = index

    pause_recommendations = [row for row in rows if row["recommendation"] == "pause"]
    push_recommendations = [row for row in rows if row["recommendation"] == "push"]
    return {
        "period": {
            "name": period.name,
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
        },
        "previous_period": {
            "name": previous.name,
            "start": previous.start.isoformat(),
            "end": previous.end.isoformat(),
        },
        "rows": rows,
        "pause_recommendations": pause_recommendations,
        "push_recommendations": push_recommendations,
    }


def roi_trend(current_minor: int, previous_minor: int) -> str:
    if current_minor == 0 and previous_minor == 0:
        return "no evidence"
    if previous_minor == 0:
        return "new revenue"
    change = (current_minor - previous_minor) / previous_minor
    if change >= 0.2:
        return "growing"
    if change <= -0.2:
        return "falling"
    return "steady"


def roi_recommendation(
    expected_minor: int,
    current_minor: int,
    previous_minor: int,
    current_count: int,
    total_count: int,
    score: int,
    effort: str,
    risk: str,
) -> tuple[str, str]:
    if current_minor >= expected_minor and expected_minor > 0:
        return "push", "It is meeting or beating the expected period value."
    if current_minor > previous_minor and current_count > 0:
        return "push", "It is improving against the previous period."
    if current_count == 0 and previous_minor == 0 and total_count == 0 and score < 65:
        return "pause", "No recorded income yet and the opportunity score is below the push threshold."
    if effort == "high" and current_minor == 0 and total_count == 0:
        return "pause", "High effort with no recorded return."
    if risk != "low" and current_minor == 0:
        return "pause", "Risk is not low and no return has been recorded."
    if current_minor == 0 and previous_minor > 0:
        return "watch", "It produced income before but has not converted this period."
    return "watch", "Keep collecting evidence before changing priority."


def set_mood(data_dir: Path, mood_name: str) -> None:
    config = load_config(data_dir)
    if mood_name not in config.get("moods", {}):
        known = ", ".join(sorted(config.get("moods", {}).keys()))
        raise DivineToolError(f"Unknown mood '{mood_name}'. Known moods: {known}")
    config["active_mood"] = mood_name
    save_config(data_dir, config)
    log_event(data_dir, f"Mood changed to {mood_name}", "config")


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
    log_event(data_dir, f"{mood_name} quota set to {format_money(amount_minor)} per {period}", "config")


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
            (reason, start.isoformat(), ends_on.isoformat(), now_iso()),
        )
        conn.commit()
        exception_id = int(cur.lastrowid)
    log_event(data_dir, f"Exception added until {ends_on.isoformat()}: {reason}", "exception")
    return exception_id


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


def generate_opportunities(data_dir: Path, today: date | None = None) -> list[dict[str, Any]]:
    report = status_report(data_dir, today)
    config = load_config(data_dir)
    period = report["period"]
    gap = int(report["remaining_minor"])
    days_left = int(report["days_left"])
    totals = strategy_income_totals(data_dir, period)
    opportunities: list[dict[str, Any]] = []

    for channel in config.get("channels", []):
        expected = int(channel.get("expected_gbp_minor", 0))
        if expected <= 0:
            continue
        strategy_id = str(channel.get("id") or slugify(channel.get("name", "Revenue channel")))
        income = totals.get(strategy_id, {"period_minor": 0, "period_count": 0, "total_minor": 0, "total_count": 0})
        components = opportunity_score_components(channel, expected, gap, days_left, income)
        score = min(sum(components.values()), 100)
        fit = "strong" if expected >= gap else "partial"
        if gap == 0:
            fit = "upgrade"
        elif days_left <= 2 and channel.get("deadline_fit", "medium") == "high":
            fit = "deadline"
        opportunities.append(
            {
                "id": strategy_id,
                "name": channel.get("name", "Revenue channel"),
                "expected": format_money(expected),
                "expected_minor": expected,
                "fit": fit,
                "risk": channel.get("risk", "unknown"),
                "effort": channel.get("effort", "unknown"),
                "deadline_fit": channel.get("deadline_fit", "medium"),
                "repeatability": channel.get("repeatability", "medium"),
                "success_probability": float(channel.get("success_probability", 0.5)),
                "score": score,
                "score_label": score_label(score),
                "period_income": format_money(income["period_minor"]),
                "period_income_minor": income["period_minor"],
                "period_count": income["period_count"],
                "total_income": format_money(income["total_minor"]),
                "total_income_minor": income["total_minor"],
                "total_count": income["total_count"],
                "components": components,
                "rationale": opportunity_rationale(channel, components, income, gap, days_left),
                "next_action": channel.get("next_action", "Define the next concrete revenue action."),
            }
        )

    opportunities.sort(key=lambda item: (item["score"], item["expected_minor"]), reverse=True)
    for index, item in enumerate(opportunities, start=1):
        item["rank"] = index
    return opportunities


def opportunity_score_components(
    channel: dict[str, Any],
    expected_minor: int,
    gap_minor: int,
    days_left: int,
    income: dict[str, int],
) -> dict[str, int]:
    target = max(gap_minor, 1)
    if gap_minor == 0:
        value_score = min(round(expected_minor / 10000 * 8), 30)
    else:
        value_score = min(round(expected_minor / target * 30), 30)

    effort_score = {"low": 16, "medium": 11, "high": 6}.get(str(channel.get("effort", "medium")), 8)
    risk_score = {"low": 16, "moderate": 10, "high": 4}.get(str(channel.get("risk", "moderate")), 8)
    repeatability_score = {"high": 12, "medium": 8, "low": 4}.get(str(channel.get("repeatability", "medium")), 6)
    deadline_score = deadline_component(str(channel.get("deadline_fit", "medium")), days_left)
    probability_score = min(round(float(channel.get("success_probability", 0.5)) * 10), 10)
    evidence_score = min(round(income["period_minor"] / max(expected_minor, 1) * 8), 8)
    if income["period_minor"] == 0 and income["total_minor"] > 0:
        evidence_score = min(round(income["total_minor"] / max(expected_minor * 4, 1) * 4), 4)

    return {
        "value": value_score,
        "deadline": deadline_score,
        "effort": effort_score,
        "risk": risk_score,
        "repeatability": repeatability_score,
        "probability": probability_score,
        "evidence": evidence_score,
    }


def deadline_component(deadline_fit: str, days_left: int) -> int:
    if days_left <= 2:
        return {"high": 18, "medium": 12, "low": 5}.get(deadline_fit, 9)
    if days_left <= 5:
        return {"high": 16, "medium": 13, "low": 8}.get(deadline_fit, 10)
    return {"high": 13, "medium": 12, "low": 10}.get(deadline_fit, 10)


def score_label(score: int) -> str:
    if score >= 80:
        return "prime offering"
    if score >= 65:
        return "strong offering"
    if score >= 50:
        return "viable offering"
    return "watchlist"


def opportunity_rationale(
    channel: dict[str, Any],
    components: dict[str, int],
    income: dict[str, int],
    gap_minor: int,
    days_left: int,
) -> str:
    reasons = []
    if components["value"] >= 24:
        reasons.append("can cover a large share of the remaining quota")
    if components["deadline"] >= 16:
        reasons.append("fits the current deadline pressure")
    if components["effort"] >= 16:
        reasons.append("has low activation effort")
    if components["risk"] >= 16:
        reasons.append("has low operational risk")
    if components["repeatability"] >= 12:
        reasons.append("is repeatable after this period")
    if income["period_minor"] > 0:
        reasons.append(f"already produced {format_money(income['period_minor'])} this period")
    elif income["total_minor"] > 0:
        reasons.append(f"has produced {format_money(income['total_minor'])} historically")
    if not reasons:
        reasons.append("needs evidence before promotion")

    urgency = "quota is satisfied" if gap_minor == 0 else f"{days_left} day{'s' if days_left != 1 else ''} left"
    return f"{channel.get('name', 'This strategy')} ranks here because it {', '.join(reasons)}; {urgency}."


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
    payload["queued_at"] = now_iso()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")
    log_event(data_dir, f"Command queued: {payload.get('action', 'unknown')}", "command")


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
            strategy=command.get("strategy", ""),
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
            command["processed_at"] = now_iso()
            command["result"] = result
            append_jsonl(processed_path, command)
            log_event(data_dir, f"Command processed: {result}", "command")
            outcomes.append(result)
        except Exception as exc:  # keep daemon alive and preserve bad commands
            failed = {"raw": raw, "failed_at": now_iso(), "error": str(exc)}
            append_jsonl(failed_path, failed)
            log_event(data_dir, f"Command failed: {exc}", "command", "error")
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
