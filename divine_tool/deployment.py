from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from . import __version__
from .core import (
    LATEST_SCHEMA_VERSION,
    SCHEMA_MIGRATIONS,
    SchemaMigration,
    DivineToolError,
    auth_status,
    connect,
    database_status,
    enqueue_command,
    ensure_state,
    list_accounts,
    list_income,
    list_worker_cycles,
    load_config,
    run_migrations,
    run_worker_cycle,
    schema_version,
    worker_status,
)


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
BACKUP_FORMAT_VERSION = 2
MAX_BACKUP_FILES = 64
MAX_BACKUP_UNCOMPRESSED_BYTES = 10 * 1024 * 1024 * 1024
BACKUP_STATE_FILES = (
    "config.json",
    "divine_tool.sqlite3",
    "commands.jsonl",
    "commands.processed.jsonl",
    "commands.failed.jsonl",
)
SQLITE_SIDECAR_FILES = ("divine_tool.sqlite3-wal", "divine_tool.sqlite3-shm")
PROCESSING_COMMAND_RE = re.compile(r"commands\.processing\.\d+\.jsonl\Z")


def env_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise DivineToolError(f"Invalid boolean environment value: {value}")


def env_int(value: str | None, default: int, *, name: str, minimum: int = 1) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise DivineToolError(f"{name} must be an integer.") from exc
    if parsed < minimum:
        raise DivineToolError(f"{name} must be at least {minimum}.")
    return parsed


def normalize_origin(value: str, *, name: str = "origin") -> str:
    candidate = value.strip().rstrip("/")
    try:
        parsed = urllib.parse.urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise DivineToolError(f"{name} is not a valid HTTP origin.") from exc
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise DivineToolError(f"{name} must be an exact http:// or https:// origin without a path.")
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 80 if parsed.scheme.lower() == "http" else 443
    port_suffix = f":{port}" if port and port != default_port else ""
    return f"{parsed.scheme.lower()}://{host}{port_suffix}"


def allowed_origins(value: str | None, public_origin: str) -> list[str]:
    candidates = [public_origin] if public_origin else []
    candidates.extend(item.strip() for item in (value or "").split(",") if item.strip())
    normalized: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        origin = normalize_origin(candidate, name=f"allowed origin {index}")
        if origin not in normalized:
            normalized.append(origin)
    return normalized


def deployment_environment(
    environ: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    root = cwd or Path.cwd()
    raw_data_dir = env.get("DIVINE_DATA_DIR", str(root / ".divine_tool"))
    data_dir = Path(raw_data_dir).expanduser()
    if not data_dir.is_absolute():
        data_dir = root / data_dir

    backup_dir = Path(env.get("DIVINE_BACKUP_DIR", str(data_dir / "backups"))).expanduser()
    if not backup_dir.is_absolute():
        backup_dir = data_dir / backup_dir

    mode = env.get("DIVINE_DEPLOYMENT_MODE", "local").strip().lower() or "local"
    public_url = env.get("DIVINE_PUBLIC_URL", "").strip().rstrip("/")
    public_origin = normalize_origin(public_url, name="DIVINE_PUBLIC_URL") if public_url else ""
    origin_allowlist = allowed_origins(env.get("DIVINE_ALLOWED_ORIGINS"), public_origin)
    hosted_https = public_origin.startswith("https://")
    hosted_mode = mode not in {"local", "development", "test"}
    secure_by_default = hosted_mode or hosted_https

    return {
        "mode": mode,
        "data_dir": data_dir.resolve(),
        "backup_dir": backup_dir.resolve(),
        "host": env.get("DIVINE_HOST", "127.0.0.1"),
        "port": env_int(env.get("DIVINE_PORT"), 8765, name="DIVINE_PORT"),
        "daemon_interval": env_int(
            env.get("DIVINE_DAEMON_INTERVAL"),
            300,
            name="DIVINE_DAEMON_INTERVAL",
        ),
        "public_url": public_url,
        "public_origin": public_origin,
        "allowed_origins": origin_allowlist,
        "cookie_secure": env_bool(env.get("DIVINE_COOKIE_SECURE"), secure_by_default),
        "csrf_require_origin": env_bool(env.get("DIVINE_CSRF_REQUIRE_ORIGIN"), hosted_mode or bool(public_origin)),
        "trust_proxy": env_bool(env.get("DIVINE_TRUST_PROXY"), False),
        "force_https": env_bool(env.get("DIVINE_FORCE_HTTPS"), secure_by_default),
    }


def deployment_preflight(
    data_dir: Path,
    *,
    host: str,
    port: int,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    raw_env = os.environ if environ is None else environ
    env = deployment_environment(raw_env)
    env["data_dir"] = data_dir.resolve()
    checks: list[dict[str, str]] = []

    try:
        ensure_state(data_dir)
        checks.append(check("state", "pass", f"State directory is available: {data_dir}"))
    except Exception as exc:
        checks.append(check("state", "fail", f"State directory cannot be initialized: {exc}"))

    try:
        probe = data_dir / ".deploy-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(check("writable_state", "pass", "State directory is writable."))
    except Exception as exc:
        checks.append(check("writable_state", "fail", f"State directory is not writable: {exc}"))

    try:
        sqlite_status = database_status(data_dir)
        if not sqlite_status["ready"]:
            raise DivineToolError("SQLite runtime guarantees are incomplete.")
        checks.append(
            check(
                "database",
                "pass",
                "SQLite is ready with WAL, foreign keys, "
                f"a {sqlite_status['busy_timeout_ms']} ms busy timeout, and schema v{sqlite_status['schema_version']}.",
            )
        )
    except Exception as exc:
        checks.append(check("database", "fail", f"SQLite state database is not ready: {exc}"))

    try:
        config = load_config(data_dir)
    except Exception as exc:
        config = {}
        checks.append(check("config", "fail", f"Configuration cannot be loaded: {exc}"))
    else:
        checks.append(check("config", "pass", "Configuration loads successfully."))

    try:
        integrity = state_integrity(data_dir)
        if not integrity["ok"]:
            failures = [item["message"] for item in integrity["checks"] if item["severity"] == "fail"]
            raise DivineToolError(" ".join(failures))
        checks.append(check("state_integrity", "pass", "Configuration, SQLite, and command-log integrity pass."))
    except Exception as exc:
        checks.append(check("state_integrity", "fail", f"Operational state integrity failed: {exc}"))

    if not raw_env.get("DIVINE_BACKUP_DIR"):
        backup_setting = config.get("deployment", {}).get("backup", {}).get("directory", "backups")
        backup_dir = Path(str(backup_setting)).expanduser()
        if not backup_dir.is_absolute():
            backup_dir = data_dir / backup_dir
        env["backup_dir"] = backup_dir.resolve()

    auth = auth_status(data_dir)
    accounts = list_accounts(data_dir)
    if not auth.get("enabled", True):
        checks.append(check("owner_account", "warn", "Authentication is disabled for this state directory."))
    elif not accounts:
        checks.append(check("owner_account", "fail", "Create the first owner account before exposing the app."))
    else:
        checks.append(check("owner_account", "pass", f"Owner account exists: {accounts[0]['username']}"))

    public_bind = host in {"0.0.0.0", "::", ""}
    if public_bind:
        checks.append(check("network_bind", "pass", f"Web service can bind for container hosting on port {port}."))
    else:
        checks.append(check("network_bind", "warn", f"Host is {host}; use 0.0.0.0 inside most containers."))

    public_url = env["public_url"]
    public_origin = env["public_origin"]
    hosted = env["mode"] not in {"local", "development", "test"} or public_bind or bool(public_url)
    if hosted and not public_origin:
        checks.append(check("hosted_origin", "fail", "Set DIVINE_PUBLIC_URL to the canonical HTTPS origin."))
    elif hosted and not public_origin.startswith("https://"):
        checks.append(check("hosted_origin", "fail", "Hosted deployments require an https:// public origin."))
    elif public_origin:
        checks.append(check("hosted_origin", "pass", f"Canonical hosted origin is {public_origin}."))
    else:
        checks.append(check("hosted_origin", "pass", "Local mode does not require a public origin."))

    if public_origin.startswith("https://") and env["cookie_secure"]:
        checks.append(check("secure_cookies", "pass", "Secure cookies are enabled for HTTPS hosting."))
    elif hosted:
        checks.append(check("secure_cookies", "fail", "Hosted sessions require DIVINE_COOKIE_SECURE=true."))
    else:
        checks.append(check("secure_cookies", "pass", "Local cookie settings are suitable for localhost use."))

    if hosted and not env["force_https"]:
        checks.append(check("secure_transport", "fail", "Set DIVINE_FORCE_HTTPS=true for hosted traffic."))
    elif hosted:
        checks.append(check("secure_transport", "pass", "HTTPS is required for hosted application traffic."))
    else:
        checks.append(check("secure_transport", "pass", "Local HTTP is permitted only for loopback development."))

    if hosted and not env["trust_proxy"]:
        checks.append(
            check(
                "proxy_headers",
                "fail",
                "Set DIVINE_TRUST_PROXY=true behind a trusted reverse proxy that overwrites forwarding headers.",
            )
        )
    elif hosted:
        checks.append(check("proxy_headers", "pass", "Trusted reverse-proxy headers are enabled."))
    else:
        checks.append(check("proxy_headers", "pass", "Forwarded headers are ignored in local mode."))

    if hosted and (
        not env["csrf_require_origin"]
        or not public_origin
        or public_origin not in env["allowed_origins"]
        or any(not origin.startswith("https://") for origin in env["allowed_origins"])
    ):
        checks.append(
            check(
                "csrf_origin",
                "fail",
                "Hosted CSRF protection requires the canonical origin in DIVINE_ALLOWED_ORIGINS.",
            )
        )
    elif hosted:
        checks.append(check("csrf_origin", "pass", "Unsafe requests require an approved Origin or Referer."))
    else:
        checks.append(check("csrf_origin", "pass", "Cross-origin unsafe requests are rejected on localhost."))

    worker = worker_status(data_dir)
    if worker["liveness"]["ok"]:
        checks.append(check("daemon_liveness", "pass", "Daemon heartbeat is current."))
    elif worker["stale"]:
        checks.append(check("daemon_liveness", "warn", "Daemon heartbeat is stale; restart the worker service."))
    else:
        checks.append(
            check("daemon_liveness", "warn", "Daemon has not reported yet; start the worker service after deployment.")
        )

    if worker["readiness"]["ok"]:
        checks.append(check("daemon_readiness", "pass", "Latest daemon cycle completed successfully."))
    elif worker["readiness"]["state"] == "degraded":
        checks.append(
            check("daemon_readiness", "warn", "Latest daemon cycle completed with recoverable command failures.")
        )
    else:
        checks.append(check("daemon_readiness", "warn", worker["readiness"]["detail"]))

    try:
        backup_dir = env["backup_dir"]
        backup_dir.mkdir(parents=True, exist_ok=True)
        checks.append(check("backups", "pass", f"Backup directory is available: {backup_dir}"))
    except Exception as exc:
        checks.append(check("backups", "fail", f"Backup directory cannot be prepared: {exc}"))

    allowed_env = config.get("auth", {}).get("secret_management", {}).get("allowed_env_vars", [])
    checks.append(
        check(
            "secrets",
            "pass",
            "Runtime secrets are expected through environment variables: " + ", ".join(allowed_env),
        )
    )

    status = preflight_status(checks)
    return {
        "status": status,
        "version": __version__,
        "host": host,
        "port": port,
        "deployment": {
            "mode": env["mode"],
            "public_url": public_url,
            "cookie_secure": env["cookie_secure"],
            "allowed_origins": env["allowed_origins"],
            "csrf_require_origin": env["csrf_require_origin"],
            "trust_proxy": env["trust_proxy"],
            "force_https": env["force_https"],
        },
        "checks": checks,
    }


def check(name: str, severity: str, message: str) -> dict[str, str]:
    return {"name": name, "severity": severity, "message": message}


def preflight_status(checks: list[dict[str, str]]) -> str:
    severities = {item["severity"] for item in checks}
    if "fail" in severities:
        return "blocked"
    if "warn" in severities:
        return "ready_with_warnings"
    return "ready"


def format_preflight(result: dict[str, Any]) -> str:
    lines = [
        f"Deployment preflight: {result['status']}",
        f"Version: {result['version']}",
        f"Web bind: {result['host']}:{result['port']}",
    ]
    for item in result["checks"]:
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(item["severity"], item["severity"].upper())
        lines.append(f"- {marker} {item['name']}: {item['message']}")
    return "\n".join(lines)


def is_backup_state_name(name: str) -> bool:
    return name in BACKUP_STATE_FILES or PROCESSING_COMMAND_RE.fullmatch(name) is not None


def backup_state_paths(data_dir: Path) -> list[Path]:
    paths = [data_dir / name for name in BACKUP_STATE_FILES if (data_dir / name).is_file()]
    paths.extend(path for path in sorted(data_dir.glob("commands.processing.*.jsonl")) if path.is_file())
    return paths


def managed_state_paths(data_dir: Path) -> list[Path]:
    paths = backup_state_paths(data_dir)
    paths.extend(data_dir / name for name in SQLITE_SIDECAR_FILES if (data_dir / name).exists())
    return paths


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_database_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DivineToolError(f"State database does not exist: {path}")
    uri = f"{path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        integrity_rows = [str(row[0]) for row in conn.execute("PRAGMA integrity_check")]
        if integrity_rows != ["ok"]:
            raise DivineToolError("SQLite integrity check failed: " + "; ".join(integrity_rows[:5]))
        foreign_key_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if foreign_key_violations:
            raise DivineToolError(
                f"SQLite foreign-key check found {len(foreign_key_violations)} violation(s)."
            )
        current_schema = schema_version(conn)
        table_names = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        table_counts: dict[str, int] = {}
        for table_name in table_names:
            quoted_name = '"' + table_name.replace('"', '""') + '"'
            table_counts[table_name] = int(conn.execute(f"SELECT COUNT(*) FROM {quoted_name}").fetchone()[0])
        return {
            "integrity": "ok",
            "foreign_key_violations": 0,
            "schema_version": current_schema,
            "latest_schema_version": LATEST_SCHEMA_VERSION,
            "table_counts": table_counts,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }
    except sqlite3.DatabaseError as exc:
        raise DivineToolError(f"SQLite database cannot be inspected: {exc}") from exc
    finally:
        conn.close()


def inspect_jsonl_file(path: Path) -> dict[str, Any]:
    records = 0
    with path.open("r", encoding="utf-8") as source:
        for line_number, raw in enumerate(source, start=1):
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DivineToolError(f"{path.name} has invalid JSON on line {line_number}.") from exc
            if not isinstance(payload, dict):
                raise DivineToolError(f"{path.name} line {line_number} must contain a JSON object.")
            records += 1
    return {"records": records, "size_bytes": path.stat().st_size, "sha256": sha256_path(path)}


def state_integrity(
    data_dir: Path,
    *,
    require_current_schema: bool = True,
    ignore_restore_marker: bool = False,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    database: dict[str, Any] | None = None
    command_logs: dict[str, Any] = {}
    config_sha256 = ""
    config_path = data_dir / "config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise DivineToolError("config.json must contain a JSON object.")
            config_sha256 = sha256_path(config_path)
            checks.append(check("config", "pass", "Configuration JSON is valid."))
        except Exception as exc:
            checks.append(check("config", "fail", f"Configuration integrity failed: {exc}"))
    else:
        severity = "fail" if require_current_schema else "warn"
        checks.append(check("config", severity, "Configuration is absent; defaults will be created during restore."))

    database_path = data_dir / "divine_tool.sqlite3"
    if database_path.is_file():
        try:
            database = inspect_database_file(database_path)
            current_schema = int(database["schema_version"])
            if current_schema > LATEST_SCHEMA_VERSION:
                checks.append(
                    check(
                        "database",
                        "fail",
                        f"Database schema v{current_schema} is newer than supported schema v{LATEST_SCHEMA_VERSION}.",
                    )
                )
            elif current_schema < LATEST_SCHEMA_VERSION:
                severity = "fail" if require_current_schema else "warn"
                checks.append(
                    check(
                        "database",
                        severity,
                        f"Database integrity passes at schema v{current_schema}; restore will migrate it to v{LATEST_SCHEMA_VERSION}.",
                    )
                )
            else:
                checks.append(
                    check("database", "pass", f"SQLite integrity and foreign keys pass at schema v{current_schema}.")
                )
        except Exception as exc:
            checks.append(check("database", "fail", f"Database integrity failed: {exc}"))
    else:
        severity = "fail" if require_current_schema else "warn"
        checks.append(check("database", severity, "State database is absent; an empty database will be created during restore."))

    for path in backup_state_paths(data_dir):
        if not path.name.endswith(".jsonl"):
            continue
        try:
            command_logs[path.name] = inspect_jsonl_file(path)
        except Exception as exc:
            checks.append(check(f"command_log:{path.name}", "fail", str(exc)))
        else:
            checks.append(check(f"command_log:{path.name}", "pass", "Command log contains valid JSON records."))

    restore_marker = data_dir / ".restore-in-progress.json"
    if restore_marker.exists() and not ignore_restore_marker:
        checks.append(
            check(
                "restore_marker",
                "fail",
                "An interrupted restore marker is present; follow the operator recovery runbook before starting services.",
            )
        )

    severities = {item["severity"] for item in checks}
    status = "failed" if "fail" in severities else "verified_with_warnings" if "warn" in severities else "verified"
    return {
        "ok": status != "failed",
        "status": status,
        "data_dir": data_dir.resolve(),
        "checks": checks,
        "config_sha256": config_sha256,
        "database": database,
        "command_logs": command_logs,
    }


def format_integrity(result: dict[str, Any], *, title: str = "State integrity") -> str:
    lines = [f"{title}: {result['status']}"]
    for item in result["checks"]:
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(
            item["severity"], item["severity"].upper()
        )
        lines.append(f"- {marker} {item['name']}: {item['message']}")
    return "\n".join(lines)


def validate_archive_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if not infos:
        raise DivineToolError("Backup archive is empty.")
    if len(infos) > MAX_BACKUP_FILES:
        raise DivineToolError(f"Backup archive contains more than {MAX_BACKUP_FILES} files.")
    members: dict[str, zipfile.ZipInfo] = {}
    total_size = 0
    for info in infos:
        name = info.filename
        if info.is_dir() or PurePosixPath(name).name != name or "\\" in name:
            raise DivineToolError(f"Backup archive contains an unsafe path: {name!r}")
        if name in members:
            raise DivineToolError(f"Backup archive contains a duplicate file: {name}")
        if name != "manifest.json" and not is_backup_state_name(name):
            raise DivineToolError(f"Backup archive contains an unsupported file: {name}")
        unix_mode = (info.external_attr >> 16) & 0o170000
        if unix_mode == stat.S_IFLNK:
            raise DivineToolError(f"Backup archive contains a symbolic link: {name}")
        total_size += int(info.file_size)
        members[name] = info
    if "manifest.json" not in members:
        raise DivineToolError("Backup archive is missing manifest.json.")
    if total_size > MAX_BACKUP_UNCOMPRESSED_BYTES:
        raise DivineToolError("Backup archive expands beyond the supported size limit.")
    corrupt_name = archive.testzip()
    if corrupt_name:
        raise DivineToolError(f"Backup archive CRC check failed for {corrupt_name}.")
    return members


def extract_backup_archive(archive_path: Path, destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = validate_archive_members(archive)
            for name, info in members.items():
                with archive.open(info) as source, (destination / name).open("wb") as target:
                    shutil.copyfileobj(source, target)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise DivineToolError(f"Backup archive cannot be read: {exc}") from exc
    try:
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DivineToolError(f"Backup manifest is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise DivineToolError("Backup manifest must contain a JSON object.")
    return manifest


def manifest_file_records(manifest: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    try:
        format_version = int(manifest.get("format_version", 1))
    except (TypeError, ValueError) as exc:
        raise DivineToolError("Backup manifest format_version must be an integer.") from exc
    if format_version not in {1, BACKUP_FORMAT_VERSION}:
        raise DivineToolError(f"Backup format v{format_version} is not supported.")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise DivineToolError("Backup manifest must declare at least one state file.")
    records: list[dict[str, Any]] = []
    for raw in raw_files:
        if format_version == 1 and isinstance(raw, str):
            records.append({"name": raw})
            continue
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            raise DivineToolError("Backup manifest has an invalid file record.")
        records.append(raw)
    names = [str(record["name"]) for record in records]
    if len(names) != len(set(names)):
        raise DivineToolError("Backup manifest declares a file more than once.")
    if any(not is_backup_state_name(name) for name in names):
        raise DivineToolError("Backup manifest declares an unsupported state file.")
    return format_version, records


def verify_backup(archive_path: Path) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise DivineToolError(f"Backup archive does not exist: {archive_path}")
    with tempfile.TemporaryDirectory(prefix="divine-backup-verify-") as tmp:
        extracted = Path(tmp)
        manifest = extract_backup_archive(archive_path, extracted)
        format_version, records = manifest_file_records(manifest)
        declared_names = {str(record["name"]) for record in records}
        actual_names = {path.name for path in extracted.iterdir() if path.name != "manifest.json"}
        if declared_names != actual_names:
            missing = sorted(declared_names - actual_names)
            unexpected = sorted(actual_names - declared_names)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if unexpected:
                details.append("unexpected " + ", ".join(unexpected))
            raise DivineToolError("Backup manifest does not match archive contents: " + "; ".join(details))

        checks: list[dict[str, str]] = [check("archive", "pass", "ZIP paths and CRC checks pass.")]
        if format_version == BACKUP_FORMAT_VERSION:
            for record in records:
                name = str(record["name"])
                path = extracted / name
                try:
                    expected_size = int(record["size_bytes"])
                    expected_sha = str(record["sha256"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise DivineToolError(f"Backup manifest checksum record is incomplete for {name}.") from exc
                if path.stat().st_size != expected_size:
                    raise DivineToolError(f"Backup size check failed for {name}.")
                if not re.fullmatch(r"[0-9a-f]{64}", expected_sha) or sha256_path(path) != expected_sha:
                    raise DivineToolError(f"Backup checksum check failed for {name}.")
            checks.append(check("checksums", "pass", "SHA-256 checksums pass for every state file."))
        else:
            checks.append(
                check("checksums", "warn", "Legacy backup has no SHA-256 manifest; archive and state checks still pass.")
            )

        integrity = state_integrity(extracted, require_current_schema=False)
        failed_checks = [item["message"] for item in integrity["checks"] if item["severity"] == "fail"]
        if failed_checks:
            raise DivineToolError("Backup state integrity failed: " + " ".join(failed_checks))
        checks.extend(integrity["checks"])
        manifest_schema = manifest.get("schema_version")
        database = integrity.get("database") or {}
        if manifest_schema is not None:
            try:
                declared_schema = int(manifest_schema)
            except (TypeError, ValueError) as exc:
                raise DivineToolError("Backup manifest schema_version must be an integer.") from exc
            if declared_schema != int(database.get("schema_version", -1)):
                raise DivineToolError("Backup manifest schema version does not match the database.")
        status = "verified_with_warnings" if any(item["severity"] == "warn" for item in checks) else "verified"
        return {
            "ok": True,
            "status": status,
            "archive": archive_path,
            "format_version": format_version,
            "created_at": manifest.get("created_at", ""),
            "app_version": manifest.get("app_version", manifest.get("version", "unknown")),
            "schema_version": database.get("schema_version"),
            "files": sorted(declared_names),
            "checks": checks,
            "database": database,
            "config_sha256": integrity.get("config_sha256", ""),
            "command_logs": integrity.get("command_logs", {}),
        }


def next_backup_archive(backup_dir: Path, timestamp: str) -> Path:
    candidate = backup_dir / f"divine-tool-backup-{timestamp}.zip"
    suffix = 2
    while candidate.exists():
        candidate = backup_dir / f"divine-tool-backup-{timestamp}-{suffix}.zip"
        suffix += 1
    return candidate


def create_backup(data_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    if not data_dir.exists():
        raise DivineToolError(f"State directory does not exist: {data_dir}")
    source_paths = backup_state_paths(data_dir)
    if not source_paths:
        raise DivineToolError(f"No Divine Tool state was found in: {data_dir}")
    backup_dir = (output_dir or data_dir / "backups").resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().isoformat(timespec="seconds")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = next_backup_archive(backup_dir, timestamp)
    temporary_archive = backup_dir / f".{archive.name}.{uuid.uuid4().hex}.tmp"

    try:
        with tempfile.TemporaryDirectory(prefix=".divine-backup-", dir=backup_dir) as tmp:
            staging = Path(tmp)
            for source_path in source_paths:
                target_path = staging / source_path.name
                if source_path.name == "divine_tool.sqlite3":
                    source = connect(data_dir)
                    target = sqlite3.connect(target_path)
                    try:
                        source.backup(target)
                    finally:
                        target.close()
                        source.close()
                else:
                    try:
                        shutil.copy2(source_path, target_path)
                    except FileNotFoundError:
                        continue

            integrity = state_integrity(staging, require_current_schema=False)
            if not integrity["ok"]:
                failed = [item["message"] for item in integrity["checks"] if item["severity"] == "fail"]
                raise DivineToolError("Backup source integrity failed: " + " ".join(failed))
            staged_paths = backup_state_paths(staging)
            records = [
                {
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_path(path),
                }
                for path in staged_paths
            ]
            database = integrity.get("database") or {}
            manifest = {
                "format_version": BACKUP_FORMAT_VERSION,
                "created_at": created_at,
                "app_version": __version__,
                "schema_version": database.get("schema_version"),
                "files": records,
            }
            manifest_path = staging / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in [*staged_paths, manifest_path]:
                    bundle.write(path, arcname=path.name)

        verification = verify_backup(temporary_archive)
        temporary_archive.replace(archive)
        verification["archive"] = archive
    except Exception:
        temporary_archive.unlink(missing_ok=True)
        raise
    files = [*verification["files"], "manifest.json"]
    return {
        "archive": archive,
        "created_at": created_at,
        "files": files,
        "size_bytes": archive.stat().st_size,
        "verification": verification,
    }


def restore_backup(
    archive_path: Path,
    data_dir: Path,
    *,
    replace: bool = False,
    safety_output_dir: Path | None = None,
    create_safety_backup: bool = True,
) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    verification = verify_backup(archive_path)
    data_dir = data_dir.expanduser().resolve()
    existing_paths = managed_state_paths(data_dir) if data_dir.exists() else []
    existing_state = [path for path in existing_paths if path.name not in SQLITE_SIDECAR_FILES]
    if existing_state and not replace:
        raise DivineToolError(
            "Target already contains Divine Tool state. Stop web and daemon services, then repeat with --confirm."
        )
    data_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".divine-restore-stage-", dir=data_dir.parent) as tmp:
        staging = Path(tmp) / "state"
        extract_backup_archive(archive_path, staging)
        (staging / "manifest.json").unlink()
        try:
            ensure_state(staging)
        except Exception as exc:
            raise DivineToolError(f"Restore staging migration failed before live state was changed: {exc}") from exc
        for sidecar_name in SQLITE_SIDECAR_FILES:
            (staging / sidecar_name).unlink(missing_ok=True)
        staged_integrity = state_integrity(staging)
        if not staged_integrity["ok"]:
            failed = [item["message"] for item in staged_integrity["checks"] if item["severity"] == "fail"]
            raise DivineToolError("Restored staging state failed integrity checks: " + " ".join(failed))

        safety_backup: dict[str, Any] | None = None
        if existing_state and create_safety_backup:
            safety_dir = safety_output_dir.resolve() if safety_output_dir else data_dir / "backups"
            safety_backup = create_backup(data_dir, safety_dir)

        data_dir.mkdir(parents=True, exist_ok=True)
        rollback_dir = data_dir.parent / f".{data_dir.name}-restore-rollback-{uuid.uuid4().hex}"
        rollback_dir.mkdir(parents=True, exist_ok=False)
        marker_path = data_dir / ".restore-in-progress.json"
        marker_path.write_text(
            json.dumps(
                {
                    "archive": str(archive_path),
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                    "safety_backup": str(safety_backup["archive"]) if safety_backup else "",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        moved_originals: list[str] = []
        moved_restored: list[str] = []
        try:
            for path in managed_state_paths(data_dir):
                path.replace(rollback_dir / path.name)
                moved_originals.append(path.name)
            for path in backup_state_paths(staging):
                path.replace(data_dir / path.name)
                moved_restored.append(path.name)
            restored_integrity = state_integrity(data_dir, ignore_restore_marker=True)
            if not restored_integrity["ok"]:
                failed = [item["message"] for item in restored_integrity["checks"] if item["severity"] == "fail"]
                raise DivineToolError("Restored state failed final integrity checks: " + " ".join(failed))
        except Exception as exc:
            for path in managed_state_paths(data_dir):
                path.unlink(missing_ok=True)
            for name in moved_originals:
                rollback_path = rollback_dir / name
                if rollback_path.exists():
                    rollback_path.replace(data_dir / name)
            marker_path.unlink(missing_ok=True)
            shutil.rmtree(rollback_dir, ignore_errors=True)
            raise DivineToolError(f"Restore failed; original state was rolled back: {exc}") from exc
        marker_path.unlink(missing_ok=True)
        shutil.rmtree(rollback_dir, ignore_errors=True)

    return {
        "status": "restored",
        "archive": archive_path,
        "target": data_dir,
        "restored_files": sorted(moved_restored),
        "source_schema_version": verification.get("schema_version"),
        "schema_version": restored_integrity["database"]["schema_version"],
        "safety_backup": safety_backup["archive"] if safety_backup else None,
        "verification": verification,
        "integrity": restored_integrity,
    }


def recovery_check(name: str, passed: bool, message: str) -> dict[str, str]:
    return check(name, "pass" if passed else "fail", message)


def run_recovery_drills(data_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    ensure_state(data_dir)
    backup = create_backup(data_dir, output_dir)
    verification = backup["verification"]
    checks: list[dict[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="divine-recovery-drills-") as tmp:
        drill_root = Path(tmp)

        try:
            restored_dir = drill_root / "persistent-volume"
            restored = restore_backup(backup["archive"], restored_dir)
            source_counts = (verification.get("database") or {}).get("table_counts", {})
            restored_counts = (restored["integrity"].get("database") or {}).get("table_counts", {})
            checks.append(
                recovery_check(
                    "backup_restore_round_trip",
                    source_counts == restored_counts and verification.get("config_sha256") == restored["integrity"].get("config_sha256"),
                    "Verified archive restored with matching configuration and database table counts.",
                )
            )
            restart_env = dict(os.environ)
            restart_env["PYTHONIOENCODING"] = "utf-8"
            restarted_process = subprocess.run(
                [sys.executable, "-m", "divine_tool", "--data-dir", str(restored_dir), "status"],
                capture_output=True,
                text=True,
                timeout=30,
                env=restart_env,
                check=False,
            )
            restarted = state_integrity(restored_dir)
            restarted_counts = (restarted.get("database") or {}).get("table_counts", {})
            checks.append(
                recovery_check(
                    "persistent_volume_restart",
                    restarted_process.returncode == 0 and restarted["ok"] and restarted_counts == restored_counts,
                    "A fresh application process against the same persistent volume preserved state.",
                )
            )
        except Exception as exc:
            checks.append(recovery_check("backup_restore_round_trip", False, f"Round-trip restore failed: {exc}"))
            checks.append(recovery_check("persistent_volume_restart", False, "Restart persistence could not be tested."))

        try:
            interrupted_dir = drill_root / "interrupted-command"
            ensure_state(interrupted_dir)
            enqueue_command(
                interrupted_dir,
                {"action": "add_income", "amount": "7.25", "currency": "GBP", "source": "recovery drill"},
            )
            inbox = interrupted_dir / "commands.jsonl"
            claimed = interrupted_dir / "commands.processing.20260828120000000000.jsonl"
            inbox.replace(claimed)
            cycle = run_worker_cycle(interrupted_dir, trigger="test", worker_name="drill")
            recovered_income = list_income(interrupted_dir, limit=5)
            passed = (
                cycle["commands"] == {"total": 1, "succeeded": 1, "failed": 0}
                and len(recovered_income) == 1
                and not list(interrupted_dir.glob("commands.processing.*.jsonl"))
            )
            checks.append(
                recovery_check(
                    "interrupted_command_write",
                    passed,
                    "A command claimed before interruption was recovered and processed exactly once.",
                )
            )
        except Exception as exc:
            checks.append(recovery_check("interrupted_command_write", False, f"Interrupted command drill failed: {exc}"))

        try:
            migration_dir = drill_root / "migration-failure"
            ensure_state(migration_dir)

            def deliberate_failure(conn: sqlite3.Connection) -> None:
                conn.execute("CREATE TABLE drill_migration_must_rollback (id INTEGER PRIMARY KEY)")
                conn.execute("INSERT INTO drill_migration_must_rollback (id) VALUES (1)")
                raise RuntimeError("deliberate recovery drill failure")

            migration_rolled_back = False
            conn = connect(migration_dir)
            try:
                try:
                    run_migrations(
                        conn,
                        SCHEMA_MIGRATIONS
                        + (SchemaMigration(LATEST_SCHEMA_VERSION + 1, "recovery_drill_failure", deliberate_failure),),
                    )
                except RuntimeError:
                    table = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'drill_migration_must_rollback'"
                    ).fetchone()
                    migration_rolled_back = schema_version(conn) == LATEST_SCHEMA_VERSION and table is None
            finally:
                conn.close()
            checks.append(
                recovery_check(
                    "migration_failure_rollback",
                    migration_rolled_back,
                    "A deliberate migration failure rolled back schema, data, and version metadata.",
                )
            )
        except Exception as exc:
            checks.append(recovery_check("migration_failure_rollback", False, f"Migration drill failed: {exc}"))

        try:
            stale_dir = drill_root / "stale-worker"
            ensure_state(stale_dir)
            stale_started = (datetime.now() - timedelta(minutes=11)).isoformat(timespec="seconds")
            conn = connect(stale_dir)
            try:
                cursor = conn.execute(
                    "INSERT INTO worker_cycles (worker_name, trigger, status, started_at) VALUES ('daemon', 'daemon', 'running', ?)",
                    (stale_started,),
                )
                stale_cycle_id = int(cursor.lastrowid)
                conn.commit()
            finally:
                conn.close()
            recovered_cycle = run_worker_cycle(stale_dir, trigger="daemon", worker_name="daemon")
            cycles = {cycle["id"]: cycle for cycle in list_worker_cycles(stale_dir)}
            stale_recovered = cycles[stale_cycle_id]["status"] == "interrupted" and recovered_cycle["status"] == "succeeded"
            checks.append(
                recovery_check(
                    "stale_worker_recovery",
                    stale_recovered,
                    "A stale running cycle was marked interrupted before the next daemon cycle succeeded.",
                )
            )
        except Exception as exc:
            checks.append(recovery_check("stale_worker_recovery", False, f"Stale worker drill failed: {exc}"))

    status = "passed" if all(item["severity"] == "pass" for item in checks) else "failed"
    return {
        "ok": status == "passed",
        "status": status,
        "backup": backup["archive"],
        "checks": checks,
    }


def format_recovery_drills(result: dict[str, Any]) -> str:
    lines = [f"Recovery drills: {result['status']}", f"Verified backup: {result['backup']}"]
    for item in result["checks"]:
        marker = "PASS" if item["severity"] == "pass" else "FAIL"
        lines.append(f"- {marker} {item['name']}: {item['message']}")
    return "\n".join(lines)


def healthcheck_url(url: str, timeout: float = 5.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            ok = response.status == 200 and bool(payload.get("ok"))
            return {"ok": ok, "status_code": response.status, "payload": payload}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "status_code": None, "error": str(exc)}
