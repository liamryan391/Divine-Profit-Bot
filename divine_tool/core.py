from __future__ import annotations

import base64
import copy
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import shutil
import sqlite3
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable


DEFAULT_CONFIG: dict[str, Any] = {
    "god_name": "Creator",
    "active_temple": "main",
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
    "temples": [
        {
            "id": "main",
            "name": "Main Temple",
            "description": "Primary revenue temple for the Creator.",
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
        }
    ],
    "strategy_templates": {
        "balanced": {
            "label": "Balanced revenue mix",
            "channels": ["freelance_services", "digital_product", "affiliate_referral"],
        },
        "services": {
            "label": "Service-led temple",
            "channels": ["freelance_services"],
        },
        "products": {
            "label": "Product-led temple",
            "channels": ["digital_product", "affiliate_referral"],
        },
    },
    "automation": {
        "check_interval_seconds": 300,
        "command_file": "commands.jsonl",
    },
    "integrations": {
        "currency_rates": {
            "enabled": True,
            "provider": "frankfurter",
            "base_url": "https://api.frankfurter.dev/v2",
            "base_currency": "GBP",
            "targets": ["USD", "EUR"],
        },
        "github": {
            "enabled": True,
            "repository": "liamryan391/Divine-Profit-Bot",
            "lookback_days": 7,
        },
        "payments": {
            "enabled": False,
            "provider": "stripe",
            "env_var": "DIVINE_STRIPE_SECRET_KEY",
            "limit": 10,
            "summary_file": "",
        },
        "product_analytics": {
            "enabled": False,
            "summary_file": "",
        },
    },
    "auth": {
        "enabled": True,
        "session_ttl_hours": 12,
        "password_min_length": 10,
        "secret_management": {
            "policy": "Keep API keys and payment credentials in environment variables, not config files.",
            "allowed_env_vars": ["DIVINE_STRIPE_SECRET_KEY", "DIVINE_GITHUB_TOKEN", "GITHUB_TOKEN"],
        },
    },
    "deployment": {
        "mode": "local",
        "public_url": "",
        "health_path": "/api/health",
        "backup": {
            "enabled": True,
            "directory": "backups",
            "retain_count": 7,
        },
        "background_job": {
            "service_name": "divine-daemon",
            "restart_policy": "unless-stopped",
        },
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


APPROVAL_KINDS = {
    "invoice_reminder": "Invoice Reminder",
    "outreach": "Outreach Message",
    "content_prompt": "Content Prompt",
}

APPROVAL_STATUSES = {"pending", "approved", "rejected", "completed"}
DEFAULT_TEMPLE_ID = "main"


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
                temple_id TEXT NOT NULL DEFAULT 'main',
                amount_minor INTEGER NOT NULL,
                currency TEXT NOT NULL,
                gbp_minor INTEGER NOT NULL,
                strategy TEXT NOT NULL DEFAULT '',
                import_fingerprint TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        ensure_column(conn, "income", "temple_id", "TEXT NOT NULL DEFAULT 'main'")
        ensure_column(conn, "income", "strategy", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "income", "import_fingerprint", "TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_income_temple_period ON income(temple_id, occurred_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_income_import_fingerprint ON income(import_fingerprint)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temple_id TEXT NOT NULL DEFAULT 'main',
                reason TEXT NOT NULL,
                starts_on TEXT NOT NULL,
                ends_on TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        ensure_column(conn, "exceptions", "temple_id", "TEXT NOT NULL DEFAULT 'main'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exceptions_temple_dates ON exceptions(temple_id, starts_on, ends_on)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temple_id TEXT NOT NULL DEFAULT 'main',
                level TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        ensure_column(conn, "events", "temple_id", "TEXT NOT NULL DEFAULT 'main'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_temple_created ON events(temple_id, created_at)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_heartbeat (
                worker_name TEXT PRIMARY KEY,
                last_seen_at TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temple_id TEXT NOT NULL DEFAULT 'main',
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT '',
                strategy TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                reviewed_at TEXT NOT NULL DEFAULT '',
                decision_note TEXT NOT NULL DEFAULT ''
            )
            """
        )
        ensure_column(conn, "approval_actions", "temple_id", "TEXT NOT NULL DEFAULT 'main'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_approval_actions_status ON approval_actions(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_approval_actions_temple_status ON approval_actions(temple_id, status)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'owner',
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL DEFAULT '',
                disabled INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                account_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                user_agent TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_account ON auth_sessions(account_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires ON auth_sessions(expires_at)")
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


def normalize_temple_id(value: str) -> str:
    cleaned = slugify(value.strip())
    if len(cleaned) < 2:
        raise DivineToolError("Temple id must be at least 2 characters.")
    return cleaned


def migrate_channels(channels: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    changed = False
    default_channels_by_name = {
        str(channel.get("name", "")).lower(): channel for channel in DEFAULT_CONFIG.get("channels", [])
    }
    output = []
    for channel in channels:
        current = dict(channel)
        default = default_channels_by_name.get(str(current.get("name", "")).lower(), {})
        for key, value in default.items():
            if key not in current:
                current[key] = copy.deepcopy(value)
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
        output.append(current)
    return output, changed


def legacy_temple_from_config(config: dict[str, Any], temple_id: str | None = None) -> dict[str, Any]:
    return {
        "id": normalize_temple_id(temple_id or str(config.get("active_temple") or DEFAULT_TEMPLE_ID)),
        "name": "Main Temple",
        "description": "Primary revenue temple for the Creator.",
        "active_mood": config.get("active_mood", "watchful"),
        "base_currency": config.get("base_currency", "GBP"),
        "moods": copy.deepcopy(config.get("moods", DEFAULT_CONFIG["moods"])),
        "channels": copy.deepcopy(config.get("channels", DEFAULT_CONFIG["channels"])),
    }


def normalize_temple_config(temple: dict[str, Any], fallback: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    current = dict(temple)
    if not current.get("id"):
        current["id"] = normalize_temple_id(str(current.get("name") or DEFAULT_TEMPLE_ID))
        changed = True
    else:
        normalized = normalize_temple_id(str(current["id"]))
        if current["id"] != normalized:
            current["id"] = normalized
            changed = True
    if not current.get("name"):
        current["name"] = str(current["id"]).replace("_", " ").title()
        changed = True
    current.setdefault("description", "")
    if "active_mood" not in current:
        current["active_mood"] = fallback.get("active_mood", "watchful")
        changed = True
    if "base_currency" not in current:
        current["base_currency"] = fallback.get("base_currency", "GBP")
        changed = True
    if "moods" not in current:
        current["moods"] = copy.deepcopy(fallback.get("moods", DEFAULT_CONFIG["moods"]))
        changed = True
    if "channels" not in current:
        current["channels"] = copy.deepcopy(fallback.get("channels", DEFAULT_CONFIG["channels"]))
        changed = True
    channels, channel_changed = migrate_channels(list(current.get("channels", [])))
    current["channels"] = channels
    changed = changed or channel_changed
    if current["active_mood"] not in current.get("moods", {}):
        current["active_mood"] = next(iter(current.get("moods", {}) or {"watchful": {}}))
        changed = True
    return current, changed


def sync_active_temple_legacy_fields(config: dict[str, Any]) -> None:
    temple = active_temple_config(config)
    config["active_temple"] = temple["id"]
    config["active_mood"] = temple.get("active_mood", "watchful")
    config["base_currency"] = temple.get("base_currency", "GBP")
    config["moods"] = copy.deepcopy(temple.get("moods", DEFAULT_CONFIG["moods"]))
    config["channels"] = copy.deepcopy(temple.get("channels", DEFAULT_CONFIG["channels"]))


def active_temple_config(config: dict[str, Any], temple_id: str | None = None) -> dict[str, Any]:
    requested = normalize_temple_id(temple_id or str(config.get("active_temple") or DEFAULT_TEMPLE_ID))
    for temple in config.get("temples", []):
        if str(temple.get("id")) == requested:
            return dict(temple)
    raise DivineToolError(f"Unknown temple '{requested}'.")


def active_temple_id_for_data_dir(data_dir: Path, temple_id: str | None = None) -> str:
    if temple_id:
        return normalize_temple_id(temple_id)
    config = load_config(data_dir)
    return str(active_temple_config(config)["id"])


def migrate_config(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    migrated = dict(config)
    for key, value in DEFAULT_CONFIG.items():
        if key not in migrated:
            migrated[key] = value
            changed = True

    channels, channels_changed = migrate_channels(list(migrated.get("channels", [])))
    changed = changed or channels_changed
    migrated["channels"] = channels

    default_integrations = DEFAULT_CONFIG.get("integrations", {})
    current_integrations = dict(migrated.get("integrations", {}))
    for name, defaults in default_integrations.items():
        if name not in current_integrations:
            current_integrations[name] = defaults
            changed = True
            continue
        if isinstance(defaults, dict):
            current = dict(current_integrations.get(name, {}))
            for key, value in defaults.items():
                if key not in current:
                    current[key] = value
                    changed = True
            current_integrations[name] = current
    migrated["integrations"] = current_integrations

    default_auth = DEFAULT_CONFIG.get("auth", {})
    current_auth = dict(migrated.get("auth", {}))
    for key, value in default_auth.items():
        if key not in current_auth:
            current_auth[key] = value
            changed = True
            continue
        if isinstance(value, dict):
            nested = dict(current_auth.get(key, {}))
            for nested_key, nested_value in value.items():
                if nested_key not in nested:
                    nested[nested_key] = nested_value
                    changed = True
            current_auth[key] = nested
    migrated["auth"] = current_auth

    default_deployment = DEFAULT_CONFIG.get("deployment", {})
    current_deployment = dict(migrated.get("deployment", {}))
    for key, value in default_deployment.items():
        if key not in current_deployment:
            current_deployment[key] = value
            changed = True
            continue
        if isinstance(value, dict):
            nested = dict(current_deployment.get(key, {}))
            for nested_key, nested_value in value.items():
                if nested_key not in nested:
                    nested[nested_key] = nested_value
                    changed = True
            current_deployment[key] = nested
    migrated["deployment"] = current_deployment

    active_temple = normalize_temple_id(str(migrated.get("active_temple") or DEFAULT_TEMPLE_ID))
    migrated["active_temple"] = active_temple
    temples_input = migrated.get("temples") or []
    if not temples_input:
        temples_input = [legacy_temple_from_config(migrated, active_temple)]
        changed = True

    temples = []
    seen_temples: set[str] = set()
    for temple in temples_input:
        if not isinstance(temple, dict):
            changed = True
            continue
        normalized, temple_changed = normalize_temple_config(temple, migrated)
        changed = changed or temple_changed
        if normalized["id"] in seen_temples:
            changed = True
            continue
        seen_temples.add(normalized["id"])
        temples.append(normalized)

    if active_temple not in seen_temples:
        temples.insert(0, legacy_temple_from_config(migrated, active_temple))
        changed = True

    migrated["temples"] = temples
    sync_active_temple_legacy_fields(migrated)

    return migrated, changed


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def list_temples(data_dir: Path) -> list[dict[str, Any]]:
    config = load_config(data_dir)
    active_id = str(active_temple_config(config)["id"])
    temples = []
    for temple in config.get("temples", []):
        temples.append(
            {
                "id": temple["id"],
                "name": temple.get("name", temple["id"]),
                "description": temple.get("description", ""),
                "active": temple["id"] == active_id,
                "active_mood": temple.get("active_mood", "watchful"),
                "base_currency": temple.get("base_currency", "GBP"),
                "channel_count": len(temple.get("channels", [])),
            }
        )
    return temples


def strategy_template_channels(config: dict[str, Any], template: str) -> list[dict[str, Any]]:
    template_id = str(template or "balanced").strip().lower()
    templates = config.get("strategy_templates", {})
    if template_id not in templates:
        known = ", ".join(sorted(templates.keys()))
        raise DivineToolError(f"Unknown strategy template '{template_id}'. Known templates: {known}")
    channel_ids = list(templates[template_id].get("channels", []))
    channels_by_id = {
        str(channel.get("id") or slugify(str(channel.get("name", "strategy")))): channel
        for channel in DEFAULT_CONFIG.get("channels", [])
    }
    for channel in config.get("channels", []):
        channel_id = str(channel.get("id") or slugify(str(channel.get("name", "strategy"))))
        channels_by_id.setdefault(channel_id, channel)
    return [copy.deepcopy(channels_by_id[channel_id]) for channel_id in channel_ids if channel_id in channels_by_id]


def create_temple(
    data_dir: Path,
    name: str,
    temple_id: str = "",
    description: str = "",
    template: str = "balanced",
) -> dict[str, Any]:
    config = load_config(data_dir)
    cleaned_name = name.strip()
    if len(cleaned_name) < 2:
        raise DivineToolError("Temple name must be at least 2 characters.")
    new_id = normalize_temple_id(temple_id or cleaned_name)
    if any(temple["id"] == new_id for temple in config.get("temples", [])):
        raise DivineToolError(f"Temple '{new_id}' already exists.")

    temple = {
        "id": new_id,
        "name": cleaned_name,
        "description": description.strip(),
        "active_mood": "watchful",
        "base_currency": config.get("base_currency", "GBP"),
        "moods": copy.deepcopy(DEFAULT_CONFIG["moods"]),
        "channels": strategy_template_channels(config, template),
    }
    normalized, _changed = normalize_temple_config(temple, config)
    config.setdefault("temples", []).append(normalized)
    save_config(data_dir, config)
    log_event(data_dir, f"Temple created: {normalized['name']}", "temple", temple_id=new_id)
    return temple_to_dict(normalized, active=False)


def switch_temple(data_dir: Path, temple_id: str) -> dict[str, Any]:
    config = load_config(data_dir)
    requested = normalize_temple_id(temple_id)
    temple = active_temple_config(config, requested)
    config["active_temple"] = requested
    sync_active_temple_legacy_fields(config)
    save_config(data_dir, config)
    log_event(data_dir, f"Active temple switched to {temple['name']}", "temple", temple_id=requested)
    return temple_to_dict(temple, active=True)


def temple_to_dict(temple: dict[str, Any], active: bool) -> dict[str, Any]:
    return {
        "id": temple["id"],
        "name": temple.get("name", temple["id"]),
        "description": temple.get("description", ""),
        "active": active,
        "active_mood": temple.get("active_mood", "watchful"),
        "base_currency": temple.get("base_currency", "GBP"),
        "channel_count": len(temple.get("channels", [])),
    }


def temple_summary(data_dir: Path, today: date | None = None) -> dict[str, Any]:
    config = load_config(data_dir)
    active_id = str(active_temple_config(config)["id"])
    rows = []
    total_quota_minor = 0
    total_earned_minor = 0
    satisfied_count = 0
    risk_count = 0

    for temple in config.get("temples", []):
        report = status_report(data_dir, today=today, temple_id=str(temple["id"]))
        top = generate_opportunities(data_dir, today=today, temple_id=str(temple["id"]))
        quota_minor = int(report["quota_minor"])
        earned_minor = int(report["earned_minor"])
        total_quota_minor += quota_minor
        total_earned_minor += earned_minor
        if report["judgement"] == "quota satisfied":
            satisfied_count += 1
        if report["judgement"] in {"wrath risk", "needs offerings"}:
            risk_count += 1
        rows.append(
            {
                "id": temple["id"],
                "name": temple.get("name", temple["id"]),
                "description": temple.get("description", ""),
                "active": temple["id"] == active_id,
                "mood": report["mood"],
                "period": {
                    "name": report["period"].name,
                    "start": report["period"].start.isoformat(),
                    "end": report["period"].end.isoformat(),
                },
                "quota": format_money(quota_minor),
                "quota_minor": quota_minor,
                "earned": format_money(earned_minor),
                "earned_minor": earned_minor,
                "remaining": format_money(int(report["remaining_minor"])),
                "remaining_minor": int(report["remaining_minor"]),
                "progress_pct": round(float(report["progress"]) * 100, 1),
                "judgement": report["judgement"],
                "top_strategy": top[0]["name"] if top else "No strategy",
            }
        )

    return {
        "active_temple_id": active_id,
        "temple_count": len(rows),
        "satisfied_count": satisfied_count,
        "risk_count": risk_count,
        "total_quota": format_money(total_quota_minor),
        "total_quota_minor": total_quota_minor,
        "total_earned": format_money(total_earned_minor),
        "total_earned_minor": total_earned_minor,
        "total_remaining": format_money(max(total_quota_minor - total_earned_minor, 0)),
        "total_remaining_minor": max(total_quota_minor - total_earned_minor, 0),
        "overall_progress_pct": 100.0
        if total_quota_minor <= 0
        else round(min(total_earned_minor / total_quota_minor, 1) * 100, 1),
        "rows": rows,
    }


def log_event(
    data_dir: Path,
    message: str,
    category: str = "system",
    level: str = "info",
    temple_id: str | None = None,
) -> int:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        cur = conn.execute(
            """
            INSERT INTO events (temple_id, level, category, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scoped_temple_id, level, category, message, now_iso()),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_events(data_dir: Path, limit: int = 50, temple_id: str | None = None) -> list[sqlite3.Row]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        return list(
            conn.execute(
                """
                SELECT * FROM events
                WHERE temple_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (scoped_temple_id, limit),
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


def normalize_header(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def first_present(row: dict[str, str], candidates: list[str]) -> str:
    normalized = {normalize_header(key): value for key, value in row.items()}
    for candidate in candidates:
        value = normalized.get(normalize_header(candidate), "")
        if str(value).strip():
            return str(value).strip()
    return ""


def clean_money_value(value: str) -> str:
    cleaned = str(value).strip()
    is_parenthesized_negative = cleaned.startswith("(") and cleaned.endswith(")")
    if is_parenthesized_negative:
        cleaned = cleaned[1:-1]
    for char in ["£", "$", "€", ","]:
        cleaned = cleaned.replace(char, "")
    for token in ["GBP", "USD", "EUR", "BTC", "LTC", "XMR"]:
        cleaned = cleaned.replace(token, "").replace(token.lower(), "")
    cleaned = cleaned.strip()
    if is_parenthesized_negative:
        cleaned = f"-{cleaned}"
    return cleaned


def parse_import_date(value: str) -> date:
    raw = str(value).strip()
    try:
        return parse_date(raw)
    except DivineToolError:
        pass

    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise DivineToolError(f"Invalid import date '{value}'. Use YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, or DD Mon YYYY.")


def income_fingerprint(
    amount_minor: int,
    currency: str,
    gbp_minor: int,
    strategy: str,
    source: str,
    note: str,
    occurred_at: str,
    external_id: str = "",
) -> str:
    payload = "|".join(
        [
            str(amount_minor),
            currency.upper(),
            str(gbp_minor),
            strategy.strip().lower(),
            source.strip().lower(),
            note.strip().lower(),
            occurred_at,
            external_id.strip().lower(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def active_mood(config: dict[str, Any], temple_id: str | None = None) -> dict[str, Any]:
    temple = active_temple_config(config, temple_id)
    mood_name = temple.get("active_mood", "watchful")
    moods = temple.get("moods", {})
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
    import_fingerprint: str = "",
    occurred_on: date | None = None,
    temple_id: str | None = None,
) -> int:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    currency = currency.upper()
    if currency != "GBP" and gbp_minor is None:
        raise DivineToolError("Non-GBP income needs a GBP equivalent, for example --gbp-equivalent 42.50.")
    if gbp_minor is None:
        gbp_minor = amount_minor
    occurred = (occurred_on or date.today()).isoformat()
    created = now_iso()
    with db(data_dir) as conn:
        if import_fingerprint:
            existing = conn.execute(
                """
                SELECT id FROM income
                WHERE import_fingerprint = ? AND temple_id = ?
                LIMIT 1
                """,
                (import_fingerprint, scoped_temple_id),
            ).fetchone()
            if existing:
                raise DivineToolError(f"Duplicate imported income row already exists as #{existing['id']}.")
        cur = conn.execute(
            """
            INSERT INTO income (temple_id, amount_minor, currency, gbp_minor, strategy, import_fingerprint, source, note, occurred_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (scoped_temple_id, amount_minor, currency, gbp_minor, strategy, import_fingerprint, source, note, occurred, created),
        )
        conn.commit()
        income_id = int(cur.lastrowid)
    strategy_suffix = f" [{strategy}]" if strategy else ""
    log_event(data_dir, f"Income recorded: {format_money(gbp_minor)} from {source}{strategy_suffix}", "income", temple_id=scoped_temple_id)
    return income_id


def import_income_csv(
    data_dir: Path,
    csv_text: str,
    source_type: str = "generic",
    default_strategy: str = "",
    dry_run: bool = False,
    filename: str = "",
    temple_id: str | None = None,
) -> dict[str, Any]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    source_type = source_type.lower()
    if source_type not in {"generic", "payment", "affiliate"}:
        raise DivineToolError("Import type must be generic, payment, or affiliate.")

    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise DivineToolError("CSV import needs a header row.")

    result: dict[str, Any] = {
        "source_type": source_type,
        "filename": filename,
        "dry_run": dry_run,
        "ready_count": 0,
        "imported_count": 0,
        "duplicate_count": 0,
        "skipped_count": 0,
        "rows": [],
        "errors": [],
    }
    seen_fingerprints: dict[str, int] = {}

    for index, raw_row in enumerate(reader, start=2):
        row = {str(key or "").strip(): str(value or "").strip() for key, value in raw_row.items()}
        parsed = parse_import_row(row, source_type, default_strategy)
        parsed["row_number"] = index
        if parsed.get("status") == "skipped":
            result["skipped_count"] += 1
            result["rows"].append(parsed)
            continue

        fingerprint = income_fingerprint(
            amount_minor=parsed["amount_minor"],
            currency=parsed["currency"],
            gbp_minor=parsed["gbp_minor"],
            strategy=parsed["strategy"],
            source=parsed["source"],
            note=parsed["note"],
            occurred_at=parsed["date"],
            external_id=parsed["external_id"],
        )
        parsed["fingerprint"] = fingerprint
        existing_id = existing_import_id(data_dir, fingerprint, temple_id=scoped_temple_id)
        if existing_id is not None:
            parsed["status"] = "duplicate"
            parsed["existing_id"] = existing_id
            result["duplicate_count"] += 1
            result["rows"].append(parsed)
            continue

        if fingerprint in seen_fingerprints:
            parsed["status"] = "duplicate"
            parsed["reason"] = f"Matches row {seen_fingerprints[fingerprint]} in this CSV."
            result["duplicate_count"] += 1
            result["rows"].append(parsed)
            continue
        seen_fingerprints[fingerprint] = index

        if dry_run:
            parsed["status"] = "ready"
            result["ready_count"] += 1
            result["rows"].append(parsed)
            continue

        income_id = add_income(
            data_dir,
            amount_minor=parsed["amount_minor"],
            currency=parsed["currency"],
            gbp_minor=parsed["gbp_minor"],
            source=parsed["source"],
            note=parsed["note"],
            strategy=parsed["strategy"],
            import_fingerprint=fingerprint,
            occurred_on=parse_date(parsed["date"]),
            temple_id=scoped_temple_id,
        )
        parsed["status"] = "imported"
        parsed["id"] = income_id
        result["imported_count"] += 1
        result["rows"].append(parsed)

    log_event(
        data_dir,
        f"CSV import complete: {result['imported_count']} imported, {result['duplicate_count']} duplicate, {result['skipped_count']} skipped",
        "import",
        temple_id=scoped_temple_id,
    )
    return result


def parse_import_row(row: dict[str, str], source_type: str, default_strategy: str) -> dict[str, Any]:
    amount_value = first_present(
        row,
        [
            "amount",
            "gbp_amount",
            "amount_gbp",
            "net",
            "net_amount",
            "total",
            "paid",
            "commission",
            "commission_amount",
            "revenue",
            "payout",
        ],
    )
    date_value = first_present(row, ["date", "occurred_at", "transaction_date", "paid_at", "created", "created_at"])
    source_value = first_present(
        row,
        [
            "source",
            "description",
            "customer",
            "client",
            "merchant",
            "name",
            "campaign",
            "product",
            "program",
            "advertiser",
        ],
    )
    note_value = first_present(row, ["note", "notes", "memo", "details", "description", "reference"])
    currency = first_present(row, ["currency", "currency_code", "ccy"]) or "GBP"
    gbp_equivalent = first_present(row, ["gbp_equivalent", "gbp", "gbp_amount", "amount_gbp", "net_gbp"])
    strategy = first_present(row, ["strategy", "channel", "module", "category"]) or default_strategy
    external_id = first_present(row, ["transaction_id", "id", "reference", "ref", "order_id", "payment_id", "sale_id"])

    if not strategy:
        if source_type == "affiliate":
            strategy = "affiliate_referral"
        elif source_type == "payment":
            strategy = "freelance_services"

    if not amount_value:
        return import_skip("Missing amount.")
    if not date_value:
        return import_skip("Missing date.")
    if not source_value:
        source_value = f"{source_type} import"

    try:
        amount_minor = parse_money_to_minor(clean_money_value(amount_value))
        occurred = parse_import_date(date_value)
    except DivineToolError as exc:
        return import_skip(str(exc))

    if amount_minor <= 0:
        return import_skip("Amount is not positive income.")

    currency = currency.upper()
    try:
        gbp_minor = amount_minor if currency == "GBP" else parse_money_to_minor(clean_money_value(gbp_equivalent))
    except DivineToolError:
        return import_skip("Non-GBP row needs a GBP equivalent column.")

    return {
        "status": "parsed",
        "date": occurred.isoformat(),
        "amount": format_money(amount_minor, currency),
        "amount_minor": amount_minor,
        "currency": currency,
        "gbp": format_money(gbp_minor),
        "gbp_minor": gbp_minor,
        "source": source_value,
        "note": note_value,
        "strategy": strategy,
        "external_id": external_id,
    }


def import_skip(reason: str) -> dict[str, Any]:
    return {"status": "skipped", "reason": reason}


def existing_import_id(data_dir: Path, fingerprint: str, temple_id: str | None = None) -> int | None:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        row = conn.execute(
            """
            SELECT id FROM income
            WHERE import_fingerprint = ? AND temple_id = ?
            LIMIT 1
            """,
            (fingerprint, scoped_temple_id),
        ).fetchone()
    return int(row["id"]) if row else None


def validate_username(username: str) -> str:
    cleaned = username.strip().lower()
    if len(cleaned) < 3:
        raise DivineToolError("Username must be at least 3 characters.")
    if len(cleaned) > 40:
        raise DivineToolError("Username must be 40 characters or fewer.")
    if any(char for char in cleaned if not (char.isalnum() or char in {"_", "-", "."})):
        raise DivineToolError("Username can use letters, numbers, dots, hyphens, and underscores.")
    return cleaned


def validate_password(config: dict[str, Any], password: str) -> None:
    min_length = int(config.get("auth", {}).get("password_min_length", 10))
    if len(password) < min_length:
        raise DivineToolError(f"Password must be at least {min_length} characters.")
    if password.strip() != password or not password:
        raise DivineToolError("Password cannot start or end with whitespace.")


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240000)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    _salt, actual = hash_password(password, salt_hex)
    return hmac.compare_digest(actual, expected_hash)


def account_count(data_dir: Path) -> int:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM accounts").fetchone()
    return int(row["count"])


def create_account(
    data_dir: Path,
    username: str,
    password: str,
    display_name: str = "",
    role: str = "owner",
) -> dict[str, Any]:
    ensure_state(data_dir)
    config = load_config(data_dir)
    username = validate_username(username)
    validate_password(config, password)
    role = role.strip().lower() or "owner"
    if role != "owner":
        raise DivineToolError("Only owner accounts are supported in this local release.")
    if account_count(data_dir) > 0:
        raise DivineToolError("Owner account already exists.")

    salt, password_hash = hash_password(password)
    created = now_iso()
    with db(data_dir) as conn:
        cur = conn.execute(
            """
            INSERT INTO accounts
                (username, display_name, role, password_salt, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, display_name.strip(), role, salt, password_hash, created),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (int(cur.lastrowid),)).fetchone()
    log_event(data_dir, f"Owner account created: {username}", "auth")
    return account_to_dict(row)


def list_accounts(data_dir: Path) -> list[dict[str, Any]]:
    ensure_state(data_dir)
    with db(data_dir) as conn:
        rows = list(
            conn.execute(
                """
                SELECT *
                FROM accounts
                ORDER BY id ASC
                """
            )
        )
    return [account_to_dict(row) for row in rows]


def create_session(data_dir: Path, username: str, password: str, user_agent: str = "") -> dict[str, Any]:
    ensure_state(data_dir)
    config = load_config(data_dir)
    if not config.get("auth", {}).get("enabled", True):
        raise DivineToolError("Authentication is disabled.")
    username = validate_username(username)
    cleanup_expired_sessions(data_dir)
    with db(data_dir) as conn:
        row = conn.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()
        if row is None or int(row["disabled"]):
            raise DivineToolError("Invalid username or password.")
        if not verify_password(password, row["password_salt"], row["password_hash"]):
            raise DivineToolError("Invalid username or password.")

        token = secrets.token_urlsafe(32)
        token_hash = session_token_hash(token)
        created = now_iso()
        ttl_hours = max(int(config.get("auth", {}).get("session_ttl_hours", 12)), 1)
        expires_at = (datetime.now() + timedelta(hours=ttl_hours)).isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO auth_sessions
                (token_hash, account_id, created_at, expires_at, last_seen_at, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token_hash, int(row["id"]), created, expires_at, created, user_agent[:200]),
        )
        conn.execute("UPDATE accounts SET last_login_at = ? WHERE id = ?", (created, int(row["id"])))
        conn.commit()
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (int(row["id"]),)).fetchone()
    log_event(data_dir, f"Account signed in: {username}", "auth")
    return {"token": token, "expires_at": expires_at, "account": account_to_dict(account)}


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_session_account(data_dir: Path, token: str | None) -> dict[str, Any] | None:
    ensure_state(data_dir)
    if not token:
        return None
    cleanup_expired_sessions(data_dir)
    with db(data_dir) as conn:
        row = conn.execute(
            """
            SELECT accounts.*
            FROM auth_sessions
            JOIN accounts ON accounts.id = auth_sessions.account_id
            WHERE auth_sessions.token_hash = ?
              AND datetime(auth_sessions.expires_at) > datetime('now', 'localtime')
              AND accounts.disabled = 0
            LIMIT 1
            """,
            (session_token_hash(token),),
        ).fetchone()
        if row is None:
            return None
        conn.execute("UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?", (now_iso(), session_token_hash(token)))
        conn.commit()
    return account_to_dict(row)


def destroy_session(data_dir: Path, token: str | None) -> None:
    ensure_state(data_dir)
    if not token:
        return
    with db(data_dir) as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (session_token_hash(token),))
        conn.commit()


def cleanup_expired_sessions(data_dir: Path) -> None:
    with db(data_dir) as conn:
        conn.execute("DELETE FROM auth_sessions WHERE datetime(expires_at) <= datetime('now', 'localtime')")
        conn.commit()


def auth_status(data_dir: Path, token: str | None = None) -> dict[str, Any]:
    ensure_state(data_dir)
    config = load_config(data_dir)
    enabled = bool(config.get("auth", {}).get("enabled", True))
    setup_required = account_count(data_dir) == 0
    account = get_session_account(data_dir, token) if enabled and not setup_required else None
    return {
        "enabled": enabled,
        "setup_required": setup_required,
        "authenticated": bool(account) or not enabled,
        "account": account,
        "accounts": list_accounts(data_dir) if account else [],
        "secret_management": config.get("auth", {}).get("secret_management", {}),
    }


def account_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
        "disabled": bool(row["disabled"]),
    }


FetchJson = Callable[[str, dict[str, str] | None], Any]


def fetch_external_json(url: str, headers: dict[str, str] | None = None) -> Any:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=6) as response:
        return json.loads(response.read().decode("utf-8"))


def external_connections_snapshot(
    data_dir: Path,
    today: date | None = None,
    fetch_json: FetchJson | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    ensure_state(data_dir)
    config = load_config(data_dir)
    integrations = config.get("integrations", {})
    fetcher = fetch_json or fetch_external_json
    env = environ if environ is not None else os.environ
    today = today or date.today()
    builders = [
        ("currency_rates", "Currency Rates", currency_rates_snapshot),
        ("github", "GitHub Telemetry", github_snapshot),
        ("payments", "Payment Summaries", payment_snapshot),
        ("product_analytics", "Product Analytics", product_analytics_snapshot),
    ]
    connections = []

    for key, display_name, builder in builders:
        settings = dict(integrations.get(key, {}))
        try:
            connections.append(builder(data_dir, settings, today, fetcher, env))
        except Exception as exc:
            connections.append(
                {
                    "id": key,
                    "name": display_name,
                    "state": "error",
                    "summary": str(exc),
                    "items": [],
                    "next_action": "Check the connector settings and try again.",
                }
            )

    return {
        "generated_at": now_iso(),
        "connected_count": sum(1 for item in connections if item["state"] == "connected"),
        "ready_count": sum(1 for item in connections if item["state"] == "ready"),
        "disabled_count": sum(1 for item in connections if item["state"] == "disabled"),
        "error_count": sum(1 for item in connections if item["state"] == "error"),
        "connections": connections,
    }


def currency_rates_snapshot(
    _data_dir: Path,
    settings: dict[str, Any],
    _today: date,
    fetch_json: FetchJson,
    _environ: dict[str, str],
) -> dict[str, Any]:
    if not settings.get("enabled", False):
        return disabled_connection(
            "currency_rates",
            "Currency Rates",
            "Currency-rate lookup is disabled.",
            "Enable currency_rates in config when live rates are useful.",
        )

    provider = str(settings.get("provider", "frankfurter"))
    base_currency = str(settings.get("base_currency", "GBP")).upper()
    if base_currency != "GBP":
        raise DivineToolError("Currency-rate integration currently expects GBP as the base currency.")
    targets = [str(item).upper() for item in settings.get("targets", []) if str(item).strip()]
    if not targets:
        return ready_connection(
            "currency_rates",
            "Currency Rates",
            "No target currencies are configured.",
            "Add fiat target currencies to integrations.currency_rates.targets.",
        )

    base_url = str(settings.get("base_url", "https://api.frankfurter.dev/v2")).rstrip("/")
    query = urllib.parse.urlencode({"base": base_currency, "quotes": ",".join(targets)})
    url = f"{base_url}/rates?{query}"
    payload = fetch_json(url, {"User-Agent": "Divine-Tool/1.5"})
    if isinstance(payload, list):
        rates = {str(row.get("quote", "")).upper(): row.get("rate") for row in payload if isinstance(row, dict)}
        updated_at = str(payload[0].get("date", "")) if payload and isinstance(payload[0], dict) else ""
    else:
        rates = payload.get("rates", {})
        updated_at = str(payload.get("date", ""))
    items = []
    for currency in targets:
        if currency not in rates:
            continue
        quoted = Decimal(str(rates[currency]))
        if quoted <= 0:
            continue
        rate_to_gbp = Decimal("1") / quoted
        one_unit_minor = int((rate_to_gbp * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        items.append(
            {
                "currency": currency,
                "base_rate": str(quoted),
                "rate_to_gbp": str(rate_to_gbp.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
                "one_unit": format_money(one_unit_minor),
            }
        )

    if not items:
        return ready_connection(
            "currency_rates",
            "Currency Rates",
            "No matching live rates came back from the provider.",
            "Check configured target currencies.",
        )

    return {
        "id": "currency_rates",
        "name": "Currency Rates",
        "state": "connected",
        "provider": provider,
        "summary": f"{len(items)} live fiat rate(s) from {provider}",
        "updated_at": updated_at,
        "items": items,
        "source_url": url,
        "next_action": "Use live rates as a check before recording non-GBP income.",
    }


def github_snapshot(
    _data_dir: Path,
    settings: dict[str, Any],
    today: date,
    fetch_json: FetchJson,
    environ: dict[str, str],
) -> dict[str, Any]:
    if not settings.get("enabled", False):
        return disabled_connection(
            "github",
            "GitHub Telemetry",
            "GitHub telemetry is disabled.",
            "Enable github in config when project activity should be visible.",
        )

    repository = str(settings.get("repository", "")).strip()
    if "/" not in repository:
        return ready_connection(
            "github",
            "GitHub Telemetry",
            "No owner/repo is configured.",
            "Set integrations.github.repository to owner/repo.",
        )

    owner, repo = repository.split("/", 1)
    safe_owner = urllib.parse.quote(owner, safe="")
    safe_repo = urllib.parse.quote(repo, safe="")
    base_url = f"https://api.github.com/repos/{safe_owner}/{safe_repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Divine-Tool/1.5",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    token = environ.get("GITHUB_TOKEN") or environ.get("DIVINE_GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    lookback_days = max(int(settings.get("lookback_days", 7)), 1)
    since = datetime.combine(today - timedelta(days=lookback_days), datetime.min.time()).isoformat() + "Z"
    repo_payload = fetch_json(base_url, headers)
    commits = fetch_json(f"{base_url}/commits?{urllib.parse.urlencode({'since': since, 'per_page': 100})}", headers)
    issues = fetch_json(f"{base_url}/issues?{urllib.parse.urlencode({'state': 'open', 'per_page': 100})}", headers)
    pulls = fetch_json(f"{base_url}/pulls?{urllib.parse.urlencode({'state': 'open', 'per_page': 100})}", headers)
    open_issues = [item for item in issues if "pull_request" not in item]

    items = [
        {"label": f"Commits {lookback_days}d", "value": str(len(commits))},
        {"label": "Open Issues", "value": str(len(open_issues))},
        {"label": "Open PRs", "value": str(len(pulls))},
        {"label": "Stars", "value": str(repo_payload.get("stargazers_count", 0))},
    ]
    return {
        "id": "github",
        "name": "GitHub Telemetry",
        "state": "connected",
        "provider": "github",
        "summary": f"{repository} activity is available",
        "updated_at": repo_payload.get("updated_at", ""),
        "items": items,
        "source_url": base_url,
        "next_action": "Use project activity to prioritize build work that supports revenue.",
    }


def payment_snapshot(
    data_dir: Path,
    settings: dict[str, Any],
    _today: date,
    fetch_json: FetchJson,
    environ: dict[str, str],
) -> dict[str, Any]:
    summary_file = str(settings.get("summary_file", "")).strip()
    if summary_file:
        return payment_file_snapshot(data_dir, summary_file)

    if not settings.get("enabled", False):
        return ready_connection(
            "payments",
            "Payment Summaries",
            "Payment connector is ready but not enabled.",
            "Enable it only with a read-only key or keep using CSV imports.",
        )

    provider = str(settings.get("provider", "stripe")).lower()
    if provider != "stripe":
        return ready_connection(
            "payments",
            "Payment Summaries",
            f"Provider '{provider}' is not implemented yet.",
            "Use provider stripe or a local summary file.",
        )

    env_var = str(settings.get("env_var", "DIVINE_STRIPE_SECRET_KEY"))
    secret = environ.get(env_var)
    if not secret:
        return ready_connection(
            "payments",
            "Payment Summaries",
            f"Stripe is enabled but {env_var} is not set.",
            "Set the environment variable with a restricted read-only key before refreshing.",
        )

    limit = min(max(int(settings.get("limit", 10)), 1), 100)
    url = f"https://api.stripe.com/v1/balance_transactions?{urllib.parse.urlencode({'limit': limit})}"
    auth = base64.b64encode(f"{secret}:".encode("utf-8")).decode("ascii")
    payload = fetch_json(url, {"Authorization": f"Basic {auth}", "User-Agent": "Divine-Tool/1.5"})
    transactions = payload.get("data", [])
    return payment_transactions_connection("stripe", transactions, url)


def payment_file_snapshot(data_dir: Path, summary_file: str) -> dict[str, Any]:
    path = Path(summary_file)
    if not path.is_absolute():
        path = data_dir / path
    if not path.exists():
        return ready_connection(
            "payments",
            "Payment Summaries",
            f"Payment summary file not found: {path}",
            "Check integrations.payments.summary_file or import the export as CSV.",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    transactions = payload.get("transactions", [])
    provider = str(payload.get("provider", "manual"))
    return payment_transactions_connection(provider, transactions, str(path))


def payment_transactions_connection(provider: str, transactions: list[dict[str, Any]], source_url: str) -> dict[str, Any]:
    totals: dict[str, dict[str, int]] = {}
    for transaction in transactions:
        currency = str(transaction.get("currency", "GBP")).upper()
        net_minor = int(transaction.get("net_minor", transaction.get("net", 0)))
        totals.setdefault(currency, {"minor": 0, "count": 0})
        totals[currency]["minor"] += net_minor
        totals[currency]["count"] += 1

    items = [
        {
            "currency": currency,
            "net": format_money(values["minor"], currency),
            "transaction_count": str(values["count"]),
        }
        for currency, values in sorted(totals.items())
    ]
    return {
        "id": "payments",
        "name": "Payment Summaries",
        "state": "connected" if transactions else "ready",
        "provider": provider,
        "summary": f"{len(transactions)} read-only payment transaction(s) reviewed",
        "items": items,
        "source_url": source_url,
        "next_action": "Import settled income rows only after review.",
    }


def product_analytics_snapshot(
    data_dir: Path,
    settings: dict[str, Any],
    _today: date,
    _fetch_json: FetchJson,
    _environ: dict[str, str],
) -> dict[str, Any]:
    summary_file = str(settings.get("summary_file", "")).strip()
    if not settings.get("enabled", False) and not summary_file:
        return disabled_connection(
            "product_analytics",
            "Product Analytics",
            "Product analytics summaries are disabled.",
            "Add a local analytics summary file when product metrics should guide priorities.",
        )
    if not summary_file:
        return ready_connection(
            "product_analytics",
            "Product Analytics",
            "Product analytics is enabled but no summary file is configured.",
            "Set integrations.product_analytics.summary_file to a local JSON export.",
        )

    path = Path(summary_file)
    if not path.is_absolute():
        path = data_dir / path
    if not path.exists():
        return ready_connection(
            "product_analytics",
            "Product Analytics",
            f"Analytics summary file not found: {path}",
            "Check integrations.product_analytics.summary_file.",
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", {})
    items = [{"label": title_case_from_key(key), "value": str(value)} for key, value in list(metrics.items())[:6]]
    return {
        "id": "product_analytics",
        "name": "Product Analytics",
        "state": "connected" if items else "ready",
        "provider": str(payload.get("provider", "local")),
        "summary": str(payload.get("summary", f"{len(items)} product metric(s) reviewed")),
        "items": items,
        "source_url": str(path),
        "next_action": "Use conversion and usage signals to pick the next revenue feature.",
    }


def title_case_from_key(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value).replace("_", " ").split())


def create_approval_draft(
    data_dir: Path,
    kind: str,
    target: str = "",
    strategy: str = "",
    amount_minor: int | None = None,
    due_on: date | None = None,
    invoice: str = "",
    offer: str = "",
    topic: str = "",
    goal: str = "",
    channel: str = "",
    context: str = "",
    tone: str = "polite",
    temple_id: str | None = None,
) -> int:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    kind = kind.strip().lower().replace("-", "_")
    if kind not in APPROVAL_KINDS:
        raise DivineToolError("Draft kind must be invoice_reminder, outreach, or content_prompt.")

    metadata = {
        "amount_minor": amount_minor,
        "amount": format_money(amount_minor) if amount_minor is not None else "",
        "due_on": due_on.isoformat() if due_on else "",
        "invoice": invoice.strip(),
        "offer": offer.strip(),
        "topic": topic.strip(),
        "goal": goal.strip(),
        "channel": channel.strip(),
        "context": context.strip(),
        "tone": tone.strip() or "polite",
    }
    title, body, normalized_target = build_action_draft(kind, target.strip(), metadata)
    created = now_iso()
    with db(data_dir) as conn:
        cur = conn.execute(
            """
            INSERT INTO approval_actions
                (temple_id, kind, title, target, strategy, body, metadata_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (scoped_temple_id, kind, title, normalized_target, strategy.strip(), body, json.dumps(metadata, sort_keys=True), created),
        )
        conn.commit()
        action_id = int(cur.lastrowid)
    log_event(data_dir, f"Draft queued for approval: {title}", "approval", temple_id=scoped_temple_id)
    return action_id


def build_action_draft(kind: str, target: str, metadata: dict[str, Any]) -> tuple[str, str, str]:
    if kind == "invoice_reminder":
        if not target:
            raise DivineToolError("Invoice reminder drafts need a target or client name.")
        if metadata.get("amount_minor") is None:
            raise DivineToolError("Invoice reminder drafts need an amount.")
        invoice = metadata.get("invoice") or "invoice"
        due_on = metadata.get("due_on") or "soon"
        amount = metadata.get("amount") or "the outstanding amount"
        title = f"Invoice reminder for {target}"
        body = "\n".join(
            [
                f"Subject: Quick reminder: {invoice}",
                "",
                f"Hi {target},",
                "",
                f"I hope you are well. This is a quick reminder that {invoice} for {amount} is due on {due_on}.",
                "",
                "When convenient, could you confirm the payment timing? If anything is blocked, let me know and I can help resolve it.",
                "",
                "Thanks,",
                "Creator",
            ]
        )
        return title, body, target

    if kind == "outreach":
        if not target:
            raise DivineToolError("Outreach drafts need a target or recipient.")
        offer = metadata.get("offer") or metadata.get("goal") or ""
        if not offer:
            raise DivineToolError("Outreach drafts need an offer.")
        context = metadata.get("context") or "there may be a useful opening to improve revenue"
        title = f"Outreach draft for {target}"
        body = "\n".join(
            [
                f"Subject: {offer}",
                "",
                f"Hi {target},",
                "",
                f"I noticed {context}.",
                "",
                f"I can help with {offer}. If useful, I can send a short plan with scope, timeline, and pricing.",
                "",
                "Would it be worth a quick reply?",
                "",
                "Thanks,",
                "Creator",
            ]
        )
        return title, body, target

    topic = metadata.get("topic") or target
    goal = metadata.get("goal") or ""
    if not topic:
        raise DivineToolError("Content prompt drafts need a topic.")
    if not goal:
        raise DivineToolError("Content prompt drafts need a goal.")
    channel = metadata.get("channel") or "content"
    title = f"Content prompt: {topic}"
    body = "\n".join(
        [
            f"Create a {channel} piece about: {topic}",
            "",
            f"Goal: {goal}",
            "",
            "Include:",
            "- A clear reader problem.",
            "- A practical answer or framework.",
            "- One proof point or example.",
            "- A calm call to action that invites a reply, booking, or purchase.",
            "",
            "Keep claims honest, avoid pressure tactics, and make the offer easy to understand.",
        ]
    )
    return title, body, topic


def list_approval_actions(
    data_dir: Path,
    status: str = "pending",
    limit: int = 20,
    temple_id: str | None = None,
) -> list[sqlite3.Row]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    status = status.strip().lower()
    limit = max(min(limit, 100), 1)
    with db(data_dir) as conn:
        if status == "all":
            return list(
                conn.execute(
                    """
                    SELECT *
                    FROM approval_actions
                    WHERE temple_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (scoped_temple_id, limit),
                )
            )
        if status not in APPROVAL_STATUSES:
            raise DivineToolError("Approval status must be pending, approved, rejected, completed, or all.")
        return list(
            conn.execute(
                """
                SELECT *
                FROM approval_actions
                WHERE temple_id = ? AND status = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (scoped_temple_id, status, limit),
            )
        )


def approval_queue_summary(data_dir: Path, limit: int = 8, temple_id: str | None = None) -> dict[str, Any]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        counts = {
            row["status"]: int(row["count"])
            for row in conn.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM approval_actions
                WHERE temple_id = ?
                GROUP BY status
                """,
                (scoped_temple_id,),
            )
        }
    for status in APPROVAL_STATUSES:
        counts.setdefault(status, 0)
    return {
        "counts": counts,
        "pending": [approval_action_to_dict(row) for row in list_approval_actions(data_dir, "pending", limit, temple_id=scoped_temple_id)],
        "recent": [approval_action_to_dict(row) for row in list_approval_actions(data_dir, "all", limit, temple_id=scoped_temple_id)],
    }


def review_approval_action(
    data_dir: Path,
    action_id: int,
    decision: str,
    note: str = "",
    temple_id: str | None = None,
) -> dict[str, Any]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    decision = decision.strip().lower()
    status_map = {
        "approve": "approved",
        "approved": "approved",
        "reject": "rejected",
        "rejected": "rejected",
        "complete": "completed",
        "completed": "completed",
    }
    if decision not in status_map:
        raise DivineToolError("Decision must be approve, reject, or complete.")
    new_status = status_map[decision]
    reviewed = now_iso()
    with db(data_dir) as conn:
        row = conn.execute(
            "SELECT * FROM approval_actions WHERE id = ? AND temple_id = ?",
            (action_id, scoped_temple_id),
        ).fetchone()
        if row is None:
            raise DivineToolError(f"Approval draft #{action_id} was not found.")
        current_status = str(row["status"])
        if new_status == "approved" and current_status != "pending":
            raise DivineToolError("Only pending drafts can be approved.")
        if new_status == "completed" and current_status != "approved":
            raise DivineToolError("Approve a draft before marking it complete.")
        if new_status == "rejected" and current_status not in {"pending", "approved"}:
            raise DivineToolError("Only pending or approved drafts can be rejected.")
        conn.execute(
            """
            UPDATE approval_actions
            SET status = ?, reviewed_at = ?, decision_note = ?
            WHERE id = ?
            """,
            (new_status, reviewed, note.strip(), action_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM approval_actions WHERE id = ? AND temple_id = ?",
            (action_id, scoped_temple_id),
        ).fetchone()
    log_event(data_dir, f"Draft #{action_id} marked {new_status}: {updated['title']}", "approval", temple_id=scoped_temple_id)
    return approval_action_to_dict(updated)


def approval_action_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = row_to_dict(row)
    try:
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
    except json.JSONDecodeError:
        item["metadata"] = {}
    item["kind_label"] = APPROVAL_KINDS.get(str(item["kind"]), title_case_from_key(str(item["kind"])))
    return item


def disabled_connection(identifier: str, name: str, summary: str, next_action: str) -> dict[str, Any]:
    return {"id": identifier, "name": name, "state": "disabled", "summary": summary, "items": [], "next_action": next_action}


def ready_connection(identifier: str, name: str, summary: str, next_action: str) -> dict[str, Any]:
    return {"id": identifier, "name": name, "state": "ready", "summary": summary, "items": [], "next_action": next_action}


def list_income(data_dir: Path, limit: int = 20, temple_id: str | None = None) -> list[sqlite3.Row]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        return list(
            conn.execute(
                """
                SELECT * FROM income
                WHERE temple_id = ?
                ORDER BY occurred_at DESC, id DESC
                LIMIT ?
                """,
                (scoped_temple_id, limit),
            )
        )


def income_total_for_period(data_dir: Path, period: Period, temple_id: str | None = None) -> int:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(gbp_minor), 0) AS total
            FROM income
            WHERE temple_id = ? AND date(occurred_at) >= date(?) AND date(occurred_at) < date(?)
            """,
            (scoped_temple_id, period.start.isoformat(), period.end.isoformat()),
        ).fetchone()
    return int(row["total"])


def income_rows_for_period(data_dir: Path, period: Period, limit: int = 25, temple_id: str | None = None) -> list[sqlite3.Row]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        return list(
            conn.execute(
                """
                SELECT *
                FROM income
                WHERE temple_id = ? AND date(occurred_at) >= date(?) AND date(occurred_at) < date(?)
                ORDER BY date(occurred_at) DESC, id DESC
                LIMIT ?
                """,
                (scoped_temple_id, period.start.isoformat(), period.end.isoformat(), limit),
            )
        )


def strategy_income_totals(data_dir: Path, period: Period, temple_id: str | None = None) -> dict[str, dict[str, int]]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    totals: dict[str, dict[str, int]] = {}
    with db(data_dir) as conn:
        period_rows = conn.execute(
            """
            SELECT strategy, COALESCE(SUM(gbp_minor), 0) AS total, COUNT(*) AS count
            FROM income
            WHERE temple_id = ? AND strategy <> '' AND date(occurred_at) >= date(?) AND date(occurred_at) < date(?)
            GROUP BY strategy
            """,
            (scoped_temple_id, period.start.isoformat(), period.end.isoformat()),
        ).fetchall()
        all_rows = conn.execute(
            """
            SELECT strategy, COALESCE(SUM(gbp_minor), 0) AS total, COUNT(*) AS count
            FROM income
            WHERE temple_id = ? AND strategy <> ''
            GROUP BY strategy
            """,
            (scoped_temple_id,),
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


def strategy_period_totals(data_dir: Path, period: Period, temple_id: str | None = None) -> dict[str, dict[str, int]]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        rows = conn.execute(
            """
            SELECT strategy, COALESCE(SUM(gbp_minor), 0) AS total, COUNT(*) AS count
            FROM income
            WHERE temple_id = ? AND strategy <> '' AND date(occurred_at) >= date(?) AND date(occurred_at) < date(?)
            GROUP BY strategy
            """,
            (scoped_temple_id, period.start.isoformat(), period.end.isoformat()),
        ).fetchall()
    return {row["strategy"]: {"minor": int(row["total"]), "count": int(row["count"])} for row in rows}


def strategy_recent_notes(
    data_dir: Path,
    limit_per_strategy: int = 3,
    temple_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    notes: dict[str, list[dict[str, Any]]] = {}
    with db(data_dir) as conn:
        rows = conn.execute(
            """
            SELECT strategy, source, note, gbp_minor, occurred_at
            FROM income
            WHERE temple_id = ? AND strategy <> ''
            ORDER BY date(occurred_at) DESC, id DESC
            """,
            (scoped_temple_id,),
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


def strategy_roi_summary(
    data_dir: Path,
    today: date | None = None,
    period_name: str | None = None,
    temple_id: str | None = None,
) -> dict[str, Any]:
    report = status_report(data_dir, today, temple_id=temple_id)
    config = load_config(data_dir)
    temple = active_temple_config(config, temple_id)
    scoped_temple_id = str(temple["id"])
    period = period_for(period_name, today) if period_name else report["period"]
    previous = previous_period(period)
    current_totals = strategy_period_totals(data_dir, period, temple_id=scoped_temple_id)
    previous_totals = strategy_period_totals(data_dir, previous, temple_id=scoped_temple_id)
    all_totals = strategy_income_totals(data_dir, period, temple_id=scoped_temple_id)
    notes = strategy_recent_notes(data_dir, temple_id=scoped_temple_id)
    opportunities_by_id = {item["id"]: item for item in generate_opportunities(data_dir, today, temple_id=scoped_temple_id)}
    rows: list[dict[str, Any]] = []

    for channel in temple.get("channels", []):
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
        "temple": temple_to_dict(temple, active=scoped_temple_id == str(active_temple_config(config)["id"])),
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


def set_mood(data_dir: Path, mood_name: str, temple_id: str | None = None) -> None:
    config = load_config(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    temple = active_temple_config(config, scoped_temple_id)
    if mood_name not in temple.get("moods", {}):
        known = ", ".join(sorted(temple.get("moods", {}).keys()))
        raise DivineToolError(f"Unknown mood '{mood_name}'. Known moods: {known}")
    for item in config.get("temples", []):
        if item["id"] == scoped_temple_id:
            item["active_mood"] = mood_name
            break
    if scoped_temple_id == str(config.get("active_temple")):
        sync_active_temple_legacy_fields(config)
    save_config(data_dir, config)
    log_event(data_dir, f"Mood changed to {mood_name}", "config", temple_id=scoped_temple_id)


def set_quota(data_dir: Path, mood_name: str, amount_minor: int, period: str, temple_id: str | None = None) -> None:
    config = load_config(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    temple = active_temple_config(config, scoped_temple_id)
    temple.setdefault("moods", {})
    existing = dict(temple["moods"].get(mood_name, {}))
    existing["period"] = period_for(period).name
    existing["quota_minor"] = amount_minor
    existing.setdefault("punishment", "review revenue actions until the quota recovers")
    temple["moods"][mood_name] = existing
    temple.setdefault("active_mood", mood_name)
    for index, item in enumerate(config.get("temples", [])):
        if item["id"] == scoped_temple_id:
            config["temples"][index] = temple
            break
    if scoped_temple_id == str(config.get("active_temple")):
        sync_active_temple_legacy_fields(config)
    save_config(data_dir, config)
    log_event(data_dir, f"{mood_name} quota set to {format_money(amount_minor)} per {period}", "config", temple_id=scoped_temple_id)


def add_exception(
    data_dir: Path,
    reason: str,
    starts_on: date | None,
    ends_on: date,
    temple_id: str | None = None,
) -> int:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    start = starts_on or date.today()
    if ends_on < start:
        raise DivineToolError("Exception end date must be on or after the start date.")
    with db(data_dir) as conn:
        cur = conn.execute(
            """
            INSERT INTO exceptions (temple_id, reason, starts_on, ends_on, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scoped_temple_id, reason, start.isoformat(), ends_on.isoformat(), now_iso()),
        )
        conn.commit()
        exception_id = int(cur.lastrowid)
    log_event(data_dir, f"Exception added until {ends_on.isoformat()}: {reason}", "exception", temple_id=scoped_temple_id)
    return exception_id


def list_exceptions(data_dir: Path, limit: int = 20, temple_id: str | None = None) -> list[sqlite3.Row]:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    with db(data_dir) as conn:
        return list(
            conn.execute(
                """
                SELECT * FROM exceptions
                WHERE temple_id = ?
                ORDER BY ends_on DESC, id DESC
                LIMIT ?
                """,
                (scoped_temple_id, limit),
            )
        )


def active_exception(data_dir: Path, today: date | None = None, temple_id: str | None = None) -> sqlite3.Row | None:
    ensure_state(data_dir)
    scoped_temple_id = active_temple_id_for_data_dir(data_dir, temple_id)
    today = (today or date.today()).isoformat()
    with db(data_dir) as conn:
        return conn.execute(
            """
            SELECT * FROM exceptions
            WHERE temple_id = ? AND date(starts_on) <= date(?) AND date(ends_on) >= date(?)
            ORDER BY ends_on DESC
            LIMIT 1
            """,
            (scoped_temple_id, today, today),
        ).fetchone()


def status_report(data_dir: Path, today: date | None = None, temple_id: str | None = None) -> dict[str, Any]:
    ensure_state(data_dir)
    config = load_config(data_dir)
    temple = active_temple_config(config, temple_id)
    scoped_temple_id = str(temple["id"])
    mood = active_mood(config, scoped_temple_id)
    period = period_for(mood["period"], today)
    earned = income_total_for_period(data_dir, period, temple_id=scoped_temple_id)
    quota = int(mood["quota_minor"])
    remaining = max(quota - earned, 0)
    progress = 1.0 if quota <= 0 else min(earned / quota, 1.0)
    days_left = max((period.end - (today or date.today())).days, 0)
    exception = active_exception(data_dir, today, temple_id=scoped_temple_id)
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
        "temple": temple_to_dict(temple, active=scoped_temple_id == str(active_temple_config(config)["id"])),
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


def generate_opportunities(
    data_dir: Path,
    today: date | None = None,
    temple_id: str | None = None,
) -> list[dict[str, Any]]:
    report = status_report(data_dir, today, temple_id=temple_id)
    config = load_config(data_dir)
    temple = active_temple_config(config, temple_id)
    scoped_temple_id = str(temple["id"])
    period = report["period"]
    gap = int(report["remaining_minor"])
    days_left = int(report["days_left"])
    totals = strategy_income_totals(data_dir, period, temple_id=scoped_temple_id)
    opportunities: list[dict[str, Any]] = []

    for channel in temple.get("channels", []):
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


def generate_upgrades(data_dir: Path, today: date | None = None, temple_id: str | None = None) -> list[str]:
    report = status_report(data_dir, today, temple_id=temple_id)
    if report["remaining_minor"] == 0:
        return [
            "Unlock payment reminders for invoices and retainers.",
            "Add lead scoring so the highest-value opportunities are contacted first.",
            "Track which approved drafts lead to replies, bookings, and paid income.",
            "Add a local web dashboard for quota progress, command history, and channel ROI.",
            "Add exportable weekly reports for the Creator.",
        ]
    return [
        "Quota is not satisfied yet, so upgrades stay focused on revenue recovery.",
        "Tighten the offer list to one fast paid service and one reusable product.",
        "Add better source notes to each income entry so profitable channels are obvious.",
        "Reduce low-return channels until the current quota is safe.",
    ]


def generate_report(
    data_dir: Path,
    period_name: str = "week",
    today: date | None = None,
    temple_id: str | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    config = load_config(data_dir)
    temple = active_temple_config(config, temple_id)
    scoped_temple_id = str(temple["id"])
    period = period_for(period_name, today)
    quota_minor, quota_source = quota_for_report_period(config, period_name, temple_id=scoped_temple_id)
    earned_minor = income_total_for_period(data_dir, period, temple_id=scoped_temple_id)
    remaining_minor = max(quota_minor - earned_minor, 0)
    progress_pct = 100.0 if quota_minor <= 0 else round(min(earned_minor / quota_minor, 1) * 100, 1)
    days_left = max((period.end - today).days, 0)
    exception = active_exception(data_dir, today, temple_id=scoped_temple_id)
    income_rows = income_rows_for_period(data_dir, period, limit=25, temple_id=scoped_temple_id)
    roi = strategy_roi_summary(data_dir, today=today, period_name=period_name, temple_id=scoped_temple_id)
    opportunities = generate_opportunities(data_dir, today, temple_id=scoped_temple_id)[:5]
    upgrades = generate_upgrades(data_dir, today, temple_id=scoped_temple_id)
    missed_review = missed_quota_review(
        quota_minor=quota_minor,
        earned_minor=earned_minor,
        remaining_minor=remaining_minor,
        days_left=days_left,
        exception=dict(exception) if exception else None,
    )
    period_label = {"week": "Weekly", "month": "Monthly"}.get(period_name, period_name.title())

    report = {
        "title": f"Divine Profit {period_label} Report",
        "temple": temple_to_dict(temple, active=scoped_temple_id == str(active_temple_config(config)["id"])),
        "generated_at": now_iso(),
        "period": {
            "name": period.name,
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
        },
        "quota_source": quota_source,
        "quota": format_money(quota_minor),
        "quota_minor": quota_minor,
        "earned": format_money(earned_minor),
        "earned_minor": earned_minor,
        "remaining": format_money(remaining_minor),
        "remaining_minor": remaining_minor,
        "progress_pct": progress_pct,
        "days_left": days_left,
        "missed_quota_review": missed_review,
        "income": serialize_income_rows_for_report(income_rows),
        "strategy_roi": roi,
        "opportunities": opportunities,
        "upgrade_recommendations": upgrades,
    }
    report["markdown"] = format_report_markdown(report)
    return report


def quota_for_report_period(config: dict[str, Any], period_name: str, temple_id: str | None = None) -> tuple[int, str]:
    temple = active_temple_config(config, temple_id)
    active = active_mood(config, temple_id)
    if active.get("period") == period_name:
        return int(active.get("quota_minor", 0)), str(active["name"])

    for mood_name, mood in temple.get("moods", {}).items():
        if mood.get("period") == period_name:
            return int(mood.get("quota_minor", 0)), str(mood_name)

    return int(active.get("quota_minor", 0)), str(active["name"])


def missed_quota_review(
    quota_minor: int,
    earned_minor: int,
    remaining_minor: int,
    days_left: int,
    exception: dict[str, Any] | None,
) -> dict[str, Any]:
    if earned_minor >= quota_minor:
        return {
            "status": "satisfied",
            "message": "Quota is satisfied. Review what worked and carry the strongest channel into the next period.",
            "remaining_minor": 0,
            "remaining": format_money(0),
        }
    if exception:
        return {
            "status": "exception",
            "message": f"Quota is short, but exception #{exception['id']} is active until {exception['ends_on']}.",
            "remaining_minor": remaining_minor,
            "remaining": format_money(remaining_minor),
        }
    if days_left <= 1:
        return {
            "status": "urgent",
            "message": f"Quota is short by {format_money(remaining_minor)} with {days_left} day left. Focus on immediate lawful income actions.",
            "remaining_minor": remaining_minor,
            "remaining": format_money(remaining_minor),
        }
    return {
        "status": "open",
        "message": f"Quota is short by {format_money(remaining_minor)} with {days_left} days left. Keep pushing the highest-ranked strategy.",
        "remaining_minor": remaining_minor,
        "remaining": format_money(remaining_minor),
    }


def serialize_income_rows_for_report(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        output.append(
            {
                "id": row["id"],
                "occurred_at": row["occurred_at"],
                "amount": format_money(int(row["amount_minor"]), str(row["currency"])),
                "counted": format_money(int(row["gbp_minor"])),
                "counted_minor": int(row["gbp_minor"]),
                "currency": row["currency"],
                "strategy": row["strategy"],
                "source": row["source"],
                "note": row["note"],
            }
        )
    return output


def format_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['title']}",
        "",
        f"Temple: {report['temple']['name']} ({report['temple']['id']})",
        f"Generated: {report['generated_at']}",
        f"Period: {report['period']['start']} to {report['period']['end']}",
        f"Quota source: {report['quota_source']}",
        "",
        "## Quota Result",
        "",
        f"- Quota: {report['quota']}",
        f"- Earned: {report['earned']}",
        f"- Remaining: {report['remaining']}",
        f"- Progress: {report['progress_pct']}%",
        "",
        "## Missed-Quota Review",
        "",
        report["missed_quota_review"]["message"],
        "",
        "## Strategy ROI",
        "",
    ]

    for row in report["strategy_roi"]["rows"][:5]:
        lines.append(
            f"- {row['name']}: {row['current_period']} current, {row['previous_period']} previous, "
            f"{row['delta']} delta, {row['trend']}; {row['recommendation']}."
        )

    lines.extend(["", "## Priority Opportunities", ""])
    for item in report["opportunities"][:5]:
        lines.append(f"- #{item['rank']} {item['name']} ({item['score']}/100): {item['next_action']}")

    lines.extend(["", "## Upgrade Recommendations", ""])
    for item in report["upgrade_recommendations"][:5]:
        lines.append(f"- {item}")

    lines.extend(["", "## Income Entries", ""])
    if report["income"]:
        for row in report["income"][:10]:
            strategy = f" [{row['strategy']}]" if row["strategy"] else ""
            note = f" - {row['note']}" if row["note"] else ""
            lines.append(f"- {row['occurred_at']}: {row['counted']}{strategy} from {row['source']}{note}")
    else:
        lines.append("- No income entries recorded for this period.")

    return "\n".join(lines) + "\n"


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
    temple_id = str(command["temple_id"]) if command.get("temple_id") else None
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
            temple_id=temple_id,
        )
        return f"added income #{income_id}"
    if action == "set_mood":
        set_mood(data_dir, command["mood"], temple_id=temple_id)
        return f"set mood to {command['mood']}"
    if action == "set_quota":
        set_quota(
            data_dir,
            mood_name=command["mood"],
            amount_minor=parse_money_to_minor(command["amount"]),
            period=command.get("period", "week"),
            temple_id=temple_id,
        )
        return f"set {command['mood']} quota"
    if action == "add_exception":
        add_exception(
            data_dir,
            reason=command["reason"],
            starts_on=parse_date(command["from"]) if command.get("from") else None,
            ends_on=parse_date(command["until"]),
            temple_id=temple_id,
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
